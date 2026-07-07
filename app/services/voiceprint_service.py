import array
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any

from app.repositories.family_repository import FamilyMemberRecord, FamilyRepository
from app.services.speaker_service import SpeakerVerificationService


@dataclass(frozen=True)
class RegisteredVoiceprint:
    family_id: int
    name: str
    relation: str
    model_name: str


@dataclass(frozen=True)
class FamilyVoiceMatch:
    family_id: int
    name: str
    relation: str
    similarity: float
    sample_count: int = 1
    max_similarity: float | None = None
    mean_similarity: float | None = None
    median_similarity: float | None = None
    weighted_mean_similarity: float | None = None
    weighted_median_similarity: float | None = None
    profile_threshold: float | None = None
    confidence_score: float | None = None
    sample_quality: str | None = None
    low_quality_sample_count: int = 0


@dataclass(frozen=True)
class FamilyVerificationResult:
    is_registered_family: bool
    best_match: FamilyVoiceMatch | None
    threshold: float
    candidates: list[FamilyVoiceMatch]
    message: str
    model_name: str


@dataclass(frozen=True)
class StoredVoiceprint:
    record: FamilyMemberRecord
    embedding: Any


@dataclass(frozen=True)
class ProfileCalibration:
    threshold: float
    confidence_score: float
    sample_weights: dict[int, float]
    sample_quality: dict[int, str]
    low_quality_sample_count: int


