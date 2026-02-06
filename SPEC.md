SPEC: pycaniuse (CLI: caniuse) — HTML-only scraping with optional --full

1) Goals
- Provide a fast terminal CLI to query caniuse.com.
- Default mode is lightweight and quick; full fidelity is opt-in via --full.
- No disk writes (no cache files, no vendored data).
- No dependency on caniuse data.json (HTML scrape only).

2) Non-goals
- Offline support (beyond graceful errors).
- Persistent caching/indexing.
- Perfect pixel/CSS parity with the website (we match structure and content, not CSS).

3) CLI Interface
- caniuse <query> [--full]
  - <query>: free text. Example: "flexbox", "css grid", "flexbox-gap".
  - --full: enables full-screen interactive view, all browsers, and all sections (notes/resources/sub-features, plus any additional sections discovered).

4) High-level UX Flow (always 2-phase)

PHASE A: Search / Fuzzy match selection (always)
A1. Fetch search page:
    GET https://caniuse.com/?search=<query>&static=1
A2. Parse search results into a list of {slug, title, href}.
A3. Branch:
    - 0 results: show "No matches" and exit non-zero.
    - 1 result: auto-select it.
    - N results: show a Rich TUI bullet list, arrow keys up/down, Enter selects, q/Esc cancels.

A4. Optional shortcut behavior:
    If <query> exactly matches a returned slug, bypass the menu and select it immediately.
    (Example: "flexbox-gap" if it appears as a direct match.)

PHASE B: Feature detail fetch + render
B1. Fetch feature page:
    GET https://caniuse.com/<slug>?static=1
B2. Parse feature details (basic always; full adds more).
B3. Render:
    - Basic mode (default): print/pager simple output.
    - Full mode (--full): open a full-screen interactive Rich view with tabs and scrolling.

5) Output Requirements

5.1 Common fields (basic + full)
- Title (from .feature-title)
- Spec link + status badge (from a.specification)
  - spec_url: a.specification href
  - spec_status: visible status suffix like "CR" (do not rely only on class)
- Global usage (from li.support-stats[data-usage-id="region.global"])
  - supported %, partial %, total %
- Description (from .feature-description)

5.2 Browser support
Data source:
- Parse support blocks from:
  div.support-container div.support-list
Each block has:
- Browser heading: h4.browser-heading (class includes browser--<key>)
- Ranges: ol > li.stat-cell

Basic mode browser filter (ONLY show these 5):
- chrome, edge, firefox, safari, opera

Full mode:
- Show ALL support-list blocks found in the page, in the page order.

Each range line must preserve:
- range text: e.g. "4 - 20", "144", "all"
- status: supported/partial/not supported/unknown
- timeline: past/current/future
- title attribute: includes usage and textual status (keep verbatim)
- note markers: classes may include "#1" etc; preserve so we can display "See notes: 1" style hints where available.

5.3 Sections / “Tabs”
Basic mode:
- No interactive tabs.
- Optionally show a hint:
  “Run with --full to see all browsers + Notes/Resources/Sub-features.”

Full mode (--full):
- Full-screen interactive UI with tabs.
- Tabs are content sections extracted from the page (optional if missing):
  - Notes
  - Resources
  - Sub-features
  - (Known issues, Feedback if discoverable on other pages; treat as optional/extensible)

Default selected tab: Notes (if present), otherwise first available.

Tab content requirements (from provided HTML sample):
- Notes: div.single-page__notes
- Resources: dl.single-feat-resources (dd > a list)
- Sub-features: find dt text "Sub-features:" then collect following dd > a entries until next dt or end

6) Interactivity (Full Mode)
- Full-screen Rich app loop (NOT console.pager)
- Keybindings:
  - Left/Right: switch tabs
  - 1-9: jump to tab index (if present)
  - Up/Down: scroll content
  - PageUp/PageDown: faster scroll
  - Home/End: top/bottom
  - q: quit
  - Esc: quit
- Mouse “clickable tabs” is optional and best-effort only (keyboard is primary, must work everywhere).

7) Parsing & Robustness

7.1 HTML parser
- Use justhtml (HTML5 parser + CSS selectors).

7.2 Selector strategy: “best effort”
- Each field extraction must have:
  - primary selector
  - fallback selector(s)
  - graceful “missing field” handling without crashing

7.3 Error handling
- Network failures:
  - Search page fetch fails -> print friendly error and exit non-zero.
  - Feature page fetch fails -> print friendly error and exit non-zero.
- Parse failures:
  - Continue with partial data; show a single warning line:
    “Some sections could not be parsed (site layout may have changed).”
  - In full mode, hide missing tabs instead of showing empty panes.

8) Internal Data Model (Python)
8.1 Search results
- SearchMatch:
  - slug: str
  - title: str
  - href: str

8.2 Feature model
- FeatureBasic:
  - slug: str
  - title: str
  - spec_url: Optional[str]
  - spec_status: Optional[str]
  - usage_supported: Optional[float]
  - usage_partial: Optional[float]
  - usage_total: Optional[float]
  - description_text: str
  - browser_blocks: list[BrowserSupportBlock]

- BrowserSupportBlock:
  - browser_name: str
  - browser_key: str
  - ranges: list[SupportRange]

- SupportRange:
  - range_text: str
  - status: Literal["y","n","a","u"]
  - is_past: bool
  - is_current: bool
  - is_future: bool
  - title_attr: str
  - raw_classes: tuple[str, ...]

8.3 Full-only additions
- FeatureFull extends FeatureBasic:
  - notes_text: Optional[str]
  - resources: list[tuple[label:str, url:str]]
  - subfeatures: list[tuple[label:str, url:str]]
  - tabs: dict[str, str]  # rendered text per tab; only for available tabs

9) Rendering Rules
- Status icons:
  - y -> ✅
  - n -> ❌
  - a -> ◐
  - u -> ﹖
- Basic support display: group by browser, then list each range line as:
  "<range_text>: <Supported/Partial/Not supported/Unknown> [extra hints if available]"
- Full mode may render support in a denser multi-column layout, but must remain readable and include the same information.

10) Performance Targets
- Basic mode should feel quick for a single feature:
  - 2 HTTP fetches (search + feature)
  - parse + print
- Full mode adds UI loop but same fetch count.

11) Compliance & Constraints
- No disk writes.
- No vendored datasets.
- No data.json usage.
- Respect terminal compatibility: keyboard-driven UI first.
