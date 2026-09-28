"""Command-line entry point for cv-dataset-toolkit."""

import argparse
import sys

from cv_dataset_toolkit import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cv-dataset-toolkit",
        description="Scan an image dataset folder and export a metadata manifest.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan", help="Scan a dataset folder (placeholder, Day 2+).")
    scan_parser.add_argument("path", help="Path to the dataset root folder.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        print(f"[placeholder] would scan: {args.path}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
