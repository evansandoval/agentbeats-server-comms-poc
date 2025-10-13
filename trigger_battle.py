#!/usr/bin/env python
"""
Trigger a battle between green agent and red agent.

This script sends a message to the green agent asking it to communicate
with the red agent, simulating a battle scenario.
"""

import asyncio
import json
import requests
import sys
import time
from agentbeats.utils.agents.a2a import send_message_to_agent

GREEN_AGENT_URL = "http://localhost:9031"
RED_AGENT_URL = "http://localhost:9021"
BACKEND_URL = "http://localhost:9000"  # Default backend URL (not required for PoC)
GREEN_AGENT_NAME = "green_agent"
RED_AGENT_NAME = "red_agent"


def check_agent_ready(url: str, name: str) -> bool:
    """Check if an agent is ready"""
    try:
        # Try new endpoint first, fall back to deprecated one
        response = requests.get(f"{url}/.well-known/agent-card.json", timeout=5)
        if response.status_code == 404:
            response = requests.get(f"{url}/.well-known/agent.json", timeout=5)
        if response.status_code == 200:
            print(f"✓ {name} is ready")
            return True
        else:
            print(f"✗ {name} returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ {name} not reachable: {e}")
        return False


async def trigger_battle(battle_id: str = None):
    """
    Trigger a battle by sending a message to the green agent using A2A SDK.

    The green agent will receive this message and should then
    communicate with the red agent.
    """
    if battle_id is None:
        battle_id = f"battle_{int(time.time())}"

    print("\n" + "="*50)
    print("TRIGGERING BATTLE")
    print("="*50)
    print(f"Battle ID: {battle_id}")
    print(f"Green Agent: {GREEN_AGENT_URL}")
    print(f"Red Agent: {RED_AGENT_URL}")
    print("="*50 + "\n")

    # Check agents are ready
    print("Checking agents...")
    green_ready = check_agent_ready(GREEN_AGENT_URL, "Green Agent")
    red_ready = check_agent_ready(RED_AGENT_URL, "Red Agent")

    if not green_ready or not red_ready:
        print("\n✗ Some agents are not ready. Please start them first:")
        print("  ./start_demo.sh")
        sys.exit(1)

    print("\n✓ All agents ready. Sending battle message...\n")

    # Construct structured JSON battle info (mimicking notify_green_agent from agentbeats)
    battle_info = {
        "type": "battle_start",
        "battle_id": battle_id,
        "green_battle_context": {
            "battle_id": battle_id,
            "backend_url": BACKEND_URL,
            "agent_name": GREEN_AGENT_NAME,
            "task_config": "Task description: Test agent-to-agent communication. Use talk_to_agent tool to send a message to the red agent and report back the response."
        },
        "red_battle_contexts": {
            RED_AGENT_URL: {
                "battle_id": battle_id,
                "backend_url": BACKEND_URL,
                "agent_name": RED_AGENT_NAME
            }
        },
        "opponent_infos": [
            {
                "agent_url": RED_AGENT_URL,
                "name": "Red Agent"
            }
        ]
    }

    try:
        print("Sending battle trigger to green agent using A2A SDK...")
        print(f"Battle info: {json.dumps(battle_info, indent=2)}\n")

        # Use the A2A SDK to send the JSON-serialized message
        response = await send_message_to_agent(
            target_url=GREEN_AGENT_URL,
            message=json.dumps(battle_info)
        )

        print("\n✓ Battle triggered successfully!")
        print("\nResponse from green agent:")
        print("-" * 50)
        print(response)
        print("-" * 50)

        print("\n✓ Battle completed!")
        print("\nCheck logs for details:")
        print("  tail -f logs/green_agent.log")
        print("  tail -f logs/red_agent.log")

    except Exception as e:
        print(f"✗ Error triggering battle: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    battle_id = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(trigger_battle(battle_id))
