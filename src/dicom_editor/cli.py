"""Command line helpers for working with the simplified DICOM toolkit."""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from . import AVAILABLE_PROFILES, get_profile, read_file, write_file
from .profiles import SaveProfile


def _list_profiles() -> None:
    for name, profile in AVAILABLE_PROFILES.items():
        print(f"{name:>16} — {profile.description}")


def _apply_window(dataset, window: Optional[str]) -> None:
    if not window:
        return
    try:
        centre, width = map(float, window.split(","))
    except Exception as exc:  # pragma: no cover - input parsing guard
        raise SystemExit(f"invalid window specification: {window}") from exc
    dataset.pixel_array.apply_window(centre, width)


def cmd_show(args: argparse.Namespace) -> None:
    dataset = read_file(args.path)
    if args.window:
        _apply_window(dataset, args.window)
    dataset.pixel_array.ensure_single_sample()
    dataset.pixel_array.rescale_to_8bit()
    print(dataset.pixel_array.ascii_preview(max_width=args.width))


def cmd_save(args: argparse.Namespace) -> None:
    dataset = read_file(args.source)
    _apply_window(dataset, args.window)
    profile: SaveProfile = get_profile(args.profile)
    write_file(dataset, args.destination, profile)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal DICOM viewer/editor")
    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser("show", help="print an ASCII representation of the image")
    show.add_argument("path", help="input DICOM file")
    show.add_argument("--width", type=int, default=60, help="maximum output width in characters")
    show.add_argument(
        "--window",
        metavar="CENTRE,WIDTH",
        help="optional window/level specification (e.g. 40,400)",
    )
    show.set_defaults(func=cmd_show)

    save = sub.add_parser("save", help="save the dataset using one of the predefined profiles")
    save.add_argument("source", help="source DICOM file")
    save.add_argument("destination", help="target DICOM file")
    save.add_argument("--profile", default="ct-explicit-8bit", choices=AVAILABLE_PROFILES.keys())
    save.add_argument(
        "--window",
        metavar="CENTRE,WIDTH",
        help="optional window/level specification before saving",
    )
    save.set_defaults(func=cmd_save)

    profiles = sub.add_parser("profiles", help="list available save profiles")
    profiles.set_defaults(func=lambda args: _list_profiles())

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution entry
    sys.exit(main())
