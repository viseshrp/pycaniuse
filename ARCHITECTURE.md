# Architecture Document: pycaniuse

## 1. Overview

`pycaniuse` is a terminal CLI application that queries browser feature compatibility data from caniuse.com via HTML scraping. The application operates in two modes:

- **Basic mode** (default): Lightweight, quick output showing core feature information with 5 major browsers
- **Full mode** (`--full`): Full-screen interactive UI with all browsers and tabbed sections

### Core Constraints

| Constraint | Description |
|------------|-------------|
| **HTML-only** | All data is scraped from caniuse.com HTML pages; no `data.json` usage |
| **No disk writes** | No cache files, no vendored data, no persistent storage |
| **No offline support** | Graceful error handling only; no offline data |
| **Keyboard-first** | Interactive UI is keyboard-driven; mouse support is optional |

---

## 2. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER TERMINAL                                   │
│                                                                             │
│  $ caniuse <query> [--full]                                                 │
└─────────────────────────────────────────────────────────┬───────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               cli.py                                         │
│                          (CLI Entry Point)                                   │
│  • Parse arguments (query, --full)                                          │
│  • Orchestrate 2-phase flow                                                  │
│  • Exit code management                                                      │
└────────────┬──────────────────────────────────────┬─────────────────────────┘
             │                                      │
             │ Phase A: Search                      │ Phase B: Feature Detail
             ▼                                      ▼
┌─────────────────────────┐          ┌─────────────────────────────────────────┐
│       http.py           │          │                                         │
│   (HTTP Client)         │◀─────────│    Network Layer (fetch_html)           │
│  • fetch search page    │          │                                         │
│  • fetch feature page   │          └─────────────────────────────────────────┘
└──────────┬──────────────┘
           │ HTML
           ▼
┌─────────────────────────┐          ┌─────────────────────────────────────────┐
│   parse_search.py       │          │       parse_feature.py                   │
│   (Search Parser)       │          │       (Feature Parser)                   │
│  • Strategy S1: search  │          │  • parse_feature_basic()                 │
│    results page         │          │  • parse_feature_full()                  │
│  • Strategy S2: fallback│          │  • Uses util_html.py helpers             │
└──────────┬──────────────┘          └──────────────────┬──────────────────────┘
           │ list[SearchMatch]                          │
           ▼                                            │ FeatureBasic / FeatureFull
┌─────────────────────────┐                             ▼
│    ui_select.py         │          ┌─────────────────────────────────────────┐
│   (Selection UI)        │          │       RENDERING LAYER                    │
│  • Rich bullet list     │          │                                         │
│  • Arrow navigation     │          │  ┌───────────────┐  ┌─────────────────┐ │
│  • Enter/q/Esc handling │          │  │render_basic.py│  │ ui_fullscreen.py│ │
└──────────┬──────────────┘          │  │ (basic mode)  │  │  (--full mode)  │ │
           │ selected slug           │  └───────────────┘  └─────────────────┘ │
           ▼                         └─────────────────────────────────────────┘
     Phase B fetch...

                         ┌─────────────────────────────────────────┐
                         │         UTILITY LAYER                    │
                         │  ┌─────────────┐    ┌──────────────┐    │
                         │  │ util_text.py│    │ util_html.py │    │
                         │  │ (wrapping,  │    │ (selectors,  │    │
                         │  │  parsing)   │    │  debug hooks)│    │
                         │  └─────────────┘    └──────────────┘    │
                         └─────────────────────────────────────────┘
```

---

## 3. Module Boundaries and Responsibilities

### 3.1 Package Structure (aligned with Implementation Plan Phase 0)

```
caniuse/
├── __init__.py
├── cli.py              # CLI entry point
├── http.py             # HTTP client
├── model.py            # Data models
├── parse_search.py     # Search results parser
├── parse_feature.py    # Feature detail parser
├── render_basic.py     # Basic mode rendering
├── ui/
│   ├── __init__.py
│   ├── select.py       # Selection UI
│   └── fullscreen.py   # Full-screen interactive UI
└── util/
    ├── __init__.py
    ├── text.py         # Text utilities (wrapping, percent parsing)
    └── html.py         # HTML utilities (selector helpers, debug hooks)
