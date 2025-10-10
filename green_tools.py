"""
Green agent tools for the PoC.
This file contains custom tools that the green agent can use.
"""

import agentbeats as ab


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
    return f"Generated {count} test items for the battle"
