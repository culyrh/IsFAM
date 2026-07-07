#!/usr/bin/env python3
"""Evaluate IsFAM risk scoring on datasets/eval.

This script uses the already registered family DB voiceprints and writes a CSV
with family similarity, spoof score, risk score, and final decision per file.
It does not train any model.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings
from app.repositories.family_repository import FamilyRepository
from app.services.model_provider import get_anti_spoofing_service, get_speaker_service
from app.services.risk_scoring_service import RiskScoringService
from app.services.voiceprint_service import VoiceprintService
from app.utils.audio import cleanup_temp_files, convert_audio_to_standard_wav


DEFAULT_EVAL_DIR = ROOT_DIR / "datasets" / "eval"
DEFAULT_OUTPUT = ROOT_DIR / "reports" / "isfam_eval_results.csv"

GROUP_EXPECTED_RISK = {
    "family_real": "safe",
    "non_family_real": "caution",
    "family_deepvoice": "danger",
    "ai_voice": "danger",
    "noisy_call": "caution",
}


@dataclass(frozen=True)
class EvalFile:
    path: Path
    group: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate IsFAM family verification + anti-spoofing risk scoring."
    )
    parser.add_argument("--eval-dir", type=Path, default=DEFAULT_EVAL_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--include-register",
        action="store_true",
        help="Also evaluate *_register_* files. Useful only for a quick smoke test.",
    )
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def collect_eval_files(eval_dir: Path, allowed_extensions: tuple[str, ...], include_register: bool) -> list[EvalFile]:
    allowed = {extension.lower().lstrip(".") for extension in allowed_extensions}
    files: list[EvalFile] = []

    for group in GROUP_EXPECTED_RISK:
        group_dir = eval_dir / group
        if not group_dir.exists():
            continue
        for path in sorted(group_dir.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.suffix.lower().lstrip(".") not in allowed:
                continue
            if not include_register and "_register_" in path.stem:
                continue
            files.append(EvalFile(path=path, group=group))

    return files


def write_csv(output_path: Path, rows: list[dict[str, object]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "file",
        "group",
        "expected_risk",
        "risk_level",
        "risk_score",
        "family_confidence",
        "mismatch_confidence",
        "final_decision",
        "is_trusted",
        "is_expected_risk",
        "best_family_name",
        "best_family_relation",
        "best_family_similarity",
        "best_family_sample_count",
        "best_family_mean_similarity",
        "best_family_max_similarity",
        "speaker_threshold",
        "profile_threshold",
        "profile_confidence",
        "weighted_median_similarity",
        "low_quality_sample_count",
        "is_registered_family",
        "spoof_score",
        "anti_spoofing_threshold",
        "is_spoofed",
        "predicted_spoof_label",
        "decision_reasons_json",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def evaluate(args: argparse.Namespace) -> None:
    settings = get_settings()
    files = collect_eval_files(args.eval_dir, settings.allowed_audio_extensions, args.include_register)
    if args.limit is not None:
        files = files[: args.limit]
    if not files:
        raise SystemExit(
            f"No evaluation files found in {args.eval_dir}. "
            "Add *_test_*, deepvoice, ai_voice, or noisy_call files first."
        )

    voiceprint_service = VoiceprintService(
        family_repository=FamilyRepository(settings.database_path),
        speaker_service=get_speaker_service(),
    )
    anti_spoofing_service = get_anti_spoofing_service()
    risk_service = RiskScoringService(
        strong_spoof_score=settings.voice_session_strong_spoof_score,
    )

    rows: list[dict[str, object]] = []
    temp_paths: list[Path | None] = []
    try:
        for index, item in enumerate(files, start=1):
            print(f"[{index}/{len(files)}] evaluating {item.path}")
            wav_path = convert_audio_to_standard_wav(
                input_path=item.path,
                target_sample_rate=settings.target_sample_rate,
                min_audio_seconds=settings.min_audio_seconds,
            )
            temp_paths.append(wav_path)

            family_result = voiceprint_service.verify_family_voice(wav_path)
            anti_result = anti_spoofing_service.detect_file(wav_path)
            risk_result = risk_service.score_secure_voice(family_result, anti_result)
            best = family_result.best_match
            expected_risk = GROUP_EXPECTED_RISK[item.group]

            rows.append(
                {
                    "file": str(item.path.relative_to(args.eval_dir)),
                    "group": item.group,
                    "expected_risk": expected_risk,
                    "risk_level": risk_result.risk_level,
                    "risk_score": risk_result.risk_score,
                    "family_confidence": risk_result.family_confidence,
                    "mismatch_confidence": risk_result.mismatch_confidence,
                    "final_decision": risk_result.final_decision,
                    "is_trusted": risk_result.is_trusted,
                    "is_expected_risk": risk_result.risk_level == expected_risk,
                    "best_family_name": best.name if best else "",
                    "best_family_relation": best.relation if best else "",
                    "best_family_similarity": best.similarity if best else "",
                    "best_family_sample_count": best.sample_count if best else "",
                    "best_family_mean_similarity": best.mean_similarity if best else "",
                    "best_family_max_similarity": best.max_similarity if best else "",
                    "speaker_threshold": family_result.threshold,
                    "profile_threshold": best.profile_threshold if best else "",
                    "profile_confidence": best.confidence_score if best else "",
                    "weighted_median_similarity": (
                        best.weighted_median_similarity if best else ""
                    ),
                    "low_quality_sample_count": best.low_quality_sample_count if best else "",
                    "is_registered_family": family_result.is_registered_family,
                    "spoof_score": anti_result.spoof_score,
                    "anti_spoofing_threshold": anti_result.threshold,
                    "is_spoofed": anti_result.is_spoofed,
                    "predicted_spoof_label": anti_result.predicted_label,
                    "decision_reasons_json": json.dumps(risk_result.reasons, ensure_ascii=False),
                }
            )
    finally:
        cleanup_temp_files(temp_paths)

    write_csv(args.output, rows)
    correct = sum(1 for row in rows if row["is_expected_risk"])
    print(f"saved results: {args.output}")
    print(f"risk-level match: {correct}/{len(rows)}")


if __name__ == "__main__":
    evaluate(parse_args())