```

### 3.2 Module Map

| Module | Responsibility | Implementation Phase |
|--------|---------------|---------------------|
| `cli.py` | CLI entry point, argument parsing, orchestration | Phase 0, 2, 4, 5 |
| `http.py` | HTTP fetching with error handling | Phase 1 |
| `parse_search.py` | Parse search results HTML (S1/S2 strategies) | Phase 2 |
| `parse_feature.py` | Parse feature detail HTML (basic + full) | Phase 3, 5 |
| `model.py` | Data model definitions | Phase 3 |
| `ui/select.py` | Interactive search result selector | Phase 2 |
| `render_basic.py` | Basic mode rendering | Phase 4 |
| `ui/fullscreen.py` | Full-screen interactive UI | Phase 5 |
| `util/text.py` | Text wrapping, percent parsing, whitespace normalization | Phase 3 |
| `util/html.py` | Selector helpers, debug hooks | Phase 3, 6 |

### 3.3 Detailed Module Responsibilities

#### `cli.py` — CLI Entry Point

```
Responsibilities:
├── Parse command-line arguments
│   ├── <query>: free text search term
│   └── --full: enable full-screen interactive mode
├── Orchestrate the 2-phase flow
│   ├── Phase A: Search → Selection
│   └── Phase B: Feature Fetch → Render
├── Implement exact slug shortcut bypass
├── Manage exit codes
│   ├── 0: success
│   └── non-zero: no matches or error
└── Route to appropriate renderer based on mode
```

#### `http.py` — HTTP Client

```
Responsibilities:
├── fetch_html(url, params=None, timeout=10) → str
├── Set consistent User-Agent ("pycaniuse/<version>")
├── Handle errors:
│   ├── Connection error → typed exception
│   ├── Timeout → typed exception
│   └── Non-200 response → typed exception
├── Retry policy: 0 retries default (determinism)
│   └── Optional 1 retry for transient connection errors
└── Fallback: if ?static=1 breaks, retry without it
```

**URLs Used:**
- Search: `https://caniuse.com/?search=<query>&static=1`
- Feature: `https://caniuse.com/<slug>?static=1`

#### `parse_search.py` — Search Result Parser

```
Responsibilities:
├── parse_search_results(html) → list[SearchMatch]
├── Two-strategy approach:
│   ├── Strategy S1: Search results page structure (primary)
│   └── Strategy S2: Fallback heuristic for feature anchors
├── S2 heuristic rules:
│   ├── href starts with "/" (not "/ciu/", "/issue-list", etc.)
│   ├── href does not contain "?"
│   ├── Link text length >= 3
│   └── Slug matches [a-z0-9-] pattern
├── De-duplicate by slug while preserving order
└── Ignore external URLs and nav links
```

#### `parse_feature.py` — Feature Parser

```
Responsibilities:
├── parse_feature_basic(html, slug) → FeatureBasic
│   ├── Title (.feature-title)
│   ├── Spec link + status (a.specification)
│   ├── Usage stats (li.support-stats[data-usage-id="region.global"])
│   ├── Description (.feature-description)
│   └── Browser blocks (filtered to 5: chrome, edge, firefox, safari, opera)
│
├── parse_feature_full(html, slug) → FeatureFull
│   ├── All fields from FeatureBasic
│   ├── Notes (div.single-page__notes)
│   ├── Resources (dl.single-feat-resources → dd > a list)
│   ├── Sub-features (dt "Sub-features:" → dd > a entries)
│   ├── ALL browser blocks (no filtering)
│   └── Build tabs dict for available sections
│
└── Graceful handling of missing fields
```

#### `model.py` — Data Models

```
Data Classes:
├── SearchMatch
│   ├── slug: str
│   ├── title: str
│   └── href: str
│
├── SupportRange
│   ├── range_text: str (e.g., "4 - 20", "144", "all")
│   ├── status: Literal["y", "n", "a", "u"]
│   ├── is_past: bool
│   ├── is_current: bool
│   ├── is_future: bool
│   ├── title_attr: str
│   └── raw_classes: tuple[str, ...]
│
├── BrowserSupportBlock
│   ├── browser_name: str
│   ├── browser_key: str
│   └── ranges: list[SupportRange]
│
├── FeatureBasic
│   ├── slug: str
│   ├── title: str
│   ├── spec_url: Optional[str]
│   ├── spec_status: Optional[str]
│   ├── usage_supported: Optional[float]
│   ├── usage_partial: Optional[float]
│   ├── usage_total: Optional[float]
│   ├── description_text: str
│   └── browser_blocks: list[BrowserSupportBlock]
│
└── FeatureFull (extends FeatureBasic)
    ├── notes_text: Optional[str]
    ├── resources: list[tuple[str, str]]  # (label, url)
    ├── subfeatures: list[tuple[str, str]]  # (label, url)
    └── tabs: dict[str, str]  # rendered text per available tab
```

