IMPLEMENTATION PLAN (detailed, HTML-grounded, with edge cases) — pycaniuse

This plan is authoritative for Codex/agents. It is grounded in the provided HTML sample and must
handle real-world variance across caniuse pages without crashing.

=====================================================================
PHASE 0 — Scaffold & packaging
=====================================================================

0.1 Repository layout (Python-only)
- pyproject.toml
- src/pycaniuse/
  - __init__.py
  - cli.py
  - http.py
  - model.py
  - parse_search.py
  - parse_feature.py
  - render_basic.py
  - ui_select.py
  - ui_fullscreen.py
  - util_text.py        (wrapping, stripping, percent parsing, etc.)
  - util_html.py        (selector helpers + debug hooks)
- README.md

0.2 Dependencies (Python)
- click
- rich
- justhtml
- httpx (preferred) OR requests (pick one, don’t mix)
- typing-extensions (optional)

Acceptance:
- editable install exposes `caniuse` CLI.
- No disk writes anywhere (audit: no open(...,'w'), no caches, no tempfile output).

=====================================================================
PHASE 1 — HTTP client (reliable, respectful, deterministic)
=====================================================================

1.1 http.py: fetch_html(url, params=None) -> str
- Always set a predictable User-Agent string (e.g., "pycaniuse/<version>").
- Use a short timeout (10s) and sensible retry policy:
  - 0 retries by default (determinism)
  - 1 retry for transient connection errors only (optional)
- Raise a typed exception for:
  - connection error
  - timeout
  - non-200 response
  - content-type mismatch (optional; caniuse might not send strict types)

1.2 URL conventions
- Search:
  GET https://caniuse.com/?search=<query>&static=1
  - NOTE: your sample HTML form includes <input name="static" value="1">.
  - Use it to prefer static-ish markup.

- Feature:
  GET https://caniuse.com/<slug>?static=1
  - If adding ?static=1 breaks some feature pages, fall back to without it.

Edge cases:
- caniuse might return a 200 page with an interstitial or minimal HTML; must still parse or error cleanly.

Acceptance:
- Fetching your sample URL yields HTML string.
- Errors print human-friendly messages only (no traceback by default).

=====================================================================
PHASE 2 — Search parsing & selection UI (Phase A)
=====================================================================

2.1 parse_search.py: parse_search_results(html) -> list[SearchMatch]
Goal: extract {slug, title, href} for each search result.

IMPORTANT: The provided HTML is a FEATURE page, not a SEARCH results page.
So implement parsing with two strategies:
- Strategy S1: "search results page" structure (primary)
- Strategy S2: fallback heuristic (anchors to /<slug> with meaningful text)

S2 heuristic rules:
- Consider <a href="/something"> where:
  - href starts with "/" AND not "/ciu/" AND not "/issue-list" etc.
  - href does not contain "?" (ignore nav links)
  - link text length >= 3
  - slug contains only [a-z0-9-] (feature slugs look like that)
- De-dupe by slug, preserve order.

Edge cases:
- Search page may include:
  - nav links (Home, News, Compare, About)
  - "New feature" banner <a class="news js-news" href="https://caniuse.com/css-grid-lanes">
- Must ignore external URLs and keep only site-local feature slugs.

2.2 Shortcut behavior
If query exactly matches one of the parsed slugs:
- auto-select it without showing the menu.

If only one match:
- auto-select.

If multiple matches:
- show Rich selector.

2.3 ui_select.py: interactive selection list
- Render each option as:
  • <title>  /<slug>
- Keys:
  - Up/Down: move selection
  - Enter: choose
  - q / Esc: abort

Edge cases:
- Very long title lines: truncate with ellipsis but keep slug visible.
- Large result set: allow scrolling viewport.

Acceptance:
- With a mocked list of results, the selector works as specified.

=====================================================================
PHASE 3 — Feature parsing (Phase B) — HTML sample grounded
=====================================================================

3.1 model.py: dataclasses (as in spec)
- SearchMatch
- FeatureBasic
- FeatureFull
- BrowserSupportBlock
- SupportRange

3.2 parse_feature.py: helpers
Implement robust helpers to avoid brittle parsing:
- first(doc, selector) -> node | None
- all(doc, selector) -> list[nodes]
- text(node) -> str (normalize whitespace)
- attr(node, name) -> str | None
- parse_percent("96.79%") -> float
- safe_join_url(base, href) -> absolute URL

