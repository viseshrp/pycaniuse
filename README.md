# pycaniuse

[![PyPI version](https://img.shields.io/pypi/v/pycaniuse.svg)](https://pypi.org/project/pycaniuse/)
[![Python versions](https://img.shields.io/pypi/pyversions/pycaniuse.svg?logo=python&logoColor=white)](https://pypi.org/project/pycaniuse/)
[![CI](https://github.com/viseshrp/pycaniuse/actions/workflows/main.yml/badge.svg)](https://github.com/viseshrp/pycaniuse/actions/workflows/main.yml)
[![Coverage](https://codecov.io/gh/viseshrp/pycaniuse/branch/main/graph/badge.svg)](https://codecov.io/gh/viseshrp/pycaniuse)
[![License: MIT](https://img.shields.io/github/license/viseshrp/pycaniuse)](https://github.com/viseshrp/pycaniuse/blob/main/LICENSE)
[![Format: Ruff](https://img.shields.io/badge/format-ruff-000000.svg)](https://docs.astral.sh/ruff/formatter/)
[![Lint: Ruff](https://img.shields.io/badge/lint-ruff-000000.svg)](https://docs.astral.sh/ruff/)
[![Typing: ty](https://img.shields.io/badge/typing-checked-blue.svg)](https://docs.astral.sh/ty/)

> Query caniuse.com from your shell.

![Demo](https://raw.githubusercontent.com/viseshrp/pycaniuse/main/demo.gif)

## 🚀 Why this project exists

I wanted a fast way to check browser compatibility without leaving the terminal.
When you are already coding in a shell, jumping to a browser for every feature
lookup adds friction. `pycaniuse` keeps this workflow simple: type a query,
get compatibility ranges immediately, and optionally open a richer interactive
full-screen view.

## 🧠 How this project works

`pycaniuse` runs in two phases:

1. Search phase
- Requests `https://caniuse.com/?search=<query>&static=1`
- Parses candidate matches from HTML
- Selection behavior:
  - No matches: exits non-zero with a friendly message
  - One match: auto-selects
  - Exact slug match: auto-selects
  - Multiple matches:
    - Interactive TTY: keyboard selector
    - Non-interactive: deterministic first match with notice

2. Feature phase
- Requests `https://caniuse.com/<slug>?static=1`
- If non-200, retries once without `static=1`
- Parses feature metadata and support ranges
- Renders:
  - Basic mode (default): compact output for major browsers
  - Full mode (`--full`): full-screen interactive TUI with all browsers and detail tabs

The parser extracts:

- feature title
- spec URL and status (when available)
- global usage percentages (supported, partial, total)
- description text
- browser support blocks and range status/timeline details
- optional notes/resources/sub-features for full mode

## 📐 Requirements

* Python `>=3.10,<4.0`
* Network access to `https://caniuse.com`

## 📦 Installation

```bash
pip install pycaniuse
```

## 🧪 Usage

```bash
$ caniuse --help
Usage: caniuse [OPTIONS] QUERY...

  Query caniuse.com from the terminal.

Options:
  --full         Enable full-screen interactive mode.
  -v, --version  Show the version and exit.
  -h, --help     Show this message and exit.
```

Examples:

```bash
caniuse flexbox
caniuse "css grid"
caniuse flexbox-gap --full
```

Basic-mode status icons:

- `✅` supported
- `❌` not supported
- `◐` partial support
- `﹖` unknown

Full-mode controls:

- `q` / `Esc`: quit
- `Left` / `Right` or `h` / `l`: move selected browser
- `Up` / `Down` or `k` / `j`: scroll selected browser ranges
- `Tab` / `Shift+Tab` or `]` / `[`: next/previous detail tab
- `PgUp` / `PgDn`: page browsers and scroll tab content
- `Home` / `End`: jump to top/bottom for active browser ranges and tab content

## 🛠️ Features

- Live caniuse.com HTML fetching and parsing (no vendored dataset)
- Two display modes:
  - Basic mode (compact output)
  - Full mode (interactive full-screen TUI)
- Resilient search parsing with primary selectors plus fallback heuristics
- Browser support ranges with status icons and note markers
- Parse warnings for partial/degraded HTML parse scenarios
- Clean, typed error handling for network/HTTP/content failures
- Defensive parser behavior to avoid hard crashes on missing optional sections

## 🧩 Project Structure

- `caniuse/cli.py`: command orchestration
- `caniuse/http.py`: HTTP fetches, retry, static fallback
- `caniuse/parse_search.py`: search page parser
- `caniuse/parse_feature.py`: feature page parser
- `caniuse/render_basic.py`: basic renderer
- `caniuse/ui/select.py`: interactive match selector
- `caniuse/ui/fullscreen.py`: full-screen renderer and key loop
- `caniuse/util/html.py`: selector/text/attribute helpers
- `caniuse/util/text.py`: formatting and parsing helpers

Core models:

- `SearchMatch`
- `SupportRange`
- `BrowserSupportBlock`
- `FeatureBasic`
- `FeatureFull`

## 🧪 Development

Setup:

```bash
uv sync --frozen
uv pip install -e .
uv run pre-commit install
```

Or:

```bash
make install
```

Common commands:

```bash
make check       # lockfile check + pre-commit hooks
make test        # tox matrix (py310-py313, excludes canary marker)
make test-local  # local pytest + HTML coverage report
make build       # build dist artifacts
```

Canary test (live caniuse.com HTML shape):

```bash
uv run pytest -m canary
```

## 🐳 Docker

```bash
docker build -t pycaniuse .
docker run --rm -it pycaniuse flexbox
```

## 🚢 Release Utilities

- `make version`
- `make check-version`
- `make build`
- `make check-dist`
- `make publish-test`
- `make publish`
- `make tag`

## 🐞 Debugging

Set:

```bash
PYCANIUSE_DEBUG=1
```

This enables debug logging hooks in HTML utility helpers.

## 🧾 Changelog

See [CHANGELOG.md](https://github.com/viseshrp/pycaniuse/blob/main/CHANGELOG.md)

## ⚠️ Limitations

- No local cache or offline dataset
- Runtime behavior depends on caniuse.com HTML structure
- Network access is required at runtime
- If caniuse.com layout changes significantly, some sections may parse partially

## 🙏 Credits

- [justhtml](https://github.com/andybalholm/justhtml), for HTML parsing
- [httpx](https://github.com/encode/httpx), for HTTP client behavior
- [Click](https://click.palletsprojects.com), for CLI ergonomics
- [Rich](https://github.com/Textualize/rich), for terminal rendering and TUI primitives

## 📄 License

MIT
