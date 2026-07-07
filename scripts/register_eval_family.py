#!/usr/bin/env python3
"""Register evaluation family voice samples into the local IsFAM DB.

This script reads datasets/eval/family_real/*_register_* audio files and
registers them as family voiceprints. It is intentionally not a training script.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings
from app.db.session import get_connection, init_db
from app.repositories.family_repository import FamilyRepository
from app.services.model_provider import get_speaker_service
from app.services.voiceprint_service import VoiceprintService
from app.utils.audio import cleanup_temp_files, convert_audio_to_standard_wav


DEFAULT_EVAL_DIR = ROOT_DIR / "datasets" / "eval" / "family_real"

PROFILE_MAP = {
    "mom": ("엄마", "mother"),
    "mother": ("엄마", "mother"),
    "dad": ("아빠", "father"),
    "father": ("아빠", "father"),
    "daughter": ("딸", "daughter"),
    "son": ("아들", "son"),
}


@dataclass(frozen=True)
class RegisterFile:
    path: Path
    key: str
    name: str
    relation: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register datasets/eval/family_real/*_register_* audio as IsFAM family voiceprints."
    )
    parser.add_argument(
        "--eval-dir",
        type=Path,
        default=DEFAULT_EVAL_DIR,
        help="Directory containing family register audio files.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not remove existing DB voiceprints for discovered profiles before registration.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be registered without loading models or writing DB rows.",
    )
    return parser.parse_args()


def discover_register_files(eval_dir: Path) -> list[RegisterFile]:
    if not eval_dir.exists():
        raise FileNotFoundError(f"evaluation directory does not exist: {eval_dir}")

    files: list[RegisterFile] = []
    for path in sorted(eval_dir.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        if "_register_" not in path.stem:
            continue

        key = path.stem.split("_register_", 1)[0].lower().strip()
        name, relation = PROFILE_MAP.get(key, (key, key))
        files.append(RegisterFile(path=path, key=key, name=name, relation=relation))

    return files


def reset_profiles(database_path: Path, files: list[RegisterFile]) -> None:
    profiles = sorted({(item.name, item.relation) for item in files})
    with get_connection(database_path) as connection:
        for name, relation in profiles:
            connection.execute(
                "DELETE FROM family_members WHERE name = ? AND relation = ?",
                (name, relation),
            )
        connection.commit()


def register_files(files: list[RegisterFile]) -> None:
    settings = get_settings()
    init_db(settings)
    repository = FamilyRepository(settings.database_path)
    service = VoiceprintService(
        family_repository=repository,
        speaker_service=get_speaker_service(),
    )

    for item in files:
        temp_paths: list[Path | None] = []
        try:
            wav_path = convert_audio_to_standard_wav(
                input_path=item.path,
                target_sample_rate=settings.target_sample_rate,
                min_audio_seconds=settings.min_audio_seconds,
            )
            temp_paths.append(wav_path)
            registered = service.register_family_voice(
                name=item.name,
                relation=item.relation,
                wav_path=wav_path,
            )
            print(
                f"registered family_id={registered.family_id} "
                f"name={registered.name} relation={registered.relation} file={item.path.name}"
            )
        finally:
            cleanup_temp_files(temp_paths)


def main() -> int:
    args = parse_args()
    files = discover_register_files(args.eval_dir)

    if not files:
        print(f"no *_register_* files found in {args.eval_dir}")
        return 1

    print("discovered register files:")
    for item in files:
        print(f"- {item.path.name} -> name={item.name} relation={item.relation}")

    if args.dry_run:
        print("dry run complete. DB was not modified.")
        return 0

    settings = get_settings()
    init_db(settings)

    if not args.keep_existing:
        reset_profiles(settings.database_path, files)
        print("removed existing DB voiceprints for discovered profiles")

    register_files(files)
    print(f"done. database={settings.database_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
