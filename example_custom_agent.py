"""
Example: Creating a Custom Local Agent

This shows how a user would create their own agent from scratch.
"""

import time
import logging
import requests
from typing import Dict, Any
from proxy_wrapper import run_with_proxy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MyCustomAgent:
    """
    User's custom agent implementation.

    The user only needs to:
    1. Implement __init__ with proxy_url parameter
    2. Implement run() method with their agent logic
    3. Use the proxy endpoints to communicate
    """

    def __init__(self, proxy_url: str = "http://localhost:9025"):
        self.proxy_url = proxy_url
        self.running = False
        logger.info(f"Custom agent initialized with proxy: {proxy_url}")

    def poll_messages(self) -> list:
        """Poll the proxy for new messages"""
        try:
            response = requests.get(f"{self.proxy_url}/poll_messages", timeout=5)
            response.raise_for_status()
            return response.json().get("messages", [])
        except Exception as e:
            logger.error(f"Error polling: {e}")
            return []

    def submit_response(self, response_text: str) -> bool:
        """Submit a response to the proxy"""
        try:
            response = requests.post(
                f"{self.proxy_url}/submit_response",
                json={"response": response_text},
                timeout=5
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error submitting: {e}")
            return False

    def process_message(self, message: Dict[str, Any]) -> str:
        """
        Custom message processing logic.
        Users implement their own logic here!
        """
        logger.info(f"Processing: {message}")

        # Example: Extract message text
        msg_content = message.get("message", {})
        if isinstance(msg_content, dict):
            parts = msg_content.get("parts", [])
            text = " ".join(p.get("text", "") for p in parts if p.get("type") == "text")
        else:
            text = str(msg_content)

        # Custom response logic
        response = f"My custom agent processed: {text[:50]}..."
        logger.info(f"Generated response: {response}")
        return response

    def run(self):
        """
        Main agent loop.
        This is called automatically by run_with_proxy()
        """
        self.running = True
        logger.info("Custom agent started!")

        try:
            while self.running:
                # Poll for messages
                messages = self.poll_messages()

                # Process each message
                for message in messages:
                    try:
                        response = self.process_message(message)
                        self.submit_response(response)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")

                # Wait before next poll
                time.sleep(1.0)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.running = False


def main():
    """
    Single command to run everything!

    Usage:
        python example_custom_agent.py

    That's it! The proxy starts automatically.
    """
    agent = MyCustomAgent(proxy_url="http://localhost:9025")

    run_with_proxy(
        agent,
        agent_card_path="custom_agent_card.toml",  # Create your own card
        proxy_port=9025
    )


if __name__ == "__main__":
    main()
