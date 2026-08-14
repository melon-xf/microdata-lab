from __future__ import annotations

import json
from functools import partial
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from microdata_lab.adapters import enabled_source_slugs, get_adapter
from microdata_lab.analysis_checks import check_all_analyses
from microdata_lab.backfill import plan_backfill, reset_backfill_state, run_backfill
from microdata_lab.bench import bench_to_json, run_bench
from microdata_lab.catalog import rebuild_catalog, search_catalog
from microdata_lab.comparability import comparability_to_json, run_comparability
from microdata_lab.config import initialize_data_root, load_source_registry, resolve_data_root
from microdata_lab.integrity import scrub_data_lake
from microdata_lab.storage import sync_release, validate_current_release
from microdata_lab.visualization import render_interactive, render_static
from microdata_lab.viz_gates import run_all_gates, store_golden_static

app = typer.Typer(no_args_is_help=True, help="Automated public microdata operations.")
catalog_app = typer.Typer(no_args_is_help=True, help="Build and search the local catalog.")
viz_app = typer.Typer(no_args_is_help=True, help="Render publication and interactive graphics.")
app.add_typer(catalog_app, name="catalog")
app.add_typer(viz_app, name="viz")
console = Console()


def _print_progress(message: str, *, prefix: str) -> None:
    console.print(f"• [{prefix}] {message}")


@app.command()
def check_analysis() -> None:
    """Validate every analysis directory against the AGENTS.md contract."""
    results = check_all_analyses(Path("analyses"))
    if not results:
        console.print("[yellow]No analysis directories found under analyses/[/yellow]")
        return
    failed = 0
    for result in results:
        if result.passed:
            console.print(f"[green]✓[/green] {result.analysis}")
            continue
        failed += 1
        console.print(f"[red]✗ {result.analysis}[/red]")
        for issue in result.issues:
            console.print(f"   [red]{issue.severity}[/red] {issue.message}")
    if failed:
        raise typer.Exit(1)
    console.print(f"[bold green]{len(results)} analyses passed the contract.[/bold green]")


