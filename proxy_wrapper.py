"""
Proxy Wrapper - Automatically starts proxy server for local agents

This module provides a decorator/wrapper that allows local agents to
automatically start a proxy server for A2A communication.
"""

import asyncio
import threading
import time
import logging
import requests
from typing import Optional, Callable, Any, Dict, List
import uvicorn
from red_agent_proxy import app, load_agent_card

logger = logging.getLogger(__name__)


class ProxyClient:
    """
    Client interface for agents to communicate with proxy.
    Abstracts away proxy URL - agents just call methods without knowing implementation.
    """

    def __init__(self, proxy_url: str):
        self._proxy_url = proxy_url

    def poll_messages(self) -> List[Dict[str, Any]]:
        """Poll the proxy for new messages"""
        try:
            response = requests.get(f"{self._proxy_url}/poll_messages", timeout=5)
            response.raise_for_status()
            return response.json().get("messages", [])
        except Exception as e:
            logger.error(f"Error polling messages: {e}")
            return []

    def submit_response(self, response_text: str) -> bool:
        """Submit a response to the proxy"""
        try:
            response = requests.post(
                f"{self._proxy_url}/submit_response",
                json={"response": response_text},
                timeout=5
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error submitting response: {e}")
            return False


class ProxyWrapper:
    """Wrapper that manages proxy server lifecycle for local agents"""

    def __init__(
        self,
        agent_card_path: str = "red_agent_card.toml",
        proxy_host: str = "0.0.0.0",
        proxy_port: int = 9021
    ):
        self.agent_card_path = agent_card_path
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.proxy_thread: Optional[threading.Thread] = None
        self.proxy_server: Optional[uvicorn.Server] = None

    def start_proxy(self):
        """Start the proxy server in a background thread"""
        logger.info(f"Starting proxy server on {self.proxy_host}:{self.proxy_port}")

        # Load agent card
        global agent_card
        try:
            from red_agent_proxy import agent_card as ac
            agent_card = load_agent_card(self.agent_card_path)
            logger.info(f"Loaded agent card: {agent_card['name']}")
        except Exception as e:
            logger.error(f"Failed to load agent card: {e}")

        # Start uvicorn in a thread
        def run_server():
            config = uvicorn.Config(
                app,
                host=self.proxy_host,
                port=self.proxy_port,
                log_level="info"
            )
            server = uvicorn.Server(config)
            self.proxy_server = server
            server.run()

        self.proxy_thread = threading.Thread(target=run_server, daemon=True)
        self.proxy_thread.start()

        # Wait for server to be ready
        time.sleep(2)
        logger.info("Proxy server started successfully")

    def stop_proxy(self):
        """Stop the proxy server"""
        if self.proxy_server:
            self.proxy_server.should_exit = True
        logger.info("Proxy server stopped")

    def __enter__(self):
        """Context manager entry - start proxy"""
        self.start_proxy()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop proxy"""
        self.stop_proxy()


def with_proxy(
    agent_card_path: str = "red_agent_card.toml",
    proxy_host: str = "0.0.0.0",
    proxy_port: int = 9021
):
    """
    Decorator to automatically start proxy server for local agent.

    Usage:
        @with_proxy(agent_card_path="my_agent_card.toml", proxy_port=9021)
        class MyLocalAgent:
            def run(self):
                # Your agent logic here
                pass
    """
    def decorator(agent_class):
        original_init = agent_class.__init__

        def new_init(self, *args, **kwargs):
            # Start proxy wrapper
            self._proxy_wrapper = ProxyWrapper(
                agent_card_path=agent_card_path,
                proxy_host=proxy_host,
                proxy_port=proxy_port
            )
            self._proxy_wrapper.start_proxy()

            # Call original init
            original_init(self, *args, **kwargs)

        agent_class.__init__ = new_init
        return agent_class

    return decorator


def run_with_proxy(
    agent_instance: Any,
    agent_card_path: str = "red_agent_card.toml",
    proxy_host: str = "0.0.0.0",
    proxy_port: int = 9021,
    poll_interval: float = 3.0
):
    """
    Run a local agent with automatic proxy startup.

    This function handles all infrastructure:
    - Starts the proxy server
    - Creates proxy client
    - Runs agent loop with polling/processing/submission

    Agent developers just pass their agent instance - everything else
    is abstracted away.

    Args:
        agent_instance: Agent instance (must inherit from AgentBase)
        agent_card_path: Path to agent card TOML file
        proxy_host: Host to bind proxy server
        proxy_port: Port for proxy server
        poll_interval: Time between message polls (seconds)

    Usage:
        agent = MyLocalAgent()
        run_with_proxy(agent, agent_card_path="my_agent_card.toml")
    """
    from agent_runner import AgentRunner

    with ProxyWrapper(agent_card_path, proxy_host, proxy_port):
        # Create proxy client
        proxy_url = f"http://{proxy_host}:{proxy_port}"
        proxy_client = ProxyClient(proxy_url)
        logger.info(f"Created ProxyClient for {proxy_url}")

        # Create and run agent with runner
        runner = AgentRunner(agent_instance, proxy_client, poll_interval)
        runner.run()
