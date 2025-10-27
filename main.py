"""CLI entry point for agentify-example-tau-bench."""

import typer
import asyncio

from src.green_agent import start_green_agent
from src.white_agent import start_white_agent
from src.launcher import launch_evaluation
from src.server.server import start_server

app = typer.Typer(help="Agentified Tau-Bench - Standardized agent assessment framework")


@app.command()
def green():
    """Start the green agent (assessment manager)."""
    start_green_agent()


@app.command()
def white():
    """Start the white agent (target being tested)."""
    start_white_agent()


@app.command()
def launch():
    """Launch the complete evaluation workflow (original, no proxy)."""
    asyncio.run(launch_evaluation())


@app.command()
def server():
    """Start the central WebSocket server."""
    start_server()


@app.command(name="launch-proxy")
def launch_proxy():
    """Launch evaluation with proxy architecture (server-initiated)."""
    from src.launcher import launch_evaluation

    asyncio.run(launch_evaluation())


if __name__ == "__main__":
    app()
