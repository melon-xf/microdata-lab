# Data lake storage and recovery

`MICRODATA_ROOT` controls the data-lake location. If it is unset, Microdata Lab uses the platform data directory. Never commit a host-specific path.

## Measure before downloading

Measure the actual lake and filesystem before a backfill. Release sizes vary by year, and upstream revisions are additive.

```bash
uv run microdata status
uv run microdata scrub
du -sh "${MICRODATA_ROOT:-${XDG_DATA_HOME:-$HOME/.local/share}/microdata-lab}"
df -h "${MICRODATA_ROOT:-${XDG_DATA_HOME:-$HOME/.local/share}/microdata-lab}"
```

Provider-reported `Content-Length` is an acquisition check, not a storage forecast. Use post-download local bytes when planning another batch.

## Retention

- `releases/` is immutable. A changed upstream file creates a new revision.
- Original artifacts stay with each release. Normalized files do not replace them.
- `current/` and `catalog/` are rebuildable indexes, not authoritative copies of data.
- `incoming/` contains unique active runs. Successful promotion removes the matching run atomically.
- `quarantine/` stays in place until a reviewed, targeted cleanup removes a named run.
- Cleanup must identify exact run IDs. Never use a wildcard over `raw/`, `releases/`, or the data root.

## Capacity rules

- Warn when free space falls below 20%.
- Block historical backfills below 10% free space.
- Reserve at least 25% above the measured backfill size for later upstream revisions.
- Re-measure after the first promoted release from a new adapter.
- Treat an unmeasured source as unknown, not zero.

## Integrity

Every promoted artifact has a SHA-256 checksum. Run:

```bash
uv run microdata validate <source>
uv run microdata scrub
```

`validate` checks the current release for one source. `scrub` recalculates artifact and normalized-asset hashes across preserved revisions, then checks release digests, manifest identity, byte counts, path containment, and current-pointer agreement.

After restoring data, rebuild the catalog from current manifests. Restore in this order:

1. immutable releases;
2. current pointers;
3. catalog;
4. derived analyses.

Never reconstruct an original artifact from normalized Parquet.

## Backups

A backup target must preserve file content, relative paths, and every immutable revision.

1. Replicate a promoted release only after validation succeeds.
2. Back up current pointers, release manifests, and repository configuration with the releases.
3. Encrypt backups that contain licensed-provider files.
4. Run a restore drill into a separate temporary root and validate hashes there.
5. Record successful replication and restore times without recording credentials.