#### `ui/select.py` — Selection UI

```
Responsibilities:
├── Display Rich bullet list of search results
├── Handle keyboard navigation
│   ├── Up/Down arrows: navigate list
│   ├── Enter: select item
│   └── q/Esc: cancel (exit non-zero)
└── Return selected slug or None if cancelled
```

#### `render_basic.py` — Basic Mode Renderer

```
Responsibilities:
├── render_basic(feature: FeatureBasic) → Rich Renderable
├── Display:
│   ├── Title
│   ├── Spec link + status (hide if missing)
│   ├── Usage summary (hide if missing)
│   ├── Description
│   └── 5-browser support blocks
├── Status icons: ✅ y, ❌ n, ◐ a, ﹖ u
└── Hint line: "Run with --full to see all browsers + Notes/Resources/Sub-features."
```

#### `ui/fullscreen.py` — Full-Screen Interactive UI

```
Responsibilities:
├── Full-screen Rich application loop
├── Layout management (header, support, tabs, content)
├── State management (see §7 for details)
├── Keyboard input handling
├── Terminal size validation
│   └── Show "Terminal too small; resize" if needed
└── Render all browsers with dense layout
```

#### `util/text.py` — Text Utilities

```
Responsibilities:
├── Text wrapping for terminal width
├── Whitespace normalization
├── parse_percent("96.79%") → float
│   └── Handle locale variance (comma as decimal: "96,79%")
└── String stripping and cleaning
```

#### `util/html.py` — HTML Utilities

```
Responsibilities:
├── Selector helper functions:
│   ├── first(doc, selector) → node | None
│   ├── all(doc, selector) → list[nodes]
│   ├── text(node) → str (normalized)
│   └── attr(node, name) → str | None
├── safe_join_url(base, href) → absolute URL
└── Debug hooks (PYCANIUSE_DEBUG=1):
    ├── Print matched selectors
    ├── Dump available browser keys
    └── Show range counts per browser
```

---

## 4. Data Flow

### 4.1 Phase A: Search → Selection

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Phase A: Search and Selection Flow                                           │
└─────────────────────────────────────────────────────────────────────────────┘

  User Input
      │
      │ <query>
      ▼
┌───────────┐
│  cli.py   │
│           │  1. Build search URL
│           │     https://caniuse.com/?search=<query>&static=1
└─────┬─────┘
      │
      ▼
┌───────────┐
│  http.py  │  2. HTTP GET request
│           │
│           │  3. Handle network errors
│           │     → Exit non-zero with friendly message
└─────┬─────┘
      │ HTML string
      ▼
┌────────────────┐
│ parse_search   │  4. Parse search results
│    .py         │     → list[SearchMatch]
└─────┬──────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│              BRANCHING LOGIC                         │
│                                                     │
│  ┌─────────────────┐                                │
│  │ 0 results?      │──YES──▶ Show "No matches"      │
│  │                 │         Exit non-zero          │
│  └────────┬────────┘                                │
│           │ NO                                      │
│           ▼                                         │
│  ┌─────────────────┐                                │
│  │ Exact slug?     │──YES──▶ Auto-select (bypass)   │
│  │ query == slug   │                                │
│  └────────┬────────┘                                │
│           │ NO                                      │
│           ▼                                         │
│  ┌─────────────────┐                                │
│  │ 1 result?       │──YES──▶ Auto-select            │
│  └────────┬────────┘                                │
│           │ NO                                      │
│           ▼                                         │
│  ┌─────────────────┐                                │
│  │ N results       │──────▶ Show ui_select          │
│  │                 │        User picks one          │
│  └─────────────────┘        or cancels (q/Esc)     │
│                                                     │
└─────────────────────────────────────────────────────┘
      │
      │ selected slug
      ▼
   Phase B...
