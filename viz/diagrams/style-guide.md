# Microdata Lab diagram style

This is the project skin for the [`diagram-design`](https://github.com/cathrynlavery/diagram-design) grammar. It is intentionally distinct from the upstream default and matches the repository's `editorial` chart theme.

| Role | Value | Use |
|---|---:|---|
| `paper` | `#F7F5EF` | Page and node background |
| `paper-2` | `#EEEAE1` | Alternating lanes and secondary fills |
| `ink` | `#1D252C` | Primary text and strokes |
| `muted` | `#65727E` | Secondary text and default connectors |
| `soft` | `#87919A` | Technical sublabels |
| `rule` | `rgba(29,37,44,0.12)` | Hairlines and lane boundaries |
| `accent` | `#087F7A` | One focal node, step, and handoff |
| `accent-tint` | `rgba(8,127,122,0.09)` | Focal fill |
| `link` | `#3A6EA5` | External-source ingress |
| `failure` | `#D64B5E` | Explicit blocked/failure path only |

## Typography

- Human-readable labels: repository-local Jost, semibold.
- Technical labels and payload chips: ui-monospace fallback stack.
- Editorial title: Georgia fallback; it is visible framing, not a technical node.

## Non-negotiable rules

- Target density 4/10; split above nine nodes.
- Exactly one focal step and one focal node in process/data-flow diagrams.
- Draw connectors before nodes; use straight aligned lines or rounded orthogonal elbows, never diagonals.
- No shadows, gradients, decorative 3D, or dark technical-glow styling.
- Static is the default. The chart/media system owns animation.
- HTML is source of truth; PNG is exported from its accessible SVG.
- Every diagram passes `viz/diagrams/check.py`, browser geometry QA, and visual inspection.
