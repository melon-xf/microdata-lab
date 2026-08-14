# NLRB data access assessment

Checked against the official [NLRB case-search page](https://www.nlrb.gov/search/case)
on August 14, 2026.

## Decision

Keep the adapter planned. The official page now advertises a **Download CSV**
control, so the earlier claim that no download exists is obsolete. The public
surface still does not document a stable bulk endpoint, snapshot semantics,
schema contract, or rate limits. The visible HTML result list is paginated and
is not a sound acquisition substitute.

## What is available

The case-search result exposes case number, filing date, status, location,
region, and case detail links. Direct requests for Drupal structured formats
have been rejected by the site's web-application firewall. The former
`/reports/graphs-data` route now returns a 404 page.

## Promotion requirements

Do not mark the adapter implemented until an official download can be shown to:

1. work without an interactive account or browser session;
2. return a complete, bounded snapshot from a stable URL;
3. carry terms that permit the intended local use and published aggregates;
4. expose a schema and official row-count or field benchmark; and
5. survive a repeat download with deterministic validation.

Until then, use the BLS adapters for supported labor-statistics questions.