```

### 4.2 Phase B: Feature Fetch → Render

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Phase B: Feature Detail Flow                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

  Selected slug
      │
      ▼
┌───────────┐
│  http.py  │  1. Fetch feature page
│           │     https://caniuse.com/<slug>?static=1
└─────┬─────┘
      │ HTML string
      ▼
┌──────────────────────────────────────────────────────┐
│               MODE BRANCHING                          │
│                                                      │
│  ┌───────────────────────────────────────────────┐  │
│  │            BASIC MODE (default)                │  │
│  │  ┌──────────────────┐                         │  │
│  │  │ parse_feature.py │                         │  │
│  │  │ parse_feature_   │  → FeatureBasic         │  │
│  │  │   basic()        │    (5 browsers only)    │  │
│  │  └────────┬─────────┘                         │  │
│  │           │                                   │  │
│  │           ▼                                   │  │
│  │  ┌──────────────────┐                         │  │
│  │  │   ui_basic.py    │                         │  │
│  │  │ render_basic()   │  → Print to terminal    │  │
│  │  │                  │    Exit 0               │  │
│  │  └──────────────────┘                         │  │
│  └───────────────────────────────────────────────┘  │
│                                                      │
│  ┌───────────────────────────────────────────────┐  │
│  │            FULL MODE (--full)                  │  │
│  │  ┌──────────────────┐                         │  │
│  │  │ parse_feature.py │                         │  │
│  │  │ parse_feature_   │  → FeatureFull          │  │
│  │  │   full()         │    (all browsers,       │  │
│  │  │                  │     notes, resources,   │  │
│  │  │                  │     sub-features)       │  │
│  │  └────────┬─────────┘                         │  │
│  │           │                                   │  │
│  │           ▼                                   │  │
│  │  ┌──────────────────┐                         │  │
│  │  │ ui_fullscreen.py │                         │  │
│  │  │ Full-screen app  │  → Interactive UI loop  │  │
│  │  │   loop           │    q/Esc to exit        │  │
│  │  └──────────────────┘                         │  │
│  └───────────────────────────────────────────────┘  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 5. HTML Parsing Strategy

### 5.1 Parser: justhtml

The application uses `justhtml` for all HTML parsing. This library provides:
- HTML5-compliant parsing
- CSS selector queries
- Lightweight and fast

### 5.2 Selector Strategy: Primary + Fallback

Each field extraction follows a "best effort" strategy:

```
For each field:
├── 1. Try PRIMARY selector
│      ↓ success → extract value
│      ↓ failure → continue
├── 2. Try FALLBACK selector(s)
│      ↓ success → extract value
│      ↓ failure → continue
└── 3. Return None / default
       → No crash
       → Populate partial data
```

### 5.3 Selector Map

| Field | Primary Selector | Notes |
|-------|-----------------|-------|
| **Title** | `.feature-title` | Fallback: `<title>` split on " \| Can I use" |
| **Spec URL** | `a.specification` | `href` attribute, may be None |
| **Spec Status** | `a.specification` | Last token after "-" (e.g., "- CR" → "CR"), fallback to class |
| **Global Usage** | `li.support-stats[data-usage-id="region.global"]` | `.support`, `.partial`, `.total` spans |
| **Description** | `.feature-description` | Text content |
| **Browser Support** | `.support-container .support-list` | Multiple blocks |
| **Browser Heading** | `h4.browser-heading` | Class includes `browser--<key>` |
| **Support Ranges** | `ol > li.stat-cell` | Within each support-list |
| **Notes** | `div.single-page__notes` | Full mode only |
| **Resources** | `dl.single-feat-resources` | `dd > a` elements |
| **Sub-features** | `dt` containing "Sub-features:" | Following `dd > a` entries |

### 5.4 Browser Support Block Extraction

```
For each div.support-list:
├── Extract browser heading (h4.browser-heading)
│   ├── browser_name: text content
│   └── browser_key: from class "browser--<key>"
│
└── Extract ranges (ol > li.stat-cell)
    For each li:
    ├── range_text: visible text (e.g., "4 - 20", "144", "all")
    ├── status: from class
    │   ├── "y" → supported
    │   ├── "n" → not supported
    │   ├── "a" → partial
    │   └── "u" → unknown
    ├── timeline: from class
    │   ├── is_past
    │   ├── is_current
    │   └── is_future
    ├── title_attr: title attribute (verbatim)
    └── raw_classes: preserve all classes for note markers
