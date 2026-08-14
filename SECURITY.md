# Security policy

## Reporting a vulnerability

Do not open a public issue for a vulnerability or suspected credential exposure. Use the repository's private GitHub Security Advisory reporting channel. Include affected versions, reproduction steps, impact, and any known mitigations.

If a secret may have entered Git history, logs, an analysis artifact, or a promoted data release, treat it as compromised: stop publication, revoke or rotate it at the provider, preserve evidence without repeating the value, and audit generated artifacts before resuming.

## Supported versions

Until versioned releases are published, only the latest commit on the repository's default branch is supported.

## Security boundaries

- Credentials are accepted only through environment variables or an approved secret store.
- Raw and promoted releases are immutable.
- Archive extraction rejects traversal, symlinks, devices, and unsafe members.
- Official sources and explicitly configured licensed APIs are authoritative; mirrors are not accepted as silent fallbacks.
- Provider-licensed data is not redistributed unless its terms explicitly permit it.
