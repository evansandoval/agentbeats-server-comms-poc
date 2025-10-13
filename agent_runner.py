"""
Agent Runner

This module provides the agent execution loop that handles all infrastructure
concerns (polling, processing, submitting) so agent developers can focus on
business logic only.
"""

import time
import logging
from typing import Dict, Any
from agent_base import AgentBase
from proxy_wrapper import ProxyClient

logger = logging.getLogger(__name__)


class AgentRunner:
    """
    Runs an agent's main loop, handling all proxy communication.

    The runner:
    1. Polls proxy for new messages
    2. Calls agent's process_message() method
    3. Submits responses back to proxy
    4. Repeats until stopped

    Agent developers never interact with this class directly.
    """

    def __init__(self, agent: AgentBase, proxy_client: ProxyClient, poll_interval: float = 3.0):
        """
        Initialize the agent runner.

        Args:
            agent: The agent instance (must inherit from AgentBase)
            proxy_client: The proxy client for communication
            poll_interval: Time to wait between polls (seconds)
        """
        self.agent = agent
        self.proxy_client = proxy_client
        self.poll_interval = poll_interval
        self.running = False
        logger.info(f"AgentRunner initialized for {agent.__class__.__name__}")

    def run(self):
        """
        Main agent loop.

        Continuously polls for messages, processes them, and submits responses.
        Runs until KeyboardInterrupt or error.
        """
        self.running = True
        logger.info(f"Starting agent loop for {self.agent.__class__.__name__}")

        try:
            while self.running:
                # Poll for messages
                messages = self.proxy_client.poll_messages()

                # Process each message
                for message in messages:
                    try:
                        logger.info(f"Processing message: {message.get('task_id', 'unknown')}")

                        # Call agent's business logic
                        response = self.agent.process_message(message)

                        # Submit response back to proxy
                        self.proxy_client.submit_response(response)

                        logger.info(f"Response submitted successfully")

                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)

                # Wait before next poll
                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            logger.info("Agent loop interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error in agent loop: {e}", exc_info=True)
        finally:
            self.running = False
            logger.info("Agent loop stopped")

    def stop(self):
        """Stop the agent loop gracefully."""
        self.running = False