```

### 5.5 Browser Filtering

| Mode | Browsers Shown |
|------|----------------|
| **Basic** | `chrome`, `edge`, `firefox`, `safari`, `opera` (5 only) |
| **Full** | ALL browsers in page order |

---

## 6. UI Architecture

### 6.1 Basic Mode (`ui_basic.py`)

**Rendering Strategy:** Simple Rich console output (no interactive loop)

```
┌─────────────────────────────────────────────────────────────────┐
│ BASIC MODE OUTPUT LAYOUT                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Title: CSS Flexible Box Layout Module                      │ │
│  │ Spec: https://...  [CR]                                    │ │
│  │ Usage: ✅ 95.5%  ◐ 1.2%  Total: 96.79%                     │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Description:                                                   │
│  Method of positioning elements in horizontal or vertical...   │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ BROWSER SUPPORT (5 browsers)                               │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │ Chrome                                                     │ │
│  │   29+: ✅ Supported                                        │ │
│  │   21-28: ◐ Partial                                         │ │
│  │   4-20: ❌ Not supported                                   │ │
│  │                                                            │ │
│  │ Firefox                                                    │ │
│  │   ...                                                      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  💡 Run with --full to see all browsers + Notes/Resources/...  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Status Icons:**

| Status | Icon | Meaning |
|--------|------|---------|
| `y` | ✅ | Supported |
| `n` | ❌ | Not supported |
| `a` | ◐ | Partial support |
| `u` | ﹖ | Unknown |

---

### 6.2 Full-Screen Interactive Mode (`ui_fullscreen.py`)

**Rendering Strategy:** Rich application loop (NOT console.pager)

#### 6.2.1 Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ FULL-SCREEN UI LAYOUT                                                        │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ HEADER REGION (fixed)                                                    │ │
│ │ Title | Spec URL [Status] | Usage: ✅ X% ◐ Y% Total: Z%                 │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ SUPPORT REGION (scrollable or fixed)                                     │ │
│ │ All browsers with support data in dense multi-column layout             │ │
│ │ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │ │
│ │ │ Chrome      │ │ Firefox     │ │ Safari      │ │ Edge        │        │ │
│ │ │ 29+: ✅     │ │ 28+: ✅     │ │ 9+: ✅      │ │ 12+: ✅     │        │ │
│ │ │ 21-28: ◐   │ │ 22-27: ◐   │ │ ...         │ │ ...         │        │ │
│ │ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘        │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ TABS ROW                                                                 │ │
│ │ [ Notes ]  [ Resources ]  [ Sub-features ]  ...                         │ │
│ │  ▲ selected (highlighted)                                               │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ CONTENT PANE (scrollable)                                                │ │
│ │ Content of selected tab...                                              │ │
│ │                                                                         │ │
│ │ (scrollable with Up/Down/PageUp/PageDown/Home/End)                      │ │
│ │                                                                         │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ FOOTER (optional)                                                        │ │
│ │ ←/→: switch tabs | ↑/↓: scroll | q: quit                                │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 6.2.2 Tab Configuration

| Tab | Source Selector | Presence |
|-----|----------------|----------|
| **Notes** | `div.single-page__notes` | Optional (default selected if present) |
| **Resources** | `dl.single-feat-resources` | Optional |
| **Sub-features** | `dt "Sub-features:"` → following `dd > a` | Optional |
| **Known issues** | Discoverable | Optional/extensible |
| **Feedback** | Discoverable | Optional/extensible |

**Default Tab Selection:** Notes (if present), otherwise first available tab.

---

## 7. State Management (Full-Screen Mode)

### 7.1 State Model

```python
# Conceptual state structure (not actual code)

class FullScreenState:
    # Tab navigation
    selected_tab_idx: int        # Current tab (0-indexed)
    tabs: list[str]              # Available tab names

    # Content scrolling
    scroll_offset: int           # Tab content scroll position
    support_scroll_offset: int   # Support region scroll (if long)

    # Focus control (optional)
    mode_focus: str              # "support" or "tab" (if both scroll)

    # Pre-computed content
    tab_lines: dict[str, list[str]]  # Pre-wrapped lines per tab

    # Feature data
    feature: FeatureFull         # Parsed feature data
```

