# Microdata Lab

Official releases are messy. Microdata Lab downloads them, checks them, keeps every revision, and builds charts you can audit. It doesn’t quietly swap in a mirror or make up a fallback when an agency endpoint breaks.

This project is inspired largely by [Matt Bruenig's microdata system](https://www.youtube.com/watch?v=KQog2g_zoJ8). Check out his work at the [People's Policy Project](https://www.peoplespolicyproject.org/).

[![Hormuz exposure, oil, gasoline, and inflation expectations updating in sequence](demos/demo4-hormuz-watch/media/hormuz-watch.gif)](demos/demo4-hormuz-watch/)

<p align="center"><strong>Oil and gasoline jumped. Five-year inflation expectations barely moved.</strong><br>One command refreshes the official series and rebuilds the finding when the data change.</p>

## What it’s for

<table>
<tr>
<td width="50%" valign="top">
<a href="demos/demo1-low-tax-illusion/"><img src="demos/demo1-low-tax-illusion/media/low-tax-illusion.png" alt="U.S. tax wedge with employer health premiums compared with Nordic countries"></a>
<br><strong>The low-tax illusion</strong><br>
Health premiums move the normalized U.S. labor-cost wedge from 30.0% to 37.9%—within one point of the Nordic average.
</td>
<td width="50%" valign="top">
<a href="demos/demo2-housing-assistance/"><img src="demos/demo2-housing-assistance/media/housing-assistance.png" alt="Severe housing burden by poverty band and rental assistance"></a>
<br><strong>Housing beyond the market</strong><br>
Public housing and vouchers coincide with lower severe burden in every low-income band studied. At the very bottom, every arrangement still fails most households.
</td>
</tr>
<tr>
<td width="50%" valign="top">
<a href="demos/demo3-public-power/"><img src="demos/demo3-public-power/media/public-power.png" alt="Rural electrification and current utility prices by ownership"></a>
<br><strong>Public capacity</strong><br>
Rural electric access rose from 9.1% to 97.9% after the public buildout. Municipal utilities now charge 18% less than investor-owned utilities.
</td>
<td width="50%" valign="top">
<a href="demos/demo4-hormuz-watch/"><img src="demos/demo4-hormuz-watch/media/hormuz-watch.png" alt="Hormuz energy and inflation watch"></a>
<br><strong>The shock watch</strong><br>
Brent and gasoline are up more than 30% from the pre-disruption baseline. Five-year inflation expectations are down 19 basis points.
</td>
</tr>
</table>

The [demo index](demos/README.md) has the source decisions, code, limitations, and 11–13 second GIF/WebM explanations. The fourth demo also has a refresh command that stays quiet when no official release has changed.

## Write in your voice

The writing rules live in this repository. [docs/writing-voice.md](docs/writing-voice.md) runs a short calibration: you type your version of a handful of phrases, and the agent turns your samples into the project's voice. Every public page and chart title follows it from the first draft. It takes a few minutes, and nothing is published until the owner has answered.

## Try it in five minutes

Five minutes gets you the code, the tests, and the finished demos. You do **not** need a data account for that. Accounts and API keys only enter the picture when you decide to pull one of the opt-in sources yourself.

### Let Hermes Agent do it

[Hermes Agent](https://hermes-agent.nousresearch.com/docs/) and its new [Bot Mode](https://github.com/NousResearch/Hermes-Bot-Mode) are highly recommended. Bot Mode gives a research agent its own files, credentials, memory, and recurring jobs instead of mixing everything into one chat.

Paste this into Hermes Agent:

```text
Set up this repository on my machine:
https://github.com/melon-xf/microdata-lab

Read AGENTS.md.
Install the core dependencies and run the tests.
Show me the four demos.
Skip R and browser QA unless I ask for them.

Then run: uv run microdata sources
Tell me which sources are keyless before pulling data.
If I choose an opt-in source, follow the README's account steps.
Give me the official signup link and pause while I use it.
Never ask me to paste a key into chat.
Use the repository's hidden-input helper.
```

Hermes will set up the repo and show you what already works. It should not send you through four signup forms on spec. Pick a source first; configure only that source.

When you do pick one, this is the handoff:

- **IPUMS:** [make an account](https://account.ipums.org/user/new), register for the collection you need, [make a key](https://account.ipums.org/api_keys), then let Hermes run `uv run python scripts/configure_ipums_key.py` so you can enter it privately.
- **FRED:** [sign in and request a key](https://fredaccount.stlouisfed.org/apikeys), then let Hermes run `uv run python scripts/configure_api_key.py fred`.
- **Census:** [request a key](https://api.census.gov/data/key_signup.html), check your email, then let Hermes run `uv run python scripts/configure_api_key.py census`.
- **BLS:** there is no account or key. Let Hermes run `uv run python scripts/configure_bls_contact.py`; you enter the identifying name and email BLS expects.
- **GSS:** read the [data terms](https://gss.norc.org/terms-and-conditions.html). There is no secret to configure.

### OpenCode, Claude Code, Oh My Pi, Pi, ZCode, or Codex

Clone the repo once:

```bash
git clone https://github.com/melon-xf/microdata-lab.git
cd microdata-lab
```

Then open that folder with the agent you already use:

| Agent | Start here |
|---|---|
| [OpenCode](https://opencode.ai/docs/cli/) | `opencode .` |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code/quickstart) | `claude` |
| [Oh My Pi](https://github.com/can1357/oh-my-pi) | `omp` |
| [Pi](https://pi.dev/docs/latest/quickstart) | `pi` |
| [ZCode](https://zcode.z.ai/) | Open `microdata-lab` as a workspace. |
| [Codex](https://developers.openai.com/codex/cli/) | `codex` |

Paste this prompt into the agent:

```text
Read AGENTS.md.
Set up the core project in this folder.
Run the tests and show me the four demos.
Do not install R or Playwright yet.

Then run: uv run microdata sources
Tell me which sources are keyless.
If I choose an opt-in source, follow the README's account steps.
Show me the official page and exact local configuration command.
Never put a key in chat, output, shell history, or this repository.
```

These agents all get the same repository rules from `AGENTS.md`. The commands above just put each one in the right folder.

<details>
<summary><strong>Or set it up by hand</strong></summary>

You need [uv](https://docs.astral.sh/uv/), Node.js 22+, and npm. R is optional unless you want the static ggplot2 renderer.

```bash
git clone https://github.com/melon-xf/microdata-lab.git
cd microdata-lab
uv sync --all-extras --dev
npm --prefix viz/interactive ci
uv run microdata --help
```

The published CSVs, PNGs, and self-contained interactive pages are already here. If you only want to inspect or rerender them, stop here. No account is needed.

```bash
ANALYSIS=analyses/energy-2026-hormuz-inflation-watch
uv run microdata viz interactive "$ANALYSIS/data.csv" "$ANALYSIS/chart.yaml" "$ANALYSIS/interactive.html"
```

For static R graphics and browser QA:

```bash
scripts/bootstrap_r.sh
npx --prefix viz/interactive playwright install --with-deps chromium
```

#### Pulling fresh source data

First, see what is available:

```bash
uv run microdata sources
```

Most implemented sources are keyless: SCF, SIPP, AHS, CE, SHED, OECD, World Bank, Eurostat, WHO, ILO, MEPS, and the energy watch all use public agency downloads. The general FRED and Census adapters and the three IPUMS-backed sources are opt-in. BLS needs an identifying contact. GSS requires you to read its terms.

Set up only the source you plan to use:

1. **IPUMS — ACS PUMS, CPS ASEC, and ATUS**
   - [Create an IPUMS account](https://account.ipums.org/user/new), then register for the collection you need: IPUMS USA for ACS, IPUMS CPS for CPS ASEC, or IPUMS Time Use for ATUS.
   - [Create an API key](https://account.ipums.org/api_keys). IPUMS documents the full sequence in its [API getting-started guide](https://developer.ipums.org/docs/v2/get-started/).
   - Store it without showing it on screen:

     ```bash
     uv run python scripts/configure_ipums_key.py
     ```

2. **FRED — general FRED adapter**
   - [Create or sign in to a FRED account and request a key](https://fredaccount.stlouisfed.org/apikeys).
   - Store it with hidden input:

     ```bash
     uv run python scripts/configure_api_key.py fred
     ```

   - The Hormuz demo uses FRED’s keyless CSV downloads. It does not need this key.

3. **Census — ACS table API**
   - [Request a Census API key](https://api.census.gov/data/key_signup.html). Census sends it to the email address on the form.
   - Store it with hidden input:

     ```bash
     uv run python scripts/configure_api_key.py census
     ```

4. **BLS CPI**
   - No account or API key is required. BLS automated downloads need an identifying contact in the request header.
   - Enter your name and email locally:

     ```bash
     uv run python scripts/configure_bls_contact.py
     ```

5. **GSS**
   - No secret is configured. Read the [GSS data terms](https://gss.norc.org/terms-and-conditions.html) before downloading or publishing, then use the public release files.

The helpers write only to `~/.config/microdata-lab/.env` (or `MICRODATA_ENV_FILE`) with mode `0600`. Do not put a real key in the repository’s `.env.example`, paste it into an agent chat, or add it directly to a shell command.
</details>

## Bad data doesn’t get a makeover

[![Official source enters validation, then either reaches an immutable release and published claim or stops on a visible failure path](docs/diagrams/microdata-evidence-flow.png)](docs/diagrams/microdata-evidence-flow.html)

A polished chart cannot rescue a failed source. Every adapter downloads into a unique incoming run, hashes each artifact, checks required files and benchmarks, then promotes the complete release atomically. If a file changes at the same URL, it becomes a new revision. If a check fails, the last good release stays current.

## Pull a source

```bash
uv run microdata sources
uv run microdata sync scf --year 2022
uv run microdata status
uv run microdata catalog rebuild
uv run microdata catalog search "credit card balance"
```

Data land in `$XDG_DATA_HOME/microdata-lab` by default. Set `MICRODATA_ROOT` to put the lake elsewhere. Raw and promoted releases are immutable.

Account links and protected setup commands are in [Try it in five minutes](#try-it-in-five-minutes). The Hormuz watch uses keyless FRED CSV releases and needs no FRED key.

## What an analysis contains

Every `analyses/<name>/` directory carries the whole argument:

- `question.md` defines the estimand, universe, design, and assumptions;
- `estimate.py` does the calculation;
- `data.csv` is the exact renderer input;
- `diagnostics.json` records row counts, design treatment, uncertainty, and benchmarks;
- `chart.yaml` declares the chart;
- `figure.png` and `interactive.html` publish the same numbers;
- `README.md` states the result and where it can break.

The repository currently includes **17 contract-checked analyses** from SCF, AHS, MEPS, SHED, CE, EIA, OECD, the World Bank, Eurostat, and other official releases.

## Keep following the story

The Hormuz demo runs the whole update path:

```bash
uv run python demos/demo4-hormuz-watch/refresh.py
```

It retrieves the market series and EIA workbook, promotes a new release only when every gate passes, and rebuilds the finding when the data change. The repository does not sneak a scheduler onto your machine. Bring your own cron, CI job, or agent.

## Rules that matter

- Official agencies and explicitly configured licensed APIs are authoritative. Mirrors are not.
- Variable names are not definitions. Analyses cite the codebook or curated catalog entry.
- Survey universes, weights, replicate weights, implicates, uncertainty, and benchmarks are part of correctness.
- Descriptive evidence stays descriptive. A dramatic line does not become a causal design.
- Confidence intervals live in the accessible table and diagnostics; publication graphics show point estimates without whiskers.
- Static and interactive charts share data, not necessarily geometry.
- Visual QA runs at 375, 768, 1280, and 1920 pixels.

## Under the hood

- **Acquisition and analysis:** Python, DuckDB, Parquet, Pydantic
- **Static graphics:** R, ggplot2, ragg, ggtext, patchwork, ggrepel
- **Interactive graphics:** TypeScript, Observable Plot, D3, esbuild
- **QA:** pytest, Ruff, mypy, Playwright, deterministic pixel gates

<details>
<summary><strong>Sources and benchmarks</strong></summary>

`uv run microdata sources` prints the live registry. Flagship adapters include SCF, ACS PUMS, CPS ASEC, ATUS, SIPP, AHS, CE, SHED, MEPS, GSS, OECD, World Bank, Eurostat, WHO, ILO, BLS CPI, FRED, Census, and the keyless energy watch. Each source carries its own required artifacts and benchmark contract.

Provider files stay outside Git. Public code does not turn copyrighted or licensed data into redistributable data. See the [provider redistribution review](docs/redistribution-review.md).
</details>

## Documentation

- [Architecture](docs/architecture.md)
- [Add a source](docs/adding-source.md)
- [Storage and backup](docs/storage-operations.md)
- [Source selection](docs/source-selection.md)
- [Chart and diagram system](viz/diagrams/README.md)
- [Agent harnesses](docs/agent-harnesses.md)
- [Writing voice](docs/writing-voice.md)

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Apache-2.0. Third-party notices live in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