class VoiceprintService:
    """Application service for registering and reading family voiceprints."""

    def __init__(
        self,
        family_repository: FamilyRepository,
        speaker_service: SpeakerVerificationService | None = None,
    ):
        self.family_repository = family_repository
        self.speaker_service = speaker_service

    def register_family_voice(
        self,
        name: str,
        relation: str,
        wav_path: Path,
    ) -> RegisteredVoiceprint:
        """Extract a speaker embedding and store it as a hidden DB voiceprint."""

        normalized_name = name.strip()
        normalized_relation = relation.strip()
        if not normalized_name:
            raise ValueError("name is required")
        if not normalized_relation:
            raise ValueError("relation is required")
        if self.speaker_service is None:
            raise RuntimeError("speaker service is required to register a voiceprint")

        embedding = self.speaker_service.extract_embedding(wav_path)
        embedding_blob = self.embedding_to_bytes(embedding)

        record = self.family_repository.create(
            name=normalized_name,
            relation=normalized_relation,
            embedding=embedding_blob,
            model_name=self.speaker_service.model_name,
        )

        return self._record_to_voiceprint(record)

    def list_family_members(self) -> list[RegisteredVoiceprint]:
        return [self._record_to_voiceprint(record) for record in self.family_repository.list_all()]

    def get_family_member(self, family_id: int) -> RegisteredVoiceprint | None:
        record = self.family_repository.get(family_id)
        if record is None:
            return None
        return self._record_to_voiceprint(record)

    def delete_family_member(self, family_id: int) -> bool:
        return self.family_repository.delete(family_id)

    def verify_family_voice(self, wav_path: Path) -> FamilyVerificationResult:
        """Compare one new voice against every registered family voiceprint."""

        if self.speaker_service is None:
            raise RuntimeError("speaker service is required to verify a voiceprint")

        records = self.family_repository.list_all()
        if not records:
            return FamilyVerificationResult(
                is_registered_family=False,
                best_match=None,
                threshold=self.speaker_service.threshold,
                candidates=[],
                message="no_registered_family_voiceprints",
                model_name=self.speaker_service.model_name,
            )

        query_embedding = self.speaker_service.extract_embedding(wav_path)
        stored_voiceprints = [
            StoredVoiceprint(
                record=record,
                embedding=self.embedding_from_bytes(
                    embedding_blob=record.embedding,
                    torch_module=self.speaker_service.torch,
                ),
            )
            for record in records
        ]
        profile_calibrations = self._calibrate_profiles(stored_voiceprints)
        raw_matches: list[FamilyVoiceMatch] = []

        for stored_voiceprint in stored_voiceprints:
            record = stored_voiceprint.record
            similarity = self.speaker_service.compare_embeddings(
                query_embedding,
                stored_voiceprint.embedding,
            )
            calibration = profile_calibrations.get(
                self._profile_key(record.name, record.relation)
            )
            sample_quality = (
                calibration.sample_quality.get(record.id)
                if calibration is not None
                else None
            )
            raw_matches.append(
                FamilyVoiceMatch(
                    family_id=record.id,
                    name=record.name,
                    relation=record.relation,
                    similarity=similarity,
                    profile_threshold=calibration.threshold if calibration else None,
                    confidence_score=calibration.confidence_score if calibration else None,
                    sample_quality=sample_quality,
                )
            )

        candidates = self._aggregate_family_matches(raw_matches, profile_calibrations)
        best_match = candidates[0]
        decision_threshold = best_match.profile_threshold or self.speaker_service.threshold
        is_registered_family = best_match.similarity >= decision_threshold
        message = (
            "registered_family_matched"
            if is_registered_family
            else "no_registered_family_match"
        )

        return FamilyVerificationResult(
            is_registered_family=is_registered_family,
            best_match=best_match,
            threshold=decision_threshold,
            candidates=candidates,
            message=message,
            model_name=self.speaker_service.model_name,
        )

    def _aggregate_family_matches(
        self,
        raw_matches: list[FamilyVoiceMatch],
        profile_calibrations: dict[tuple[str, str], ProfileCalibration],
    ) -> list[FamilyVoiceMatch]:
        """Group repeated voice samples for the same family profile.

        A competition demo should not trust a single lucky similarity spike.
        When the same name/relation is registered multiple times, the decision
        score uses the median similarity and still exposes max/mean values for
        explainability.
        """

        grouped: dict[tuple[str, str], list[FamilyVoiceMatch]] = {}
        for match in raw_matches:
            key = self._profile_key(match.name, match.relation)
            grouped.setdefault(key, []).append(match)

        candidates: list[FamilyVoiceMatch] = []
        for key, matches in grouped.items():
            similarities = [match.similarity for match in matches]
            representative = min(matches, key=lambda match: match.family_id)
            calibration = profile_calibrations.get(key)
            weights = [
                calibration.sample_weights.get(match.family_id, 1.0)
                if calibration is not None
                else 1.0
                for match in matches
            ]
            weighted_median_similarity = self._weighted_median(similarities, weights)
            weighted_mean_similarity = self._weighted_mean(similarities, weights)
            median_similarity = round(float(median(similarities)), 4)
            candidates.append(
                FamilyVoiceMatch(
                    family_id=representative.family_id,
                    name=representative.name,
                    relation=representative.relation,
                    similarity=weighted_median_similarity,
                    sample_count=len(matches),
                    max_similarity=round(max(similarities), 4),
                    mean_similarity=round(float(mean(similarities)), 4),
                    median_similarity=median_similarity,
                    weighted_mean_similarity=weighted_mean_similarity,
                    weighted_median_similarity=weighted_median_similarity,
                    profile_threshold=(
                        calibration.threshold if calibration else self.speaker_service.threshold
                    ),
                    confidence_score=calibration.confidence_score if calibration else None,
                    sample_quality=(
                        "review"
                        if calibration and calibration.low_quality_sample_count > 0
                        else "ok"
                    ),
                    low_quality_sample_count=(
                        calibration.low_quality_sample_count if calibration else 0
                    ),
                )
            )

        candidates.sort(key=lambda candidate: candidate.similarity, reverse=True)
        return candidates

    def _calibrate_profiles(
        self,
        stored_voiceprints: list[StoredVoiceprint],
    ) -> dict[tuple[str, str], ProfileCalibration]:
        grouped: dict[tuple[str, str], list[StoredVoiceprint]] = {}
        for stored_voiceprint in stored_voiceprints:
            key = self._profile_key(
                stored_voiceprint.record.name,
                stored_voiceprint.record.relation,
            )
            grouped.setdefault(key, []).append(stored_voiceprint)

        calibrations: dict[tuple[str, str], ProfileCalibration] = {}
        for key, profile_items in grouped.items():
            same_scores: list[float] = []
            diff_scores: list[float] = []
            sample_same_scores: dict[int, list[float]] = {
                item.record.id: [] for item in profile_items
            }
            sample_diff_scores: dict[int, list[float]] = {
                item.record.id: [] for item in profile_items
            }

            for left_index, left in enumerate(profile_items):
                for right in profile_items[left_index + 1 :]:
                    similarity = self.speaker_service.compare_embeddings(
                        left.embedding,
                        right.embedding,
                    )
                    same_scores.append(similarity)
                    sample_same_scores[left.record.id].append(similarity)
                    sample_same_scores[right.record.id].append(similarity)

                for other_key, other_items in grouped.items():
                    if other_key == key:
                        continue
                    for other in other_items:
                        similarity = self.speaker_service.compare_embeddings(
                            left.embedding,
                            other.embedding,
                        )
                        diff_scores.append(similarity)
                        sample_diff_scores[left.record.id].append(similarity)

            threshold = self.speaker_service.threshold
            confidence_score = 0.5
            if same_scores and diff_scores:
                min_same = min(same_scores)
                max_diff = max(diff_scores)
                gap = min_same - max_diff
                if gap > 0:
                    threshold = max(threshold, round(min_same - 0.02, 4))
                confidence_score = round(max(0.0, min(1.0, gap / 0.15)), 4)

            sample_weights: dict[int, float] = {}
            sample_quality: dict[int, str] = {}
            for item in profile_items:
                record_id = item.record.id
                own_same_scores = sample_same_scores.get(record_id, [])
                own_diff_scores = sample_diff_scores.get(record_id, [])
                min_same = min(own_same_scores) if own_same_scores else 0.0
                mean_same = mean(own_same_scores) if own_same_scores else 0.0
                max_diff = max(own_diff_scores) if own_diff_scores else 0.0

                needs_review = False
                if own_same_scores and min_same < threshold + 0.03:
                    needs_review = True
                if own_same_scores and mean_same < threshold + 0.08:
                    needs_review = True
                if own_diff_scores and max_diff > threshold - 0.05:
                    needs_review = True

                sample_quality[record_id] = "review" if needs_review else "ok"
                sample_weights[record_id] = 0.6 if needs_review else 1.0

            low_quality_sample_count = sum(
                1 for quality in sample_quality.values() if quality == "review"
            )
            calibrations[key] = ProfileCalibration(
                threshold=threshold,
                confidence_score=confidence_score,
                sample_weights=sample_weights,
                sample_quality=sample_quality,
                low_quality_sample_count=low_quality_sample_count,
            )

        return calibrations

    @staticmethod
    def _profile_key(name: str, relation: str) -> tuple[str, str]:
        return (name.strip().lower(), relation.strip().lower())

    @staticmethod
    def _weighted_mean(values: list[float], weights: list[float]) -> float:
        total_weight = sum(weights)
        if total_weight <= 0:
            return round(float(mean(values)), 4)
        return round(sum(value * weight for value, weight in zip(values, weights)) / total_weight, 4)

    @staticmethod
    def _weighted_median(values: list[float], weights: list[float]) -> float:
        pairs = sorted(zip(values, weights), key=lambda item: item[0])
        total_weight = sum(weights)
        if total_weight <= 0:
            return round(float(median(values)), 4)

        midpoint = total_weight / 2.0
        running = 0.0
        for value, weight in pairs:
            running += weight
            if running >= midpoint:
                return round(value, 4)
        return round(pairs[-1][0], 4)

    @staticmethod
    def embedding_to_bytes(embedding: Any) -> bytes:
        """Serialize a 1D float embedding without exposing it through the API."""

        values = array.array("f", [float(value) for value in embedding.flatten().tolist()])
        return values.tobytes()

    @staticmethod
    def embedding_from_bytes(embedding_blob: bytes, torch_module: Any) -> Any:
        """Rebuild an embedding tensor. This will be used by the 3rd phase comparison API."""

        values = array.array("f")
        values.frombytes(embedding_blob)
        return torch_module.tensor(values, dtype=torch_module.float32)

    @staticmethod
    def _record_to_voiceprint(record: FamilyMemberRecord) -> RegisteredVoiceprint:
        return RegisteredVoiceprint(
            family_id=record.id,
            name=record.name,
            relation=record.relation,
            model_name=record.model_name,
        )