### 7.2 State Transitions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STATE MACHINE                                                                │
└─────────────────────────────────────────────────────────────────────────────┘

              ┌──────────────────────────────────────┐
              │         INITIAL STATE                │
              │  selected_tab_idx = 0                │
              │  scroll_offset = 0                   │
              │  support_scroll_offset = 0           │
              │  tabs = [Notes, Resources, ...]      │
              └────────────────┬─────────────────────┘
                               │
                               ▼
              ┌──────────────────────────────────────┐
              │           RUNNING                    │◀──────────┐
              │  Check terminal size                 │           │
              │  Render current state                │           │
              │  Wait for key input                  │           │
              └────────────────┬─────────────────────┘           │
                               │                                 │
                               ▼                                 │
              ┌──────────────────────────────────────┐           │
              │         INPUT HANDLER                 │           │
              ├──────────────────────────────────────┤           │
              │ Left Arrow:                          │           │
              │   selected_tab_idx = max(0, i-1)     │───────────┤
              │   scroll_offset = 0 (reset)          │           │
              │                                      │           │
              │ Right Arrow:                         │           │
              │   selected_tab_idx = min(n-1, i+1)   │───────────┤
              │   scroll_offset = 0 (reset)          │           │
              │                                      │           │
              │ 1-9:                                 │           │
              │   Jump to tab[key-1] if exists       │───────────┤
              │   scroll_offset = 0 (reset)          │           │
              │                                      │           │
              │ Up Arrow:                            │           │
              │   scroll_offset = max(0, offset-1)   │───────────┤
              │                                      │           │
              │ Down Arrow:                          │           │
              │   scroll_offset = min(max, offset+1) │───────────┤
              │                                      │           │
              │ PageUp/PageDown:                     │           │
              │   Faster scroll (larger delta)       │───────────┤
              │                                      │           │
              │ Home/End:                            │           │
              │   scroll_offset = 0 or max           │───────────┤
              │                                      │           │
              │ Terminal too small:                  │           │
              │   Show resize message, retry render  │───────────┘
              │                                      │
              │ q / Esc:                             │
              │   EXIT                               │───────────▶ DONE
              └──────────────────────────────────────┘
```

### 7.3 Input Handling Summary

| Key | Action |
|-----|--------|
| `←` Left | Previous tab, reset scroll |
| `→` Right | Next tab, reset scroll |
| `1`-`9` | Jump to tab by index (if exists), reset scroll |
| `↑` Up | Scroll content up by 1 line |
| `↓` Down | Scroll content down by 1 line |
| `PageUp` | Scroll up by page |
| `PageDown` | Scroll down by page |
| `Home` | Scroll to top |
| `End` | Scroll to bottom |
| `q` | Quit |
| `Esc` | Quit |

**Mouse:** Optional, best-effort only. Keyboard is the primary and required input method.

---

## 8. Error Handling and Graceful Degradation

### 8.1 Error Categories

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ERROR HANDLING STRATEGY                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ NETWORK ERRORS (Fatal)                                               │   │
│  │                                                                      │   │
│  │ Search page fetch fails:                                             │   │
│  │   → Print friendly error message                                     │   │
│  │   → Exit non-zero                                                    │   │
│  │                                                                      │   │
│  │ Feature page fetch fails:                                            │   │
│  │   → Print friendly error message                                     │   │
│  │   → Exit non-zero                                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PARSE ERRORS (Graceful Degradation)                                  │   │
│  │                                                                      │   │
│  │ Field extraction fails:                                              │   │
│  │   → Continue with partial data                                       │   │
│  │   → Use None/default for missing fields                              │   │
│  │   → Show warning: "Some sections could not be parsed                 │   │
│  │     (site layout may have changed)."                                 │   │
│  │                                                                      │   │
│  │ In full mode with missing tabs:                                      │   │
│  │   → Hide missing tabs entirely                                       │   │
│  │   → Do NOT show empty panes                                          │   │
│  │                                                                      │   │
│  │ Support list missing:                                                │   │
│  │   → Show warning line                                                │   │
│  │   → Still display title/description                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ USER CANCELLATION                                                    │   │
│  │                                                                      │   │
│  │ User presses q/Esc during selection:                                 │   │
│  │   → Exit non-zero (no output)                                        │   │
│  │                                                                      │   │
│  │ User presses q/Esc during full-screen mode:                          │   │
│  │   → Exit 0 (normal exit after viewing)                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Error Message Guidelines

All user-facing errors must:
- Be friendly and non-technical (no stack traces by default)
- Suggest possible causes where applicable
- Avoid exposing internal implementation details

### 8.3 Debug Mode

A developer-only debug mode is available via environment variable:

```bash
PYCANIUSE_DEBUG=1 caniuse flexbox
```

Debug output (to stderr, no disk writes):
- Which selectors matched
- Available browser keys found
- Range counts per browser

---

## 9. Extensibility Points

### 9.1 New Content Sections

The architecture supports discovering and displaying additional sections (tabs) beyond the core three:

```
Current tabs (explicitly specified):
├── Notes
├── Resources
└── Sub-features