3.3 Extract common header fields (from your HTML)

TITLE:
- Primary selector: ".feature-title"
- Fallback: "title" element parsed from <head> (split on " | Can I use")
- Output: title str (required; if missing use slug as last resort)

SPEC LINK + STATUS:
From:
<a href="https://www.w3.org/TR/css3-flexbox/" class="specification cr" title="W3C Candidate Recommendation">
  ... - CR
</a>

- Selector: "a.specification"
- spec_url: href
- spec_status:
  - Parse visible text; best rule:
    - take last non-empty token after "-" (e.g. "- CR" => "CR")
  - fallback to class names (cr, wd, etc.) if visible parsing fails.

Edge cases:
- Some features may not have a spec link (spec_url=None).
- The visible text may vary; do not hardcode "- CR".

GLOBAL USAGE:
From:
<li class="support-stats" data-usage-id="region.global">
  <span class="support">96.39%</span>
  <span class="partial">0.4%</span>
  <span class="total">96.79%</span>
</li>

- Base selector: 'li.support-stats[data-usage-id="region.global"]'
- supported: ".support"
- partial: ".partial"
- total: ".total"
- Parse to float, strip '%' and whitespace.

Edge cases:
- Some pages may omit partial or total.
- Some locales may format with commas; tolerate "96,79%" by replacing comma with dot if needed.

DESCRIPTION:
From:
<div class="feature-description"><p>...<code>flex</code>...</p></div>

- Selector: ".feature-description"
- Requirement:
  - Convert to plain text but preserve inline code markers as backticks if feasible.
  - If justhtml supports markdown-ish conversion, use it; else do:
    - text extraction and post-process code spans.

Edge cases:
- Description may include links; keep link text and optionally append URL in full mode.

3.4 Browser support parsing (core complexity)

STRUCTURE in sample HTML:
<div class="support-list last-era-3">
  <h4 class="browser-heading browser--chrome">Chrome</h4>
  <ol>
    <li class="stat-cell a x #1 past" title="Global usage: ... - Partial support, requires ...">
      4 - 20
    </li>
    ...
  </ol>
</div>

Extraction algorithm:
- Find all support blocks:
  - Selector: ".support-container .support-list"
  - For each block:
    - heading node: "h4.browser-heading"
    - browser_name: heading text
    - browser_key: parse from class list item starting with "browser--"
      - Example: "browser--chrome" => "chrome"
    - ranges: for each "ol > li.stat-cell":
      - raw_classes: tuple of class tokens
      - status: first token among {"y","n","a","u"} found in class list
        - Sample: "a" or "y" or "n"
      - timeline flags:
        - is_past = "past" in classes
        - is_current = "current" in classes
        - is_future = "future" in classes
      - range_text: normalized text content (e.g. "4 - 20", "144", "all")
      - title_attr: li.get("title") (keep verbatim)
      - note markers:
        - class tokens like "#1", "#4" may appear.
        - Preserve them in raw_classes so renderer can show "See notes: 1,4" if desired.

Basic mode filtering:
- Keep only browser_key in {"chrome","edge","firefox","safari","opera"}.

Full mode:
- Keep all blocks, preserve order.

Edge cases:
- Some browsers may have no <ol> or different structure; skip gracefully.
- "TP" or "Preview" ranges appear (e.g., "26.3 - TP"); treat as plain text.
- Some items include "x" class for prefixed requirement; preserve via raw_classes + title_attr.

Acceptance:
- Parsing your HTML must produce:
  - Chrome ranges: 4-20 partial, 21-28 supported, 29-143 supported, 144 current, 145-147 future
  - etc. for other browsers.

3.5 Full-only extra sections (from your HTML sample)

NOTES:
<div class="single-page__notes">
  <p>Most partial support refers to ... <a href="...">older version</a> ...</p>
</div>
- Selector: ".single-page__notes"
- Extract as:
  - plain text with preserved links OR markdown-ish text.
- Store as notes_text.

RESOURCES:
<dl class="single-feat-resources">
  <dt>Resources:</dt>
  <dd><a href="...">Flexbox CSS generator</a></dd>
  ...
</dl>
- Selector: "dl.single-feat-resources dd a"
- Extract list of (label, absolute_url)

