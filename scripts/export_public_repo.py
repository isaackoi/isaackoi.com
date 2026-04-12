from __future__ import annotations

import argparse
import shutil
from pathlib import Path


EXCLUDED_NAMES = {
    ".git",
    ".bundle",
    ".jekyll-cache",
    ".jekyll-metadata",
    ".sass-cache",
    "_site",
    "tmp",
    "vendor",
}
PRESERVED_ROOT_FILES = {"Gemfile.lock"}


def reset_output_root(output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    for child in output_root.iterdir():
        if child.name in EXCLUDED_NAMES or child.name in PRESERVED_ROOT_FILES:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def should_exclude(path: Path) -> bool:
    return any(part in EXCLUDED_NAMES for part in path.parts)


def export_public_repo(source_root: Path, output_root: Path) -> dict[str, int]:
    if not source_root.exists():
        raise FileNotFoundError(f"Source root does not exist: {source_root}")

    reset_output_root(output_root)

    copied_files = 0
    copied_dirs: set[Path] = set()

    for source_path in source_root.rglob("*"):
        relative_path = source_path.relative_to(source_root)
        if should_exclude(relative_path):
            continue
        target_path = output_root / relative_path
        if len(relative_path.parts) == 1 and relative_path.name in PRESERVED_ROOT_FILES and target_path.exists():
            continue
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            copied_dirs.add(relative_path)
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied_files += 1

    return {
        "copied_files": copied_files,
        "copied_directories": len(copied_dirs),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage a clean standalone public repo from the generated Jekyll tree.")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("jekyll-site"),
        help="Generated Jekyll source tree to export from.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("jekyll-public-repo"),
        help="Destination staging directory for the standalone public repo.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = export_public_repo(args.source_root.resolve(), args.output_root.resolve())
    print(
        f"Exported clean public repo staging tree with {result['copied_files']} files "
        f"and {result['copied_directories']} directories into {args.output_root.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
