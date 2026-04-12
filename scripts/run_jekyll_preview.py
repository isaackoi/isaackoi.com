from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def resolve_command(command: list[str]) -> list[str]:
    executable = command[0]
    resolved = shutil.which(executable)
    if resolved:
        return [resolved, *command[1:]]
    if os.name == "nt" and "." not in executable:
        for suffix in (".bat", ".cmd", ".exe"):
            resolved = shutil.which(executable + suffix)
            if resolved:
                return [resolved, *command[1:]]
    return command


def run_command(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(resolve_command(command), cwd=str(cwd), check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a filtered Jekyll preview tree and run a local Jekyll build or server."
    )
    parser.add_argument(
        "--route-prefix",
        action="append",
        default=[],
        help="Include only content under this route prefix, e.g. /ufo-history/ufo-books",
    )
    parser.add_argument(
        "--limit-items",
        type=int,
        default=40,
        help="Limit the number of article pages after filtering. Defaults to 40.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("jekyll-site-preview"),
        help="Output directory for the generated preview tree.",
    )
    parser.add_argument(
        "--skip-bundle-install",
        action="store_true",
        help="Skip bundle install before the Jekyll command.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run `bundle exec jekyll serve` instead of `bundle exec jekyll build --profile`.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for `jekyll serve`.")
    parser.add_argument("--port", type=int, default=4000, help="Port for `jekyll serve`.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output_root = (repo_root / args.output_root).resolve()

    build_command = [
        sys.executable,
        str(repo_root / "scripts" / "build_jekyll_site.py"),
        "--output-root",
        str(output_root),
    ]
    for route_prefix in args.route_prefix:
        build_command.extend(["--route-prefix", route_prefix])
    if args.limit_items is not None:
        build_command.extend(["--limit-items", str(args.limit_items)])

    run_command(build_command, cwd=repo_root)

    if not args.skip_bundle_install:
        run_command(["bundle", "install"], cwd=output_root)

    if args.serve:
        jekyll_command = [
            "bundle",
            "exec",
            "jekyll",
            "serve",
            "--host",
            args.host,
            "--port",
            str(args.port),
        ]
    else:
        jekyll_command = ["bundle", "exec", "jekyll", "build", "--profile"]

    run_command(jekyll_command, cwd=output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
