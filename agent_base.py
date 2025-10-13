"""
Agent Base Class

This module provides an abstract base class for agent development.
Developers only need to implement process_message() - all infrastructure
details (proxy communication, HTTP requests, etc.) are abstracted away.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class AgentBase(ABC):
    """
    Abstract base class for agents.

    Agent developers should inherit from this class and implement
    the process_message() method with their business logic.

    The framework handles all infrastructure concerns:
    - Proxy communication
    - Message polling
    - Response submission
    - A2A protocol details

    Example:
        class MyAgent(AgentBase):
            def process_message(self, message: Dict[str, Any]) -> str:
                # Your business logic here
                return "Response from my agent"
    """

    @abstractmethod
    def process_message(self, message: Dict[str, Any]) -> str:
        """
        Process a message and return a response.

        This is the only method agent developers need to implement.

        Args:
            message: Message dict containing:
                - task_id: Unique task identifier
                - message: The message content (dict with 'parts')
                - timestamp: When the message was received

        Returns:
            str: The response text to send back
        """
        pass
