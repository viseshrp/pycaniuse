# pycaniuse

`pycaniuse` provides a fast terminal CLI (`caniuse`) for querying [caniuse.com](https://caniuse.com) via HTML scraping.

## Requirements

- Python 3.10+
- Network access to `https://caniuse.com`

## Install

```bash
pip install pycaniuse
```

## Usage

```bash
caniuse flexbox
caniuse "css grid"
caniuse flexbox-gap --full
```

## Flow

- Phase A: fetch search results, parse matches, resolve selection.
- Phase B: fetch feature page, parse details, render basic or full mode.

## Full Mode Keybindings

- `Left`/`Right`: switch tabs
- `1-9`: jump to tab index
- `Up`/`Down`: scroll tab content
- `PageUp`/`PageDown`: faster scroll
- `Home`/`End`: top/bottom
- `q` or `Esc`: quit

## Debugging

Set `PYCANIUSE_DEBUG=1` to print parser diagnostics to stderr.

## Limitations

- The parser depends on caniuse HTML structure.
- No offline support or persistent cache.
- No disk writes for runtime data.

## Docker

```bash
docker build -t pycaniuse .
docker run --rm -it pycaniuse flexbox
```

## License

MIT
