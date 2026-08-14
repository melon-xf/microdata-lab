# Architecture

## Data plane

```text
official release page
  → source adapter discovery
  → unique incoming run
  → streamed download + SHA-256
  → archive safety and required-artifact gates
  → survey-specific design/schema checks
  → official benchmark
  → documentation sidecars
  → content-addressed immutable release
  → atomic current pointer
  → DuckDB catalog
```

Routine acquisition is deterministic software. Agents choose sources, inspect methodology, write analyses, and diagnose failed adapters; they do not improvise downloads.

## Storage

The Git repository and data lake are separate. `$MICRODATA_ROOT` contains:

- `incoming/`: unique in-progress runs;
- `quarantine/`: failed runs with the evidence needed to debug them;
- `releases/<survey>/<year>/<release-sha256>/`: immutable artifacts, extracted members, docs, validation, and manifest;
- `current/<survey>.json`: atomically replaced pointer to a validated release;
- `catalog/catalog.duckdb`: rebuildable release, artifact, variable, and document index.

An unchanged URL with changed bytes produces a new release digest. The previous release remains intact. HEAD validators skip downloads only when every artifact has matching official ETags or matching modification/length metadata; missing validators fall back to full download and checksum.

## Trust boundaries

- Only official agency hosts or explicitly configured licensed APIs are authoritative.
- Archive members are rejected if absolute, path-traversing, or symbolic links.
- Credentials come from environment variables or an approved secret store and never enter manifests.
- A failed gate moves only the unique incoming run to quarantine. It cannot update `current/`.
- Documentation sidecars retain source checksums and explicit page markers.

## Analysis plane

Every analysis directory owns its estimand and complete rendering inputs. Statistical code writes `data.csv` and `diagnostics.json`; neither renderer computes survey estimates. Static R and interactive TypeScript consume the same `data.csv` and `chart.yaml`.

SCF is the first adapter because it exercises the hard cases immediately: five implicates, 999 bootstrap replicates plus multiplicity factors, weighted bins, and official benchmark reproduction.

## Refresh

`scripts/scheduled_sync.sh` runs enabled adapters without an LLM. It stays silent when official files are unchanged, reports newly promoted release IDs, and exits nonzero on discovery or validation failure so scheduler errors cannot be hidden.
