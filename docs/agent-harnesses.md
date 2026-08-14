# Coding-agent contract

Start the agent from the repository root and make `AGENTS.md` its first read.
`CLAUDE.md` forwards the same contract for Claude Code. OpenCode, Oh My Pi,
Pi, ZCode, Codex, and other harnesses should receive the same instruction
explicitly if they do not load it automatically.

The contract requires official sources, immutable validated releases,
documented survey design, executable analyses, and visible failures. It also
keeps credentials out of prompts, output, shell history, and Git.

For chart work, read `docs/dataviz-wiki/` and the renderer rulebook before
changing a specification or output. For diagrams, follow
`viz/diagrams/README.md`.

## Standard commands

```text
uv sync --all-extras --dev
uv run microdata sources
uv run microdata discover scf --year 2022
uv run microdata sync scf --year 2022
uv run pytest
uv run ruff check .
uv run mypy src
npm --prefix viz/interactive run typecheck
```

The root README has the maintained launch commands and credential handoff for
each supported agent. R is optional and provisioned with
`scripts/bootstrap_r.sh`. Large data belongs under `MICRODATA_ROOT`, never in
the Git worktree.
