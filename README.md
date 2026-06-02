# researcherer

A terminal UI (TUI) for fetching and reading **arXiv** papers as PDFs, built with
[Textual](https://textual.textualize.io/).

Give it an arXiv URL and it downloads the paper into a local library folder named by
its arXiv ID, then lets you browse your library and read papers right in the terminal —
with **real rendered page images** where your terminal supports them (Kitty / iTerm2 /
Sixel) and a crisp **text fallback** everywhere else.

## Features

- **Fetch by URL** — paste any arXiv URL (`/abs/`, `/pdf/`, versioned IDs, old-style
  `math/0309136`) and the PDF + metadata are saved under `<library>/<arxiv-id>/`.
- **Library browser** — a sortable table of every paper you've fetched.
- **PDF viewer** — page navigation, scroll, zoom (DPI), and image ↔ text toggle.
- **Full-text search** — find text inside a PDF and jump between matches.

## Requirements

- **Python ≥ 3.12** (the image-rendering and PDF libraries do not support 3.9).
  Do **not** use the macOS system `python3` (3.9). Use [`uv`](https://docs.astral.sh/uv/)
  or a 3.12+ interpreter.
- For true page images: a terminal with a graphics protocol — **Kitty**, **WezTerm**,
  **iTerm2**, or any **Sixel**-capable terminal. Other terminals fall back to
  unicode-block images or text mode.

## Install & run (with uv)

```bash
uv sync                 # creates .venv with Python 3.13 and installs deps
uv run researcherer     # launch the TUI
```

Or with a manual virtualenv:

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e .
researcherer
```

## Usage

### In the TUI

- **Library screen**
  - `f` — fetch a paper (paste an arXiv URL)
  - `enter` — open the selected paper
  - `r` — refresh, `d` — delete, `/` — filter by title, `q` — quit
- **Viewer screen**
  - `→` / `space` / `pgdn` — next page, `←` / `pgup` — previous page
  - `↑` / `↓` — scroll within the page
  - `g` / `G` — first / last page
  - `+` / `-` — zoom in / out (render DPI)
  - `t` — toggle image ↔ text mode
  - `/` — search, `n` / `N` — next / previous match
  - `escape` — back to the library

### Headless fetch (no TUI)

```bash
uv run researcherer fetch https://arxiv.org/abs/1706.03762
```

Downloads the paper into your library and prints the destination — handy for scripts
and for verifying the pipeline without a graphics terminal.

## Blurry / pixelated page images?

Crisp page images require a terminal with a real **graphics protocol**. Without one,
`textual-image` falls back to blocky character-cell rendering — which looks pixelated no
matter the resolution. Check what your terminal supports:

```bash
uv run researcherer doctor
```

- **`Crisp page images : yes`** (renderer `sixel` or `tgp`) — you'll get sharp pages.
  If they still look soft, zoom with `+` in the viewer or raise `default_dpi` in config.
- **`Crisp page images : no`** (renderer `halfcell`/`unicode`) — your terminal has no
  graphics protocol. Either read in **text mode** (press `t`), or switch to a terminal
  that supports one:
  - **Kitty** — Terminal Graphics Protocol
  - **iTerm2** / **WezTerm** — Sixel
  - **Ghostty**, **foot**, **contour** — graphics protocols

  macOS **Terminal.app** supports *neither* and will always render blocky images.

The viewer's status bar shows the active renderer (e.g. `… | 200 dpi | sixel | …`) and a
banner warns when image mode can only render low-res on your terminal.

## Configuration

Config is read from the first of:

1. `$XDG_CONFIG_HOME/researcherer/config.toml`
2. `~/.config/researcherer/config.toml`
3. the platform default config dir

```toml
library_dir = "~/researcherer/papers"   # where papers are stored
default_dpi = 150                         # page render resolution
image_mode = "auto"                       # auto | image | text
user_agent_contact = ""                   # optional email/URL added to the User-Agent
```

If no config file exists, defaults are used and a template is written to
`~/.config/researcherer/config.toml`.

## Library layout

```
~/researcherer/papers/
└── 2301.12345/
    ├── 2301.12345.pdf
    └── metadata.json
```

Old-style arXiv IDs (`math/0309136`) use `_` in the folder name (`math_0309136`); the
canonical ID is preserved in `metadata.json`.

## arXiv etiquette

`researcherer` sets a descriptive `User-Agent` and throttles to **≤ 1 request / 3 s**
against the arXiv API, per the
[arXiv API Terms of Use](https://info.arxiv.org/help/api/tou.html). Downloaded PDFs are a
local personal cache — do not re-serve them.

## License

[AGPL-3.0-or-later](LICENSE). This project depends on **PyMuPDF**, which is licensed
AGPL-3.0; `researcherer` adopts the same license to stay compatible. If you need a
permissive license, the PDF engine would have to be swapped for `pypdf` + Poppler (which
loses positional in-page search).

## Development

```bash
uv sync --extra dev
uv run pytest
```
