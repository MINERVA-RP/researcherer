"""Command-line entry point: launch the TUI or run a headless fetch."""

from __future__ import annotations

import argparse
import asyncio
import sys

from . import __version__
from .config import load_config


def _cmd_fetch(url: str) -> int:
    """Headless fetch (no TUI) — useful for scripts and non-graphics terminals."""
    from . import library

    cfg = load_config()
    try:
        meta = asyncio.run(library.fetch_paper(url, cfg))
    except Exception as exc:  # noqa: BLE001 - surface a clean CLI error
        print(f"error: {exc}", file=sys.stderr)
        return 1
    dest = library.paper_dir(meta, cfg)
    print(f"Fetched {meta.id_with_version}: {meta.title}")
    print(f"  -> {dest}")
    return 0


def _cmd_doctor() -> int:
    """Report this terminal's image capabilities (run it in your real terminal)."""
    from .render import active_renderer_name, prime_terminal_detection

    prime_terminal_detection()
    renderer = active_renderer_name()
    try:
        from textual_image._terminal import get_cell_size

        cell = get_cell_size()
        cell_str = f"{cell.width}x{cell.height} px"
    except Exception as exc:  # noqa: BLE001
        cell_str = f"unknown ({exc})"

    crisp = renderer in ("sixel", "tgp")
    print(f"Active image renderer : {renderer}")
    print(f"Terminal cell size    : {cell_str}")
    print(f"Crisp page images     : {'yes' if crisp else 'no'}")
    if not crisp:
        print(
            "\nThis terminal has no true graphics protocol, so image mode uses\n"
            "blocky character cells. For sharp page images, use one of:\n"
            "  • Kitty            (Terminal Graphics Protocol)\n"
            "  • iTerm2 / WezTerm (Sixel)\n"
            "  • Ghostty, foot, contour (graphics protocols)\n"
            "Otherwise, read in text mode (press 't' in the viewer)."
        )
    return 0


def _cmd_tui() -> int:
    # Probe the terminal's image capabilities while we still own stdin —
    # textual-image cannot do this once Textual's input loop starts.
    from .render import prime_terminal_detection

    prime_terminal_detection()

    from .tui.app import ResearchererApp

    ResearchererApp(load_config()).run()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="researcherer",
        description="Fetch and read arXiv papers in your terminal.",
    )
    parser.add_argument("--version", action="version", version=f"researcherer {__version__}")
    sub = parser.add_subparsers(dest="command")

    fetch = sub.add_parser("fetch", help="Download a paper by arXiv URL/ID (no TUI).")
    fetch.add_argument("url", help="arXiv URL or ID, e.g. https://arxiv.org/abs/1706.03762")

    sub.add_parser("doctor", help="Report this terminal's image capabilities.")

    args = parser.parse_args(argv)

    if args.command == "fetch":
        return _cmd_fetch(args.url)
    if args.command == "doctor":
        return _cmd_doctor()
    return _cmd_tui()


if __name__ == "__main__":
    raise SystemExit(main())