Edge cases:
- Some resources may have relative URLs; normalize.
- Some pages may have no resources; omit tab.

SUB-FEATURES:
In sample:
<dl>
  <dt>Sub-features:</dt>
  <dd><a href="./flexbox-gap">gap property for Flexbox</a></dd>
</dl>

Algorithm:
- Find dt elements: "dl dt"
- Locate dt whose text normalized equals "Sub-features:"
- Then collect following sibling dd elements until next dt or end
- For each dd a: (label, normalized href)

Edge cases:
- Multiple <dl> blocks: only the one with dt "Sub-features:".
- dd might contain multiple links.

KNOWN ISSUES / FEEDBACK:
- Not present in your sample HTML.
- Must be treated as optional:
  - If future pages contain identifiable sections, add extraction later without breaking current flow.

Acceptance:
- For your HTML sample:
  - Notes tab exists
  - Resources tab exists with 10 links
  - Sub-features tab exists with flexbox-gap

=====================================================================
PHASE 4 — Rendering (Basic mode)
=====================================================================

4.1 render_basic.py: render_basic(feature: FeatureBasic) -> Rich renderable
- Header:
  - Title
  - Spec status + URL
  - Global usage (supported + partial = total)
- Description
- Support (5 browsers only):
  For each BrowserSupportBlock:
    - print browser heading
    - print each SupportRange line:
      "<range_text>: <status_label> [optional note markers]"
    Status label mapping:
      y -> "Supported" (✅)
      n -> "Not supported" (❌)
      a -> "Partial support" (◐)
      u -> "Unknown" (﹖)

Edge cases:
- Missing usage: hide usage line.
- Missing spec: hide spec line.

Acceptance:
- `caniuse flexbox` shows only the 5 specified browsers.

=====================================================================
PHASE 5 — Rendering + UI (Full mode)
=====================================================================

5.1 FeatureFull parsing
- Use parse_feature_full to build tabs dict in stable order:
  1) Notes
  2) Resources
  3) Sub-features
  + optional future tabs if discovered

5.2 ui_fullscreen.py: full-screen interactive app loop
State:
- selected_tab_idx: int
- scroll_offset: int (for tab content pane)
- support_scroll_offset: int (optional; if support list is long)
- tabs: list[str]
- tab_lines: dict[str, list[str]] (pre-wrapped)
- mode_focus: "support" or "tab" (optional; if both scroll)

Layout:
- Header region (fixed):
  - Title
  - Spec
  - Usage
- Support region:
  - All browsers support blocks rendered densely
  - If too long: allow scrolling OR collapse/expand browsers (optional later)
- Tabs row (fixed):
  - render tab labels with active highlight
- Content region (scrollable):
  - render selected tab content

Keybindings:
- Left/Right: switch tabs
- 1-9: jump to tab
- Up/Down: scroll content region
- PageUp/PageDown/Home/End: scroll
- q/Esc: quit

Edge cases:
- Very long resources list: content scroll handles it.
- Notes with lots of links: wrap cleanly.
- Terminal too small: show a minimal message "Terminal too small; resize" and retry render.

Acceptance:
- `caniuse flexbox --full` allows:
  - switching between Notes/Resources/Sub-features
  - scrolling long Resources
  - quitting with q

=====================================================================
PHASE 6 — Hardening & diagnostics
=====================================================================

6.1 Debug mode (developer-only, not exposed by default)
- Provide internal toggle (env var like PYCANIUSE_DEBUG=1) to:
  - print which selectors matched
  - dump available browser keys found
  - show counts of ranges per browser
No disk writes; just stderr logs.

6.2 Resilience
- If any section missing:
  - omit tab
  - no crash
- If support list missing:
  - show warning line and still show title/description.

6.3 Consistent error UX
- All exceptions converted to friendly output.
- Non-zero exit codes for failure.

Acceptance:
- When selectors fail, CLI still returns usable output + warning, not tracebacks.

=====================================================================
PHASE 7 — Documentation (minimal, accurate)
=====================================================================

7.1 README.md
- What it is
- Install
- Usage examples:
  - caniuse flexbox
  - caniuse flexbox --full
- Keybindings for full mode
- Limitations (HTML structure changes, depends on network)

Acceptance:
- README matches real behavior.
