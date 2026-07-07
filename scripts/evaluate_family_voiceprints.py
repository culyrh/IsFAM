#!/usr/bin/env python3
"""Evaluate registered family voiceprint separability.

This evaluates only the family_real audio currently available. It does not
measure deepfake detection accuracy because no fake/non-family evaluation audio
is required for this script.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings
from app.services.model_provider import get_speaker_service
from app.utils.audio import cleanup_temp_files, convert_audio_to_standard_wav


DEFAULT_EVAL_DIR = ROOT_DIR / "datasets" / "eval" / "family_real"
DEFAULT_PAIR_OUTPUT = ROOT_DIR / "reports" / "family_voiceprint_pairs.csv"
DEFAULT_METRICS_OUTPUT = ROOT_DIR / "reports" / "family_voiceprint_threshold_metrics.csv"
DEFAULT_SUMMARY_OUTPUT = ROOT_DIR / "reports" / "family_voiceprint_summary.md"
DEFAULT_THRESHOLDS = "0.50,0.55,0.60,0.65,0.70,0.72,0.75,0.78,0.80,0.85"


@dataclass(frozen=True)
class AudioSample:
    path: Path
    speaker_key: str
    embedding: Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate how well current family samples separate by speaker."
    )
    parser.add_argument("--eval-dir", type=Path, default=DEFAULT_EVAL_DIR)
    parser.add_argument("--pair-output", type=Path, default=DEFAULT_PAIR_OUTPUT)
    parser.add_argument("--metrics-output", type=Path, default=DEFAULT_METRICS_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    return parser.parse_args()


def parse_thresholds(raw_value: str) -> list[float]:
    return [float(item.strip()) for item in raw_value.split(",") if item.strip()]


def speaker_key_from_filename(path: Path) -> str:
    stem = path.stem.lower()
    for marker in ("_register_", "_test_", "_noisy_", "_deepvoice_"):
        if marker in stem:
            return stem.split(marker, 1)[0]
    return stem.split("_", 1)[0]


def collect_audio_files(eval_dir: Path, allowed_extensions: tuple[str, ...]) -> list[Path]:
    allowed = {extension.lower().lstrip(".") for extension in allowed_extensions}
    return [
        path
        for path in sorted(eval_dir.iterdir())
        if path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower().lstrip(".") in allowed
    ]


def load_samples(eval_dir: Path) -> list[AudioSample]:
    settings = get_settings()
    service = get_speaker_service()
    paths = collect_audio_files(eval_dir, settings.allowed_audio_extensions)
    if len(paths) < 2:
        raise SystemExit(f"Need at least 2 audio files in {eval_dir}")

    temp_paths: list[Path | None] = []
    samples: list[AudioSample] = []
    try:
        for index, path in enumerate(paths, start=1):
            print(f"[{index}/{len(paths)}] embedding {path.name}")
            wav_path = convert_audio_to_standard_wav(
                input_path=path,
                target_sample_rate=settings.target_sample_rate,
                min_audio_seconds=settings.min_audio_seconds,
            )
            temp_paths.append(wav_path)
            samples.append(
                AudioSample(
                    path=path,
                    speaker_key=speaker_key_from_filename(path),
                    embedding=service.extract_embedding(wav_path),
                )
            )
    finally:
        cleanup_temp_files(temp_paths)

    return samples


def build_pair_rows(samples: list[AudioSample]) -> list[dict[str, object]]:
    service = get_speaker_service()
    rows: list[dict[str, object]] = []
    for left_index, left in enumerate(samples):
        for right in samples[left_index + 1 :]:
            is_same = left.speaker_key == right.speaker_key
            similarity = service.compare_embeddings(left.embedding, right.embedding)
            rows.append(
                {
                    "audio_file_1": left.path.name,
                    "speaker_1": left.speaker_key,
                    "audio_file_2": right.path.name,
                    "speaker_2": right.speaker_key,
                    "label": "same" if is_same else "different",
                    "similarity": similarity,
                }
            )
    return rows


def compute_threshold_metrics(
    pair_rows: list[dict[str, object]],
    thresholds: list[float],
) -> list[dict[str, object]]:
    metrics: list[dict[str, object]] = []
    for threshold in thresholds:
        tp = tn = fp = fn = 0
        for row in pair_rows:
            expected_same = row["label"] == "same"
            predicted_same = float(row["similarity"]) >= threshold
            if expected_same and predicted_same:
                tp += 1
            elif expected_same and not predicted_same:
                fn += 1
            elif not expected_same and predicted_same:
                fp += 1
            else:
                tn += 1

        total = tp + tn + fp + fn
        correct = tp + tn
        far = fp / (fp + tn) if fp + tn else 0.0
        frr = fn / (fn + tp) if fn + tp else 0.0
        metrics.append(
            {
                "threshold": threshold,
                "total_pairs": total,
                "correct": correct,
                "accuracy": round(correct / total, 4) if total else 0.0,
                "tp_same_accept": tp,
                "tn_diff_reject": tn,
                "fp_diff_accept": fp,
                "fn_same_reject": fn,
                "false_accept_rate": round(far, 4),
                "false_reject_rate": round(frr, 4),
            }
        )
    return metrics


def compute_leave_one_out(samples: list[AudioSample]) -> dict[str, object]:
    service = get_speaker_service()
    correct = 0
    margins: list[float] = []

    for query in samples:
        scored = [
            (candidate, service.compare_embeddings(query.embedding, candidate.embedding))
            for candidate in samples
            if candidate.path != query.path
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        best_sample, best_similarity = scored[0]
        second_similarity = scored[1][1] if len(scored) > 1 else 0.0
        if best_sample.speaker_key == query.speaker_key:
            correct += 1
        margins.append(round(best_similarity - second_similarity, 4))

    return {
        "total_files": len(samples),
        "correct_identifications": correct,
        "identification_accuracy": round(correct / len(samples), 4),
        "mean_top1_margin": round(statistics.mean(margins), 4) if margins else 0.0,
        "min_top1_margin": round(min(margins), 4) if margins else 0.0,
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_summary(
    path: Path,
    samples: list[AudioSample],
    pair_rows: list[dict[str, object]],
    metrics: list[dict[str, object]],
    loo: dict[str, object],
) -> None:
    same_scores = [float(row["similarity"]) for row in pair_rows if row["label"] == "same"]
    diff_scores = [float(row["similarity"]) for row in pair_rows if row["label"] == "different"]
    best_metric = max(
        metrics,
        key=lambda row: (float(row["accuracy"]), -abs(float(row["false_accept_rate"]) - float(row["false_reject_rate"]))),
    )

    min_same = min(same_scores) if same_scores else 0.0
    max_diff = max(diff_scores) if diff_scores else 0.0
    gap = round(min_same - max_diff, 4)

    lines = [
        "# Family Voiceprint Evaluation",
        "",
        "This report uses only current `datasets/eval/family_real` audio files.",
        "It measures family voiceprint separability, not deepfake detection accuracy.",
        "",
        "## Dataset",
        "",
        f"- files: {len(samples)}",
        f"- speakers: {', '.join(sorted({sample.speaker_key for sample in samples}))}",
        f"- same-speaker pairs: {len(same_scores)}",
        f"- different-speaker pairs: {len(diff_scores)}",
        "",
        "## Similarity Distribution",
        "",
        f"- same mean: {statistics.mean(same_scores):.4f}" if same_scores else "- same mean: n/a",
        f"- same min: {min_same:.4f}" if same_scores else "- same min: n/a",
        f"- same max: {max(same_scores):.4f}" if same_scores else "- same max: n/a",
        f"- different mean: {statistics.mean(diff_scores):.4f}" if diff_scores else "- different mean: n/a",
        f"- different min: {min(diff_scores):.4f}" if diff_scores else "- different min: n/a",
        f"- different max: {max_diff:.4f}" if diff_scores else "- different max: n/a",
        f"- separation gap `(min same - max different)`: {gap:.4f}",
        "",
        "## Best Threshold In Sweep",
        "",
        f"- threshold: {best_metric['threshold']}",
        f"- accuracy: {best_metric['accuracy']}",
        f"- false accept rate: {best_metric['false_accept_rate']}",
        f"- false reject rate: {best_metric['false_reject_rate']}",
        "",
        "## Leave-One-Out Identification",
        "",
        f"- accuracy: {loo['identification_accuracy']}",
        f"- correct: {loo['correct_identifications']}/{loo['total_files']}",
        f"- mean top-1 margin: {loo['mean_top1_margin']}",
        f"- min top-1 margin: {loo['min_top1_margin']}",
        "",
        "## Interpretation",
        "",
    ]

    if gap > 0:
        lines.append("Current family samples are separable in this dataset.")
    else:
        lines.append(
            "Current family samples overlap. Collect cleaner or more varied registration samples before relying on strict thresholds."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    samples = load_samples(args.eval_dir)
    pair_rows = build_pair_rows(samples)
    metrics = compute_threshold_metrics(pair_rows, parse_thresholds(args.thresholds))
    loo = compute_leave_one_out(samples)

    write_csv(args.pair_output, pair_rows)
    write_csv(args.metrics_output, metrics)
    write_summary(args.summary_output, samples, pair_rows, metrics, loo)

    print(f"saved pair details: {args.pair_output}")
    print(f"saved threshold metrics: {args.metrics_output}")
    print(f"saved summary: {args.summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
