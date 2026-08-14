# Diagram system

Microdata Lab uses Cathryn Lavery's MIT-licensed [`diagram-design`](https://github.com/cathrynlavery/diagram-design) grammar for architecture, process, and data-flow figures. The integration is pinned to upstream commit `a5e3978088cf89c7caff5c20cabd99fbc2a301de` (skill version 2.3).

The repository does not execute a mutable upstream package at build time. It keeps:

- a project-specific [style guide](style-guide.md);
- accessible, static, one-file HTML/SVG sources under `docs/diagrams/`;
- a local structural validator, adapted from upstream's self-check contract;
- a Playwright renderer that fails on viewBox overflow or aspect-ratio drift.

## Build and validate

```bash
uv run python viz/diagrams/check.py docs/diagrams/microdata-evidence-flow.html
(
  cd viz/interactive
  node render-diagram.mjs ../../docs/diagrams/microdata-evidence-flow.html \
    ../../docs/diagrams/microdata-evidence-flow.png 2
)
```

The canonical README preset is a 960×600 viewBox rendered at 2× to a 1920×1200 PNG.

## Authoring contract

1. Decide whether a diagram teaches more than prose or a table.
2. Choose one diagram type and state the detail/size/audience budget.
3. Use [style-guide.md](style-guide.md), not upstream default colors.
4. Keep HTML static and script-free; include SVG `title`, `desc`, and prefixed IDs.
5. Run structural validation and browser geometry checks.
6. Inspect the PNG at native size and at README width before linking it.

See `THIRD_PARTY_NOTICES.md` for license attribution.