Extensible tabs (discoverable):
├── Known issues
├── Feedback
└── (Future sections as caniuse.com evolves)
```

**Extension Strategy:**
- The `parse_feature_full()` function can be extended to search for additional `dt` headers or section containers
- New tabs are added to the `tabs` dict with their content
- UI automatically accommodates additional tabs

### 9.2 Layout Changes on caniuse.com

The selector strategy with primary + fallback handles layout changes:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ SELECTOR FALLBACK CHAIN EXAMPLE                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ Title extraction:                                                           │
│   1. Primary: .feature-title                                                │
│   2. Fallback: h1.title, .main-title, etc.                                  │
│   3. Final: Return empty string or "Unknown Feature"                        │
│                                                                             │
│ When adding new selectors:                                                   │
│   1. Update parse_feature.py with new primary selector                      │
│   2. Keep old selector as first fallback                                    │
│   3. Add additional fallbacks as needed                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Adding New Browsers to Basic Mode Filter

The browser filter for basic mode is defined as a constant:

```
BASIC_MODE_BROWSERS = ["chrome", "edge", "firefox", "safari", "opera"]
```

To modify the filter:
- Update this constant
- No other code changes required

---

## 10. Phase Mapping

This architecture maps directly to the Implementation Plan phases:

| Phase | Modules | Architecture Section |
|-------|---------|---------------------|
| **Phase 0** | Package structure (`caniuse/`) | §3.1 Package Structure |
| **Phase 1** | `http.py` | §3.3 (http.py), §4.1-4.2 (data flow) |
| **Phase 2** | `parse_search.py`, `ui_select.py`, `cli.py` | §3.3, §4.1, §6 |
| **Phase 3** | `model.py`, `parse_feature.py`, `util_text.py`, `util_html.py` | §3.3, §5 |
| **Phase 4** | `render_basic.py`, `cli.py` | §6.1 |
| **Phase 5** | `parse_feature.py` (full), `ui_fullscreen.py` | §5, §6.2, §7 |
| **Phase 6** | All modules (hardening + debug mode) | §8 |
| **Phase 7** | Documentation | README.md |

---

## 11. Performance Characteristics

| Metric | Basic Mode | Full Mode |
|--------|-----------|-----------|
| HTTP requests | 2 (search + feature) | 2 (search + feature) |
| Parse operations | 2 (search + feature basic) | 2 (search + feature full) |
| UI complexity | Print-and-exit | Interactive event loop |
| Memory | Minimal (single feature) | Feature + pre-rendered content |
| Expected latency | < 2 seconds (network-bound) | < 2 seconds + UI interaction |

---

## 12. Dependency Summary

| Package | Purpose |
|---------|---------|
| `click` | CLI argument parsing |
| `rich` | Terminal UI (tables, panels, interactive elements) |
| `justhtml` | HTML5 parsing with CSS selectors |
| `httpx` | HTTP client (preferred over requests) |
| `typing-extensions` | Python < 3.11 compatibility (optional) |

---

## Appendix A: Quick Reference

### A.1 Command Syntax

```bash
caniuse <query>          # Basic mode (5 browsers, simple output)
caniuse <query> --full   # Full mode (all browsers, interactive tabs)
```

### A.2 Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| Non-zero | Error or no matches |

### A.3 URLs

| Purpose | URL Pattern |
|---------|-------------|
| Search | `https://caniuse.com/?search=<query>&static=1` |
| Feature | `https://caniuse.com/<slug>?static=1` |
