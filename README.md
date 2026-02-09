# pycaniuse

`pycaniuse` is a Python CLI that queries [caniuse.com](https://caniuse.com) directly from the terminal.

It performs live HTML fetches and parsing, then renders feature compatibility data in a terminal-friendly format.

## What It Does

- Resolves a user query to a concrete caniuse feature slug.
- Fetches feature details from caniuse.com.
- Shows compatibility support ranges with status icons.
- Supports two display modes:
  - Default basic mode for quick output.
  - `--full` mode for an expanded view with all available browser blocks and sections.

## Requirements

- Python `>=3.10,<4.0`
- Network access to `https://caniuse.com`

## Installation

```bash
pip install pycaniuse
```

After install, the command is available as:

```bash
caniuse --help
```

## Quick Start

```bash
caniuse flexbox
caniuse "css grid"
caniuse flexbox-gap --full
```

## How Query Resolution Works

Every run has two phases:

1. Search phase
- Requests `https://caniuse.com/?search=<query>&static=1`.
- Parses candidate feature matches.
- Selection rules:
  - No matches: exits non-zero with a friendly message.
  - One match: auto-selects.
  - Exact slug match: auto-selects.
  - Multiple matches: uses interactive selection in TTY; deterministic first result in non-TTY.

2. Feature phase
- Requests `https://caniuse.com/<slug>?static=1` (with fallback when needed).
- Parses feature metadata and support ranges.
- Renders output based on selected mode.

## Output Modes

### Basic Mode (default)

Designed for quick checks:

- Feature title
- Spec URL and status (when available)
- Global usage percentages (when available)
- Description
- Browser support for:
  - Chrome
  - Edge
  - Firefox
  - Safari
  - Opera

Status icons:

- `✅` supported
- `❌` not supported
- `◐` partial support
- `﹖` unknown

### Full Mode (`--full`)

Shows an expanded interactive TUI, including:

- A feature metadata panel with usage summary.
- All browser support blocks in a horizontal support table.
- A selected-browser detail view with range-by-range status rows.
- Tabbed feature sections for:
  - Info
  - Notes (when present)
  - Resources (when present)
  - Sub-features (when present)
  - Legend
- A dedicated legend and keyboard help footer.

Controls:

- `q` / `Esc`: quit full mode
- `←` / `→` (or `h` / `l`): move selected browser
- `↑` / `↓` (or `k` / `j`): scroll selected browser range rows
- `Tab` / `[` / `]`: switch right-side detail tabs
- `PgUp` / `PgDn`: scroll tab content
- `Home` / `End`: jump to top/bottom in detail panes

In non-interactive or piped output contexts, full mode falls back to static wrapped rendering.

## Parser Model

`pycaniuse` uses resilient HTML parsing helpers and returns structured data models:

- `SearchMatch`
- `SupportRange`
- `BrowserSupportBlock`
- `FeatureBasic`
- `FeatureFull`

Primary modules:

- `caniuse/cli.py`: command orchestration
- `caniuse/http.py`: HTTP requests and error mapping
- `caniuse/parse_search.py`: search results parser
- `caniuse/parse_feature.py`: feature page parser
- `caniuse/render_basic.py`: basic mode renderer
- `caniuse/ui/select.py`: interactive selection helpers
- `caniuse/ui/fullscreen.py`: expanded full-mode renderer
- `caniuse/util/html.py`: selector/text/attribute helpers
- `caniuse/util/text.py`: formatting/parsing helpers

## Error Handling

Expected operational failures are normalized into domain exceptions and shown as clean CLI errors:

- network connectivity issues
- timeouts
- non-200 responses
- empty/invalid HTML bodies

Parsing is defensive. Missing sections do not crash the CLI; partial output is still rendered with warnings where applicable.

## Development

### Setup

```bash
uv sync --frozen
uv pip install -e .
uv run pre-commit install
```

Or use:

```bash
make install
```

### Common Commands

```bash
make check       # lockfile + full pre-commit hook suite
make test        # tox matrix (py310, py311, py312, py313)
make test-local  # run pytest + HTML coverage report in current env
make build       # build dist artifacts
```

### CI-Parity Details

`make check` runs:

- lockfile validation
- markdown/style/format checks
- `ruff`, `black`, `mypy`
- dependency and security checks (`pip-audit`, `bandit`, `deptry`)
- spelling/dead-code checks (`codespell`, `vulture`)

`make test` runs `tox` environments across supported Python versions.

## Coverage

Coverage is collected with `pytest-cov` and configured in `pyproject.toml`.

Generate local reports:

```bash
uv run python -m pytest tests --cov --cov-config=pyproject.toml --cov-report=term-missing
```

or

```bash
make test-local
```

## Docker

```bash
docker build -t pycaniuse .
docker run --rm -it pycaniuse flexbox
```

## Release Utilities

Helpful targets/scripts:

- `make version`
- `make check-version`
- `make build`
- `make check-dist`
- `make publish-test`
- `make publish`
- `make tag` (invokes `scripts/tag_release.sh`)

## Debugging

Set:

```bash
PYCANIUSE_DEBUG=1
```

This enables internal debug logging hooks in HTML utilities.

## Limitations

- No offline dataset or local cache.
- Depends on caniuse.com HTML shape.
- Runtime behavior requires network availability.

## License

MIT
