"""
Example: Creating a Custom Local Agent

This shows how a user would create their own agent from scratch.

Key Points:
1. Inherit from AgentBase
2. Implement only process_message() with your business logic
3. No infrastructure code needed!
"""

import logging
from typing import Dict, Any
from agent_base import AgentBase
from proxy_wrapper import run_with_proxy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MyCustomAgent(AgentBase):
    """
    User's custom agent implementation.

    The user only needs to:
    1. Inherit from AgentBase
    2. Implement process_message() with their business logic

    That's it! No proxy URLs, no HTTP requests, no polling loops.
    All infrastructure is handled by the framework.
    """

    def __init__(self):
        logger.info("Custom agent initialized")

    def process_message(self, message: Dict[str, Any]) -> str:
        """
        Custom message processing logic.

        This is the ONLY method you need to implement!

        Args:
            message: The incoming message dict

        Returns:
            str: Your response text
        """
        logger.info(f"Processing: {message}")

        # Example: Extract message text
        msg_content = message.get("message", {})
        if isinstance(msg_content, dict):
            parts = msg_content.get("parts", [])
            text = " ".join(p.get("text", "") for p in parts if p.get("type") == "text")
        else:
            text = str(msg_content)

        # Custom response logic - this is where your agent's intelligence goes!
        response = f"My custom agent processed: {text[:50]}..."
        logger.info(f"Generated response: {response}")
        return response


def main():
    """
    Single command to run everything!

    Usage:
        python example_custom_agent.py

    That's it! The framework handles:
    - Starting the proxy server
    - Polling for messages
    - Calling your process_message() method
    - Submitting responses
    - A2A protocol details
    """
    # Step 1: Create your agent (no parameters needed!)
    agent = MyCustomAgent()

    # Step 2: Run it with proxy (one line!)
    run_with_proxy(
        agent,
        agent_card_path="custom_agent_card.toml",  # Create your own card
        proxy_port=9025
    )


if __name__ == "__main__":
    main()
