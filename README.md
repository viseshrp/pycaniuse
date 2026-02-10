# pycaniuse

`pycaniuse` is a Python CLI for querying [caniuse.com](https://caniuse.com) from the terminal.
[![PyPI version](https://img.shields.io/pypi/v/pycaniuse.svg)](https://pypi.org/project/pycaniuse/)
[![Python versions](https://img.shields.io/pypi/pyversions/pycaniuse.svg?logo=python&logoColor=white)](https://pypi.org/project/pycaniuse/)
[![CI](https://github.com/viseshrp/pycaniuse/actions/workflows/main.yml/badge.svg)](https://github.com/viseshrp/pycaniuse/actions/workflows/main.yml)
[![Coverage](https://codecov.io/gh/viseshrp/pycaniuse/branch/main/graph/badge.svg)](https://codecov.io/gh/viseshrp/pycaniuse)
[![License: MIT](https://img.shields.io/github/license/viseshrp/pycaniuse)](https://github.com/viseshrp/pycaniuse/blob/main/LICENSE)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://black.readthedocs.io/en/stable/)
[![Lint: Ruff](https://img.shields.io/badge/lint-ruff-000000.svg)](https://docs.astral.sh/ruff/)
[![Typing: ty](https://img.shields.io/badge/typing-checked-blue.svg)](https://docs.astral.sh/ty/)

It performs live HTML fetches and parsing, then renders compatibility data in either a quick basic view or an interactive full-screen view.

## Features

- Resolves a text query to a feature slug.
- Fetches live feature data from caniuse.com.
- Renders browser support ranges with status icons.
- Provides two display modes:
  - Basic mode (default): compact output with major browsers.
  - Full mode (`--full`): full-screen TUI with all browsers and tabbed sections.

## Requirements

- Python `>=3.10,<4.0`
- Network access to `https://caniuse.com`

## Installation

```bash
pip install pycaniuse
```

Verify install:

```bash
caniuse --help
```

## Quick Start

```bash
caniuse flexbox
caniuse "css grid"
caniuse flexbox-gap --full
```

## CLI Flow

Each command run has two phases.

1. Search phase
- Requests `https://caniuse.com/?search=<query>&static=1`.
- Parses matches from the returned HTML.
- Selection behavior:
  - No matches: exits non-zero with a friendly message.
  - One match: auto-selects.
  - Exact slug match: auto-selects.
  - Multiple matches:
    - Interactive TTY: opens keyboard selector.
    - Non-interactive: prints a notice and deterministically picks the first match.

2. Feature phase
- Requests `https://caniuse.com/<slug>?static=1`.
- If that response is non-200, retries once without `static=1`.
- Parses feature metadata and support ranges.
- Renders basic output or full mode UI.

## Output Modes

### Basic Mode (default)

Shows:

- Feature title
- Spec URL and spec status (when present)
- Global usage percentages (supported, partial, total when present)
- Description
- Support ranges for:
  - Chrome
  - Edge
  - Firefox
  - Safari
  - Opera
- Note marker hints derived from support classes (for example, `See notes: 1`)
- Hint to run `--full`

Status icons:

- `✅` supported
- `❌` not supported
- `◐` partial support
- `﹖` unknown

### Full Mode (`--full`)

- Uses a full-screen keyboard-driven TUI when stdin/stdout support it.
- Falls back to static wrapped output when interactive TUI support is unavailable.

Current full-screen layout:

- Feature heading panel (title, spec, usage, description preview)
- Browser support table with horizontal browser tabs
- Feature detail tabs (`Info` always, then parsed tabs like `Notes`, `Resources`, `Sub-features`, plus `Legend`)
- Footer with controls and legend

Controls:

- `q` / `Esc`: quit
- `Left` / `Right` or `h` / `l`: move selected browser
- `Up` / `Down` or `k` / `j`: scroll ranges for selected browser
- `Tab` / `Shift+Tab` or `]` / `[`: next/previous detail tab
- `PgUp` / `PgDn`: page browsers and scroll tab content
- `Home` / `End`: jump to top/bottom for active browser ranges and tab content

## Data Model

Core models in `caniuse/model.py`:

- `SearchMatch`
- `SupportRange`
- `BrowserSupportBlock`
- `FeatureBasic`
- `FeatureFull`

`FeatureBasic` and `FeatureFull` include `parse_warnings` for partial parse cases.

## Key Modules

- `caniuse/cli.py`: CLI orchestration
- `caniuse/http.py`: HTTP fetches, retries, and fallback behavior
- `caniuse/parse_search.py`: search HTML parsing
- `caniuse/parse_feature.py`: feature HTML parsing
- `caniuse/render_basic.py`: basic output renderer
- `caniuse/ui/select.py`: interactive match selection
- `caniuse/ui/fullscreen.py`: full-screen UI and static full fallback
- `caniuse/util/html.py`: HTML helper utilities
- `caniuse/util/text.py`: text formatting and parsing helpers

## Error Handling

Expected operational failures are normalized into domain exceptions and surfaced as clean CLI errors.

Examples:

- network connectivity issues
- request timeout
- non-200 responses
- empty HTML bodies

Parsing is defensive. If browser support parsing fails, CLI output continues with:

`Some sections could not be parsed (site layout may have changed).`

## Development

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

## Docker

```bash
docker build -t pycaniuse .
docker run --rm -it pycaniuse flexbox
```

## Release Utilities

- `make version`
- `make check-version`
- `make build`
- `make check-dist`
- `make publish-test`
- `make publish`
- `make tag`

## Debugging

Set:

```bash
PYCANIUSE_DEBUG=1
```

This enables debug logging hooks in HTML utility helpers.

## Limitations

- No local cache or offline dataset.
- Behavior depends on caniuse.com HTML structure.
- Network access is required at runtime.

## License

MIT
