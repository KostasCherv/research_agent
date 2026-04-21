"""CLI entry point using Typer + Rich."""

import asyncio

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
    from src.observability import end_workflow_run, start_workflow_run

    console.print(Panel(f"[bold cyan]Research Agent[/bold cyan]\n[dim]{query}[/dim]"))

    initial_state = {
        "query": query,
        "use_vector_store": vector_store,
        "error": None,
    }

    trace_status = "success"
    trace_error: str | None = None

    with start_workflow_run(
        entrypoint="cli",
        query=query,
        use_vector_store=vector_store,
    ) as trace_ctx:
        try:
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
                trace_status = "error"
                trace_error = "Pipeline returned no state."
                console.print("[red]Pipeline returned no state.[/red]")
                raise typer.Exit(code=1)

            # Grab the last state values from the final event dict
            state = list(final_state.values())[-1]

            error = state.get("error")
            if error:
                trace_status = "error"
                trace_error = str(error)
                console.print(f"[bold red]Error:[/bold red] {error}")
                raise typer.Exit(code=1)

            report = state.get("report", "")
            if not report:
                trace_status = "error"
                trace_error = "Report is empty."
                console.print("[yellow]Warning:[/yellow] Report is empty.")
                raise typer.Exit(code=1)

            console.print("\n")
            console.print(Markdown(report))

            if output:
                with open(output, "w", encoding="utf-8") as fh:
                    fh.write(report)
                console.print(f"\n[green]Report saved to[/green] {output}")

            end_workflow_run(
                trace_ctx,
                status=trace_status,
                outputs={
                    "node": "__end__",
                    "has_report": bool(report),
                    "has_error": bool(error),
                },
            )
        except Exception as exc:
            if not trace_error:
                trace_error = str(exc)
            trace_status = "error"
            end_workflow_run(trace_ctx, status=trace_status, error=trace_error)
            raise


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


@app.command()
def rag_sidecar(
    host: str = typer.Option("0.0.0.0", help="Bind host."),
    port: int = typer.Option(8090, help="Bind port."),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev mode)."),
):
    """Start the internal RAG sidecar service."""
    import uvicorn

    console.print(Panel(f"[bold cyan]RAG Sidecar[/bold cyan]\nhttp://{host}:{port}"))
    uvicorn.run(
        "src.sidecar.app:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def rag_worker(
    poll_seconds: float = typer.Option(None, help="Polling interval in seconds."),
):
    """Run the RAG ingestion worker loop."""
    from src.rag import process_queued_ingestion_jobs

    from src.config import settings

    interval = settings.rag_worker_poll_seconds if poll_seconds is None else poll_seconds

    async def _run_worker() -> None:
        console.print(Panel("[bold cyan]RAG Ingestion Worker[/bold cyan]"))
        while True:
            processed = await process_queued_ingestion_jobs(limit=10)
            if processed > 0:
                console.print(f"[green]Processed {processed} RAG ingestion job(s)[/green]")
            await asyncio.sleep(max(interval, 0.2))

    asyncio.run(_run_worker())


if __name__ == "__main__":
    app()
