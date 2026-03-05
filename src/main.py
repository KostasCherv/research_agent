"""CLI entry point using Typer + Rich."""

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(
    name="research-agent",
    help="Multi-step LangGraph research agent — search, retrieve, summarize, report.",
    add_completion=False,
)
console = Console()


@app.command()
def search(
    query: str = typer.Argument(..., help="Research query to investigate."),
    vector_store: bool = typer.Option(
        False, "--vector-store", "-v", help="Persist the report to ChromaDB."
    ),
    output: str = typer.Option(
        "", "--output", "-o", help="Optional file path to save the markdown report."
    ),
):
    """Run the full research pipeline for a query and print the report."""
    from src.graph.graph import build_graph

    console.print(Panel(f"[bold cyan]Research Agent[/bold cyan]\n[dim]{query}[/dim]"))

    initial_state = {
        "query": query,
        "use_vector_store": vector_store,
        "error": None,
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Running research pipeline…", total=None)
        graph = build_graph()
        final_state = None
        for event in graph.stream(initial_state):
            for node_name in event:
                progress.update(task, description=f"[cyan]{node_name}[/cyan] ✓")
            final_state = event

    if not final_state:
        console.print("[red]Pipeline returned no state.[/red]")
        raise typer.Exit(code=1)

    # Grab the last state values from the final event dict
    state = list(final_state.values())[-1]

    error = state.get("error")
    if error:
        console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1)

    report = state.get("report", "")
    if not report:
        console.print("[yellow]Warning:[/yellow] Report is empty.")
        raise typer.Exit(code=1)

    console.print("\n")
    console.print(Markdown(report))

    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(report)
        console.print(f"\n[green]Report saved to[/green] {output}")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host."),
    port: int = typer.Option(8000, help="Bind port."),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev mode)."),
):
    """Start the FastAPI server."""
    import uvicorn

    console.print(
        Panel(f"[bold cyan]Research Agent API[/bold cyan]\nhttp://{host}:{port}")
    )
    uvicorn.run(
        "src.api.endpoints:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    app()
