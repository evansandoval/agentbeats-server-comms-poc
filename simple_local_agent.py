"""
Simple Local Agent with Auto-Proxy

This demonstrates the improved UX where the user just runs their agent
and the proxy is automatically started.
"""

from proxy_wrapper import run_with_proxy
from local_red_agent import LocalRedAgent


def main():
    """
    Main entry point - single command to run everything!

    The user just needs to:
    1. Create their agent class (or use LocalRedAgent)
    2. Call run_with_proxy()

    That's it! No manual proxy startup needed.
    """
    # Create your local agent
    agent = LocalRedAgent(proxy_url="http://localhost:9021")

    # Run with automatic proxy startup
    # The proxy will start automatically and handle A2A communication
    run_with_proxy(
        agent,
        agent_card_path="red_agent_card.toml",
        proxy_port=9021
    )


if __name__ == "__main__":
    main()
