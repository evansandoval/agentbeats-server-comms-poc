"""
Green agent tools for the PoC.
This file contains custom tools that the green agent can use.
"""

import agentbeats as ab
import asyncio
from agentbeats.utils.agents.a2a import send_message_to_agent


@ab.tool
def evaluate_battle(battle_id: str, red_response: str) -> str:
    """
    Simple evaluation function for the battle.

    Args:
        battle_id: The ID of the battle
        red_response: The response from the red agent

    Returns:
        Evaluation result as a string
    """
    # Simple dummy evaluation
    print("[Green] Evaluation called!")
    result = f"Battle {battle_id} evaluated. Red agent responded with: '{red_response}'"
    return result


@ab.tool
def generate_test_data(count: int = 1) -> str:
    """
    Generate test data for the battle.

    Args:
        count: Number of test items to generate

    Returns:
        Generated test data
    """
    print("[Green] Generated Test Data")
    return f"Generated {count} test items for the battle"


@ab.tool
def talk_to_agent(message: str, agent_url: str) -> str:
    """
    Send a message to another agent via A2A protocol.

    Args:
        message: The message to send to the agent
        agent_url: The URL of the target agent (e.g., "http://localhost:9021")

    Returns:
        The agent's response as a string
    """
    print(f"[Green] Sending message to agent at {agent_url}")
    print(f"[Green] Message: {message}")

    # Send message via A2A protocol (async)
    response = asyncio.run(send_message_to_agent(
        endpoint=agent_url,
        message=message
    ))

    print(f"[Green] Received response: {response}")
    return response