@app.command()
def bench(
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Re-run every adapter's benchmark gates against current releases."""
    root = resolve_data_root()
    rows = run_bench(root)
    if as_json:
        console.print(bench_to_json(rows))
        return
    table = Table("Source", "Year", "Release", "Checks", "Benchmark")
    for row in rows:
        bench_status = (
            "[green]PASS[/green]"
            if row.benchmark_passed
            else "[red]FAIL[/red]"
            if row.benchmark_passed is False
            else "[yellow]n/a[/yellow]"
        )
        table.add_row(
            row.survey,
            str(row.year),
            row.release_id,
            f"{row.passed_checks}/{row.checks}",
            bench_status,
        )
    console.print(table)
    if any(row.benchmark_passed is False for row in rows):
        raise typer.Exit(1)


@app.command()
def comparability(
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Run cross-source comparability checks on current releases."""
    root = resolve_data_root()
    rows = run_comparability(root)
    if as_json:
        console.print(comparability_to_json(rows))
        return
    table = Table("Check", "Sources", "Value A", "Value B", "Diff", "Tolerance", "Result")
    for row in rows:
        if row.skipped:
            result = "[yellow]SKIP[/yellow]"
        elif row.passed:
            result = "[green]PASS[/green]"
        else:
            result = "[red]FAIL[/red]"
        table.add_row(
            row.check,
            f"{row.source_a} vs {row.source_b}",
            f"{row.value_a:.4g}",
            f"{row.value_b:.4g}",
            f"{row.difference:.4f}",
            row.tolerance,
            result,
        )
    console.print(table)
    for row in rows:
        if row.note:
            console.print(f"[dim]{row.check}: {row.note}[/dim]")
    if any(not row.skipped and not row.passed for row in rows):
        raise typer.Exit(1)


@app.command()
def backfill(
    source: list[str] = typer.Option(None, "--source", help="Restrict to one or more sources."),
    delay: float = typer.Option(5.0, help="Seconds to wait between requests."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan without fetching."),
    no_resume: bool = typer.Option(False, "--no-resume", help="Ignore saved progress."),
    reset: bool = typer.Option(False, "--reset", help="Clear saved progress and exit."),
) -> None:
    """Backfill missing historical years with rate limiting and resume."""
    root = resolve_data_root()
    if reset:
        reset_backfill_state(root)
        console.print("[green]Backfill state cleared.[/green]")
        return
    plan = plan_backfill(root)
    if source:
        plan = {slug: years for slug, years in plan.items() if slug in source}
    if not plan:
        console.print("[green]No missing years; the lake is fully backfilled.[/green]")
        return
    for slug, years in plan.items():
        preview = ", ".join(str(y) for y in years[:6])
        suffix = "…" if len(years) > 6 else ""
        console.print(f"[bold]{slug}[/bold]: missing {len(years)} year(s) — {preview}{suffix}")
    if dry_run:
        console.print("[yellow]Dry run; nothing fetched.[/yellow]")
        return
    results = run_backfill(root, delay=delay, sources=source, resume=not no_resume)
    table = Table("Source", "Year", "Status", "Release")
    for r in results:
        color = {"promoted": "green", "already-current": "yellow", "failed": "red"}[r.status]
        table.add_row(
            r.source, str(r.year), f"[{color}]{r.status}[/{color}]", r.release_id or r.error or ""
        )
    console.print(table)
    if any(r.status == "failed" for r in results):
        raise typer.Exit(1)


@app.command()
def sources() -> None:
    """List source adapters and implementation status."""
    table = Table("Source", "Survey", "Agency", "Access", "Status")
    for slug, source in load_source_registry().items():
        table.add_row(
            slug,
            source.name,
            source.agency,
            source.access,
            "ready" if source.implemented and source.enabled else "planned",
        )
    console.print(table)


@app.command()
def discover(
    survey: str = typer.Argument(..., help="Survey adapter slug."),
    year: int | None = typer.Option(None, help="Release year; defaults to latest discovered."),
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Discover a complete release from the official landing page."""
    with get_adapter(survey) as adapter:
        release = adapter.discover(year=year)
    if as_json:
        console.print_json(release.model_dump_json())
        return
    table = Table("Role", "Filename", "Official URL")
    for artifact in release.artifacts:
        table.add_row(str(artifact.role), artifact.filename, str(artifact.url))
    console.print(f"[bold]{release.survey.upper()} {release.year}[/bold]")
    console.print(table)


@app.command()
def sync(
    survey: str | None = typer.Argument(None, help="Survey adapter slug; omit with --all."),
    all_sources: bool = typer.Option(False, "--all", help="Synchronize every enabled source."),
    year: int | None = typer.Option(None, help="Release year; defaults to latest discovered."),
    backfill: bool = typer.Option(False, help="Synchronize every discoverable release year."),
    from_year: int | None = typer.Option(None, help="Backfill lower year bound, inclusive."),
    to_year: int | None = typer.Option(None, help="Backfill upper year bound, inclusive."),
    data_root: Path | None = typer.Option(None, help="Override MICRODATA_ROOT."),
) -> None:
    """Discover, download, validate, document, and atomically promote a release."""
    if (survey is None) == (not all_sources):
        raise typer.BadParameter("Provide one survey slug or --all, but not both")
    if year is not None and (all_sources or backfill):
        raise typer.BadParameter("--year cannot be combined with --all or --backfill")
    if (from_year is not None or to_year is not None) and not backfill:
        raise typer.BadParameter("--from-year and --to-year require --backfill")

    root = resolve_data_root(data_root)
    slugs = enabled_source_slugs() if all_sources else [str(survey)]
    failures: list[str] = []
    changed = False
    for slug in slugs:
        try:
            with get_adapter(slug) as adapter:
                years: list[int | None]
                if backfill:
                    years = [
                        candidate
                        for candidate in adapter.available_years()
                        if (from_year is None or candidate >= from_year)
                        and (to_year is None or candidate <= to_year)
                    ]
                else:
                    years = [year]
                if not years:
                    raise ValueError(f"No {slug} releases matched the requested year range")
                for selected_year in years:
                    release = adapter.discover(year=selected_year)
                    result = sync_release(
                        release,
                        root,
                        adapter=adapter,
                        client=adapter.download_client(),
                        progress=partial(_print_progress, prefix=slug),
                    )
                    changed = changed or result.changed
                    state = "promoted" if result.changed else "already current"
                    console.print(f"[bold green]{result.manifest.release_id} {state}[/bold green]")
                    console.print(result.release_path)
        except Exception as error:
            failures.append(f"{slug}: {error}")
            console.print(f"[bold red]Failed {slug}:[/bold red] {error}")

    if changed:
        counts = rebuild_catalog(root)
        console.print(
            f"Cataloged {counts.releases} releases, {counts.variables} variables, "
            f"and {counts.documents} documents."
        )
    if failures:
        raise typer.Exit(code=1)


@app.command()
def validate(
    survey: str = typer.Argument(..., help="Survey slug."),
    data_root: Path | None = typer.Option(None, "--data-root"),
) -> None:
    """Re-run structural validators against the current immutable release."""
    root = resolve_data_root(data_root)
    initialize_data_root(root)
    with get_adapter(survey) as adapter:
        manifest, release_path = validate_current_release(root, survey, adapter=adapter)
    if not manifest.validation.passed:
        console.print_json(manifest.validation.model_dump_json())
        raise typer.Exit(code=1)
    console.print(
        f"[bold green]{manifest.release_id} passed "
        f"{len(manifest.validation.checks)} checks[/bold green]"
    )
    console.print(release_path)


@app.command()
def scrub(
    data_root: Path | None = typer.Option(None, help="Override MICRODATA_ROOT."),
) -> None:
    """Recalculate hashes and verify every preserved release and current pointer."""
    root = resolve_data_root(data_root)
    summary = scrub_data_lake(root)
    style = "bold green" if summary.passed else "bold red"
    console.print(f"[{style}]Integrity scrub: {'passed' if summary.passed else 'failed'}[/{style}]")
    console.print(
        f"Releases={summary.releases_checked} pointers={summary.pointers_checked} "
        f"files={summary.files_checked} bytes={summary.bytes_checked}"
    )
    for error in summary.errors:
        console.print(f"[red]ERROR[/red] {error}")
    if not summary.passed:
        raise typer.Exit(code=1)


@app.command()
def status(
    data_root: Path | None = typer.Option(None, help="Override MICRODATA_ROOT."),
) -> None:
    """Show promoted releases."""
    root = resolve_data_root(data_root)
    initialize_data_root(root)
    pointers = sorted((root / "current").glob("*.json"))
    if not pointers:
        console.print("No promoted releases.")
        return
    table = Table("Survey", "Year", "Release", "Path")
    for pointer_path in pointers:
        pointer = json.loads(pointer_path.read_text())
        table.add_row(
            str(pointer["survey"]),
            str(pointer["year"]),
            str(pointer["release_id"]),
            str(pointer["release_path"]),
        )
    console.print(table)


@catalog_app.command("rebuild")
def catalog_rebuild(
    data_root: Path | None = typer.Option(None, help="Override MICRODATA_ROOT."),
) -> None:
    """Rebuild the DuckDB catalog from promoted releases."""
    root = resolve_data_root(data_root)
    counts = rebuild_catalog(root)
    console.print(
        f"Cataloged {counts.releases} releases, {counts.variables} variables, "
        f"and {counts.documents} documents."
    )


@catalog_app.command("search")
def catalog_search(
    query: str = typer.Argument(..., help="Variable or documentation query."),
    data_root: Path | None = typer.Option(None, help="Override MICRODATA_ROOT."),
    limit: int = typer.Option(20, min=1, max=200),
) -> None:
    """Search variable names and official documentation."""
    root = resolve_data_root(data_root)
    results = search_catalog(root, query, limit=limit)
    if not results:
        console.print("No catalog matches.")
        raise typer.Exit()
    for result in results:
        if result["kind"] == "variable":
            console.print(
                f"[cyan]variable[/cyan] {result['survey']} {result['year']} "
                f"[bold]{result['name']}[/bold] ({result['data_type']})"
            )
        else:
            console.print(
                f"[magenta]document[/magenta] {result['survey']} {result['year']} "
                f"{result['role']}: {result['snippet']}"
            )


@viz_app.command("static")
def viz_static(
    data: Path = typer.Argument(..., exists=True, readable=True),
    config: Path = typer.Argument(..., exists=True, readable=True),
    output: Path = typer.Argument(...),
) -> None:
    """Render a publication PNG using the locked R/ggplot environment."""
    render_static(data, config, output)
    console.print(f"[bold green]Rendered static chart:[/bold green] {output.resolve()}")


@viz_app.command("interactive")
def viz_interactive(
    data: Path = typer.Argument(..., exists=True, readable=True),
    config: Path = typer.Argument(..., exists=True, readable=True),
    output: Path = typer.Argument(...),
) -> None:
    """Render a standalone responsive Observable Plot HTML artifact."""
    render_interactive(data, config, output)
    console.print(f"[bold green]Rendered interactive chart:[/bold green] {output.resolve()}")


@viz_app.command("gates")
def viz_gates(
    analysis: str | None = typer.Option(None, help="Restrict to one analysis directory."),
) -> None:
    """Run deterministic re-render and golden-image gates for all analyses."""
    root = Path("analyses")
    results = (
        run_all_gates(root)
        if analysis is None
        else run_all_gates(root / analysis)
        if (root / analysis).is_dir()
        else []
    )
    if not results:
        console.print("[yellow]No analyses matched for viz gates.[/yellow]")
        return
    failed = 0
    for result in results:
        mark = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
        if not result.passed:
            failed += 1
        console.print(
            f"{mark} {result.analysis} {result.renderer} {result.gate}"
            + (f" — {result.detail}" if result.detail else "")
        )
    if failed:
        raise typer.Exit(1)
    console.print(f"[bold green]{len(results)} viz gates passed.[/bold green]")


@viz_app.command("golden-store")
def viz_golden_store(
    data: Path = typer.Argument(..., exists=True, readable=True),
    config: Path = typer.Argument(..., exists=True, readable=True),
) -> None:
    """Store (or refresh) the golden baseline for one analysis figure."""
    result = store_golden_static(data, config)
    console.print(f"[green]{result.detail}[/green]")


if __name__ == "__main__":  # pragma: no cover
    app()
