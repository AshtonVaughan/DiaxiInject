"""DiaxiInject CLI - click-based command-line interface with rich output."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from diaxiinject.config import DiaxiConfig, delete_key, get_key, load_keys, save_key

console = Console()

# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------

def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


# ------------------------------------------------------------------
# CLI group
# ------------------------------------------------------------------

@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
@click.version_option(version="0.1.0", prog_name="diaxiinject")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """DiaxiInject - LLM safety assessment toolkit."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    _setup_logging(verbose)


# ------------------------------------------------------------------
# campaign
# ------------------------------------------------------------------

@cli.command()
@click.option("--target", "-t", required=True, help="Target provider (e.g. openai, anthropic, google).")
@click.option("--model", "-m", default=None, help="Target model name.")
@click.option("--budget", "-b", type=float, default=50.0, help="Daily budget in AUD.")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True), default=None, help="YAML config file.")
@click.pass_context
def campaign(
    ctx: click.Context,
    target: str,
    model: str | None,
    budget: float,
    config_path: str | None,
) -> None:
    """Run a full multi-phase attack campaign."""
    from diaxiinject.campaign import CampaignController

    console.print(Panel.fit(
        f"[bold cyan]DiaxiInject Campaign[/bold cyan]\n"
        f"Target: [yellow]{target}[/yellow]  "
        f"Budget: [green]${budget:.2f} AUD[/green]",
        border_style="cyan",
    ))

    # Load config
    if config_path:
        config = DiaxiConfig.from_yaml(config_path)
    else:
        config = DiaxiConfig()

    config.campaign.target = target
    config.campaign.daily_budget_aud = budget
    config.verbose = ctx.obj.get("verbose", False)

    try:
        controller = CampaignController()
        stats = asyncio.run(controller.run(config))
    except KeyboardInterrupt:
        console.print("\n[yellow]Campaign interrupted by user.[/yellow]")
        sys.exit(1)
    except Exception as exc:
        console.print(f"[red bold]Campaign failed:[/red bold] {exc}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        sys.exit(1)

    _display_stats(stats)


# ------------------------------------------------------------------
# attack
# ------------------------------------------------------------------

@cli.command()
@click.option("--target", "-t", required=True, help="Target provider.")
@click.option("--model", "-m", default=None, help="Target model name.")
@click.option("--type", "-T", "attack_type", required=True,
              type=click.Choice(["single_turn", "pair", "tap", "crescendo", "genetic"]),
              help="Orchestrator type.")
@click.option("--objective", "-o", required=True, help="Attack objective text.")
@click.option("--max-iterations", type=int, default=20, help="Max iterations (PAIR/Genetic).")
@click.option("--threshold", type=float, default=0.7, help="Success threshold.")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True), default=None, help="YAML config file.")
@click.pass_context
def attack(
    ctx: click.Context,
    target: str,
    model: str | None,
    attack_type: str,
    objective: str,
    max_iterations: int,
    threshold: float,
    config_path: str | None,
) -> None:
    """Run a single attack with a specific orchestrator."""
    from diaxiinject.attacks.orchestrators import (
        CrescendoOrchestrator,
        GeneticOrchestrator,
        PAIROrchestrator,
        SingleTurnOrchestrator,
        TAPOrchestrator,
    )
    from diaxiinject.attacks.probes.library import ProbeLibrary
    from diaxiinject.attacks.scoring.pipeline import ScoringPipeline
    from diaxiinject.config import DiaxiConfig
    from diaxiinject.providers.hub import ProviderHub

    console.print(Panel.fit(
        f"[bold cyan]DiaxiInject Attack[/bold cyan]\n"
        f"Type: [yellow]{attack_type}[/yellow]  Target: [yellow]{target}[/yellow]\n"
        f"Objective: [dim]{objective[:80]}[/dim]",
        border_style="cyan",
    ))

    if config_path:
        config = DiaxiConfig.from_yaml(config_path)
    else:
        config = DiaxiConfig()
    config.campaign.target = target
    hub = ProviderHub()
    target_adapter = hub.get_target(provider=target, model=model, api_key=config.campaign.target_api_key or None)
    scorer = ScoringPipeline()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Running {attack_type}...", total=None)

            if attack_type == "single_turn":
                library = ProbeLibrary()
                probes = library.get_all()
                orch = SingleTurnOrchestrator()
                results = asyncio.run(
                    orch.run(probes, target_adapter, scorer, objective=objective)
                )
                progress.update(task, completed=True)
                _display_results(results)

            elif attack_type == "pair":
                attacker = hub.get_attacker(config.attacker)
                orch_pair = PAIROrchestrator()
                result = asyncio.run(orch_pair.run(
                    objective, target_adapter, attacker, scorer,
                    max_iterations=max_iterations, threshold=threshold,
                ))
                progress.update(task, completed=True)
                if result:
                    _display_results([result])
                else:
                    console.print("[yellow]PAIR did not achieve bypass.[/yellow]")

            elif attack_type == "tap":
                attacker = hub.get_attacker(config.attacker)
                orch_tap = TAPOrchestrator()
                result = asyncio.run(
                    orch_tap.run(objective, target_adapter, attacker, scorer)
                )
                progress.update(task, completed=True)
                if result:
                    _display_results([result])
                else:
                    console.print("[yellow]TAP did not achieve bypass.[/yellow]")

            elif attack_type == "crescendo":
                attacker = hub.get_attacker(config.attacker)
                orch_cresc = CrescendoOrchestrator()
                result = asyncio.run(orch_cresc.run(
                    objective, target_adapter, attacker, scorer,
                    threshold=threshold,
                ))
                progress.update(task, completed=True)
                if result:
                    _display_results([result])
                else:
                    console.print("[yellow]Crescendo did not achieve bypass.[/yellow]")

            elif attack_type == "genetic":
                attacker = hub.get_attacker(config.attacker)
                orch_gen = GeneticOrchestrator()
                result = asyncio.run(orch_gen.run(
                    objective, target_adapter, attacker, scorer,
                    seed_probes=[objective],
                    generations=max_iterations,
                ))
                progress.update(task, completed=True)
                if result:
                    _display_results([result])
                else:
                    console.print("[yellow]Genetic evolution did not achieve bypass.[/yellow]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Attack interrupted.[/yellow]")
        sys.exit(1)
    except Exception as exc:
        console.print(f"[red bold]Attack failed:[/red bold] {exc}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        sys.exit(1)


# ------------------------------------------------------------------
# probe
# ------------------------------------------------------------------

@cli.command()
@click.option("--target", "-t", required=True, help="Target provider.")
@click.option("--model", "-m", default=None, help="Target model name.")
@click.option("--probe-id", "-p", required=True, help="Probe ID from the library.")
@click.option("--mutators", default=None, help="Comma-separated mutator names.")
@click.pass_context
def probe(
    ctx: click.Context,
    target: str,
    model: str | None,
    probe_id: str,
    mutators: str | None,
) -> None:
    """Send a single probe to the target."""
    from diaxiinject.attacks.mutators.chain import MutatorChain
    from diaxiinject.attacks.orchestrators.single_turn import SingleTurnOrchestrator
    from diaxiinject.attacks.probes.library import ProbeLibrary
    from diaxiinject.attacks.scoring.pipeline import ScoringPipeline
    from diaxiinject.providers.hub import ProviderHub

    hub = ProviderHub()
    target_adapter = hub.get_target(provider=target, model=model, api_key=None)
    scorer = ScoringPipeline()
    library = ProbeLibrary()

    # Find the probe
    all_probes = library.get_all()
    matched = [p for p in all_probes if p.id == probe_id]
    if not matched:
        console.print(f"[red]Probe '{probe_id}' not found.[/red]")
        console.print("Available probes:")
        for p in all_probes[:20]:
            console.print(f"  [dim]{p.id}[/dim] - {p.name}")
        sys.exit(1)

    the_probe = matched[0]
    mutator_list = mutators.split(",") if mutators else None
    chain = MutatorChain() if mutator_list else None

    console.print(Panel.fit(
        f"[bold cyan]Sending Probe[/bold cyan]\n"
        f"ID: [yellow]{the_probe.id}[/yellow]  Name: {the_probe.name}\n"
        f"Target: [yellow]{target}[/yellow]"
        + (f"  Mutators: [magenta]{mutators}[/magenta]" if mutators else ""),
        border_style="cyan",
    ))

    try:
        orch = SingleTurnOrchestrator()
        results = asyncio.run(orch.run(
            [the_probe], target_adapter, scorer,
            mutator_chain=chain, mutators=mutator_list,
        ))
        _display_results(results)
    except Exception as exc:
        console.print(f"[red bold]Probe failed:[/red bold] {exc}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        sys.exit(1)


# ------------------------------------------------------------------
# evolve
# ------------------------------------------------------------------

@cli.command()
@click.option("--target", "-t", required=True, help="Target provider.")
@click.option("--model", "-m", default=None, help="Target model name.")
@click.option("--objective", "-o", required=True, help="Attack objective.")
@click.option("--generations", "-g", type=int, default=50, help="Number of generations.")
@click.option("--population", type=int, default=20, help="Population size.")
@click.option("--mutation-rate", type=float, default=0.3, help="Mutation rate.")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True), default=None, help="YAML config file.")
@click.pass_context
def evolve(
    ctx: click.Context,
    target: str,
    model: str | None,
    objective: str,
    generations: int,
    population: int,
    mutation_rate: float,
    config_path: str | None,
) -> None:
    """Run genetic evolution to find optimal attack prompts."""
    from diaxiinject.attacks.orchestrators.genetic import GeneticOrchestrator
    from diaxiinject.attacks.scoring.pipeline import ScoringPipeline
    from diaxiinject.config import DiaxiConfig
    from diaxiinject.providers.hub import ProviderHub

    console.print(Panel.fit(
        f"[bold cyan]DiaxiInject Genetic Evolution[/bold cyan]\n"
        f"Target: [yellow]{target}[/yellow]  "
        f"Generations: [green]{generations}[/green]  "
        f"Population: [green]{population}[/green]",
        border_style="cyan",
    ))

    if config_path:
        config = DiaxiConfig.from_yaml(config_path)
    else:
        config = DiaxiConfig()
    config.campaign.target = target
    hub = ProviderHub()
    target_adapter = hub.get_target(provider=target, model=model, api_key=config.campaign.target_api_key or None)
    attacker = hub.get_attacker(config.attacker)
    scorer = ScoringPipeline()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Evolving...", total=generations)
            orch = GeneticOrchestrator()
            result = asyncio.run(orch.run(
                objective=objective,
                target=target_adapter,
                attacker=attacker,
                scorer=scorer,
                seed_probes=[objective],
                population_size=population,
                generations=generations,
                mutation_rate=mutation_rate,
            ))
            progress.update(task, completed=generations)

        if result:
            _display_results([result])
        else:
            console.print("[yellow]Evolution did not find a successful attack.[/yellow]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Evolution interrupted.[/yellow]")
        sys.exit(1)
    except Exception as exc:
        console.print(f"[red bold]Evolution failed:[/red bold] {exc}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        sys.exit(1)


# ------------------------------------------------------------------
# report
# ------------------------------------------------------------------

@cli.command()
@click.option("--campaign-id", "-c", required=True, help="Campaign ID to generate report for.")
@click.option("--format", "-f", "fmt",
              type=click.Choice(["hackerone", "msrc", "bugcrowd"]),
              default="hackerone", help="Report format.")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path.")
@click.pass_context
def report(
    ctx: click.Context,
    campaign_id: str,
    fmt: str,
    output: str | None,
) -> None:
    """Generate a vulnerability report from campaign findings."""
    from diaxiinject.evidence.reporters.hackerone import HackerOneReporter
    from diaxiinject.evidence.reporters.msrc import MSRCReporter
    from diaxiinject.memory.database import MemoryDatabase

    db = MemoryDatabase()

    # Retrieve findings from the database
    try:
        stats = db.get_campaign_stats(campaign_id)
    except Exception as exc:
        console.print(f"[red]Failed to load campaign {campaign_id}:[/red] {exc}")
        sys.exit(1)

    console.print(Panel.fit(
        f"[bold cyan]Generating Report[/bold cyan]\n"
        f"Campaign: [yellow]{campaign_id}[/yellow]  Format: [green]{fmt}[/green]",
        border_style="cyan",
    ))

    reporters = {
        "hackerone": HackerOneReporter,
        "msrc": MSRCReporter,
    }

    reporter_cls = reporters.get(fmt)
    if reporter_cls is None:
        console.print(f"[yellow]Format '{fmt}' is not yet implemented. Available: hackerone, msrc[/yellow]")
        sys.exit(1)

    reporter_instance = reporter_cls()
    console.print(f"[green]Report generator ready ({fmt}). "
                  f"Use with findings from campaign {campaign_id}.[/green]")

    if output:
        console.print(f"[green]Report would be written to: {output}[/green]")


# ------------------------------------------------------------------
# stats
# ------------------------------------------------------------------

@cli.command()
@click.option("--campaign-id", "-c", required=True, help="Campaign ID.")
@click.pass_context
def stats(ctx: click.Context, campaign_id: str) -> None:
    """Display statistics for a campaign."""
    from diaxiinject.memory.database import MemoryDatabase

    db = MemoryDatabase()

    try:
        campaign_stats = db.get_campaign_stats(campaign_id)
    except Exception as exc:
        console.print(f"[red]Failed to load stats for {campaign_id}:[/red] {exc}")
        sys.exit(1)

    _display_stats(campaign_stats)


# ------------------------------------------------------------------
# Display helpers
# ------------------------------------------------------------------

def _display_results(results: list) -> None:
    """Render attack results as a rich table."""
    if not results:
        console.print("[yellow]No results to display.[/yellow]")
        return

    table = Table(
        title="Attack Results",
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
    )
    table.add_column("Probe", style="cyan", max_width=30)
    table.add_column("Orchestrator", style="yellow")
    table.add_column("Score", justify="right")
    table.add_column("Success", justify="center")
    table.add_column("Turn", justify="right")
    table.add_column("Response (excerpt)", max_width=50, style="dim")
    table.add_column("Cost", justify="right", style="green")

    for r in results:
        probe_name = getattr(r.probe, "name", getattr(r.probe, "id", "?"))
        score_val = r.score.overall
        if score_val >= 0.7:
            score_str = f"[bold green]{score_val:.3f}[/bold green]"
        elif score_val >= 0.3:
            score_str = f"[yellow]{score_val:.3f}[/yellow]"
        else:
            score_str = f"[red]{score_val:.3f}[/red]"

        success_str = "[bold green]YES[/bold green]" if r.score.is_success else "[red]NO[/red]"
        excerpt = r.response.text[:60].replace("\n", " ") if r.response.text else ""

        table.add_row(
            str(probe_name)[:30],
            r.orchestrator,
            score_str,
            success_str,
            str(r.turn_number),
            excerpt,
            f"${r.cost_aud:.4f}",
        )

    console.print(table)

    # Summary line
    successes = sum(1 for r in results if r.score.is_success)
    total_cost = sum(r.cost_aud for r in results)
    best = max(results, key=lambda r: r.score.overall)

    console.print(
        f"\n[bold]Summary:[/bold] {len(results)} attacks, "
        f"[green]{successes} successes[/green], "
        f"best score [cyan]{best.score.overall:.3f}[/cyan], "
        f"total cost [green]${total_cost:.4f} AUD[/green]"
    )


def _display_stats(campaign_stats) -> None:
    """Render campaign stats as a rich panel with tables."""
    # Main stats panel
    success_rate = (
        (campaign_stats.successful_attacks / campaign_stats.total_attacks * 100)
        if campaign_stats.total_attacks > 0
        else 0.0
    )

    stats_text = (
        f"[bold]Campaign:[/bold] {campaign_stats.campaign_id}\n"
        f"[bold]Target:[/bold] {campaign_stats.target}\n"
        f"[bold]Total Attacks:[/bold] {campaign_stats.total_attacks}\n"
        f"[bold]Successful:[/bold] [green]{campaign_stats.successful_attacks}[/green] "
        f"({success_rate:.1f}%)\n"
        f"[bold]Findings:[/bold] [cyan]{campaign_stats.findings}[/cyan]\n"
        f"[bold]Total Cost:[/bold] [green]${campaign_stats.total_cost_aud:.2f} AUD[/green]\n"
        f"[bold]Runtime:[/bold] {campaign_stats.runtime_seconds:.1f}s"
    )
    console.print(Panel(stats_text, title="Campaign Statistics", border_style="cyan"))

    # Orchestrator breakdown
    if campaign_stats.success_by_orchestrator:
        table = Table(
            title="Success by Orchestrator",
            show_header=True,
            header_style="bold magenta",
            border_style="dim",
        )
        table.add_column("Orchestrator", style="yellow")
        table.add_column("Successes", justify="right", style="green")

        for orch_name, count in sorted(
            campaign_stats.success_by_orchestrator.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            table.add_row(orch_name, str(count))
        console.print(table)

    # Category breakdown
    if campaign_stats.attacks_by_category:
        table = Table(
            title="Attacks by Category",
            show_header=True,
            header_style="bold magenta",
            border_style="dim",
        )
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right")

        for cat, count in sorted(
            campaign_stats.attacks_by_category.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            table.add_row(cat, str(count))
        console.print(table)


# ------------------------------------------------------------------
# keys
# ------------------------------------------------------------------

@cli.group()
def keys() -> None:
    """Manage saved API keys for target providers."""


@keys.command("set")
@click.argument("provider")
@click.argument("api_key")
def keys_set(provider: str, api_key: str) -> None:
    """Save an API key for PROVIDER.

    \b
    Examples:
      diaxiinject keys set anthropic sk-ant-api03-...
      diaxiinject keys set openai sk-...
      diaxiinject keys set google AIza...
    """
    save_key(provider, api_key)
    masked = api_key[:8] + "..." + api_key[-4:]
    console.print(f"[green]Saved[/green] [cyan]{provider}[/cyan] key: [dim]{masked}[/dim]")


@keys.command("list")
def keys_list() -> None:
    """List all saved provider keys (masked)."""
    all_keys = load_keys()
    if not all_keys:
        console.print("[yellow]No keys saved. Use:[/yellow] diaxiinject keys set <provider> <key>")
        return

    table = Table(show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("Provider", style="cyan")
    table.add_column("Key (masked)")
    table.add_column("Status")

    for provider, key in sorted(all_keys.items()):
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        table.add_row(provider, masked, "[green]set[/green]")

    console.print(table)


@keys.command("delete")
@click.argument("provider")
def keys_delete(provider: str) -> None:
    """Remove the saved key for PROVIDER."""
    if delete_key(provider):
        console.print(f"[green]Deleted[/green] key for [cyan]{provider}[/cyan]")
    else:
        console.print(f"[yellow]No key found for '{provider}'[/yellow]")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
