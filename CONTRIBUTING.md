# Contributing

Microdata Lab is licensed under the Apache License 2.0. This document describes the contribution contract that applies when the repository is public.

## Development setup

1. Install `uv`, Node.js, npm, and micromamba.
2. Run `uv sync --all-extras --dev`.
3. Run `scripts/bootstrap_r.sh`.
4. Install browser dependencies with `npm --prefix viz/interactive ci` and `npx --prefix viz/interactive playwright install --with-deps chromium`.
5. Run the verification commands below before proposing a change.

## Required verification

```text
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
npm --prefix viz/interactive run typecheck
```

Changes to renderers must also render the checked example analysis and run browser QA at 375, 768, 1280, and 1920 pixels.

## Source adapters

Follow `docs/adding-source.md` and the acquisition, methodology, and benchmark gates in `AGENTS.md`. New adapters must use official agency sources or an explicitly configured licensed API. They must fail visibly rather than substitute mirrors, inferred schemas, or fabricated fixtures.

## Data and credentials

Do not commit raw microdata, licensed extracts, secrets, `.env` files, generated caches, or provider credentials. Test fixtures must be synthetic, minimal, and labeled. Public documentation may link to official sources but must not redistribute files whose provider terms prohibit redistribution.

## Commits and pull requests

Keep changes coherent and scoped. Include tests for failure paths and describe the official benchmark used to accept a new source/year pipeline.
