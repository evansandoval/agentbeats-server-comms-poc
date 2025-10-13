"""
Simple Local Red Agent with Auto-Proxy

This demonstrates the improved UX where the user just runs their agent
and the proxy is automatically started.
"""

import time
import logging
import re
from typing import Dict, Any, Optional
from proxy_wrapper import run_with_proxy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleRedAgent:
    """Simple red agent that responds to battle messages"""

    def __init__(self):
        self.running = False
        self.proxy_client = None  # Will be injected by run_with_proxy
        logger.info("Red agent initialized")

    def extract_battle_id(self, message_text: str) -> Optional[str]:
        """Extract battle_id from message text"""
        match = re.search(r'battle_id[:\s=]+(\S+)', message_text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def poll_messages(self) -> list:
        """Poll the proxy for new messages"""
        if self.proxy_client is None:
            logger.error("ProxyClient not injected - did you use run_with_proxy()?")
            return []
        return self.proxy_client.poll_messages()

    def submit_response(self, response_text: str) -> bool:
        """Submit a response to the proxy"""
        if self.proxy_client is None:
            logger.error("ProxyClient not injected - did you use run_with_proxy()?")
            return False
        return self.proxy_client.submit_response(response_text)

    def process_message(self, message: Dict[str, Any]) -> str:
        """Process a message and generate a response"""
        logger.info(f"Processing message: {message}")

        # Extract message text
        msg_content = message.get("message", {})
        if isinstance(msg_content, dict):
            parts = msg_content.get("parts", [])
            text = " ".join(p.get("text", "") for p in parts if p.get("type") == "text")
        else:
            text = str(msg_content)

        logger.info(f"Message text: {text}")

        # Extract battle_id if present
        battle_id = self.extract_battle_id(text)

        # Generate response
        if battle_id:
            response = f"Red agent completed task for battle {battle_id}. Task acknowledged and executed successfully."
        else:
            response = "Red agent completed the assigned task successfully."

        logger.info(f"Generated response: {response}")
        return response

    def run(self):
        """Main agent loop"""
        self.running = True
        logger.info("Red agent started!")

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
                time.sleep(3.0)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.running = False


def main():
    """Main entry point - single command to run everything!"""
    # Create agent - no proxy URL needed!
    agent = SimpleRedAgent()

    # Run with automatic proxy startup - proxy URL is handled internally
    run_with_proxy(
        agent,
        agent_card_path="red_agent_card.toml",
        proxy_port=9021
    )


if __name__ == "__main__":
    main()
