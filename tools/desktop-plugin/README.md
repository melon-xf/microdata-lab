# Desktop plugin (microdata-lab)

Hermes desktop integration for this repo: a layout pane (repo health:
branch tip, contract-check pass/fail counts), a statusbar chip
(`mdlab` — click to re-check, green/gray/red dot), and three command-palette
commands (`Run microdata viz gates`, `Run microdata check-analysis`,
`Run microdata tests`) that execute inside the repo venv and toast the exit
status.

## Files

- `plugin.js` — frontend. Live copy goes to
  `~/.hermes/desktop-plugins/microdata-lab/plugin.js` (hot-reloaded by the
  desktop app; enable via ⌘K → "Reload desktop plugins", then
  Settings → Plugins).
- `plugin_api.py` + `manifest.json` — Python backend. Live copy goes to
  `~/.hermes/plugins/microdata-lab/dashboard/`. The backend is imported only
  when `plugins.enabled` in `config.yaml` lists `microdata-lab`.

## Security model

The backend executes an allowlist of commands only (`gates`, `check`,
`tests`, `sources`, `new <slug>` with slug sanitization). It shells out via
`uv run` inside the cloned repo (auto-detected; override with
`MICRODATA_LAB_REPO`). No arbitrary command
execution, no secrets returned; output is truncated.

## Install

```sh
cp plugin.js ~/.hermes/desktop-plugins/microdata-lab/plugin.js
mkdir -p ~/.hermes/plugins/microdata-lab/dashboard
cp plugin_api.py manifest.json ~/.hermes/plugins/microdata-lab/dashboard/
# add 'microdata-lab' under plugins.enabled in config.yaml if using the backend
```

Then ⌘K → **Reload desktop plugins**.
