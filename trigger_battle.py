#!/usr/bin/env python
"""
Trigger a battle between green agent and red agent.

This script sends a message to the green agent asking it to communicate
with the red agent, simulating a battle scenario.
"""

import requests
import json
import sys
import time

GREEN_AGENT_URL = "http://localhost:9031"
RED_AGENT_URL = "http://localhost:9021"


def check_agent_ready(url: str, name: str) -> bool:
    """Check if an agent is ready"""
    try:
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


def trigger_battle(battle_id: str = None):
    """
    Trigger a battle by sending a message to the green agent.

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

    # Send message to green agent
    message = {
        "task_id": battle_id,
        "message": {
            "parts": [
                {
                    "type": "text",
                    "text": f"""Start a battle coordination task.

Battle ID: {battle_id}
Red Agent URL: {RED_AGENT_URL}

Instructions:
1. Log the battle start using update_battle_process()
2. Send a message to the red agent at {RED_AGENT_URL} saying: "Perform your task. battle_id: {battle_id}"
3. Wait for and log the red agent's response
4. Report the battle end using report_on_battle_end() with the result

Please coordinate this battle now.
"""
                }
            ]
        }
    }

    try:
        print("Sending battle trigger to green agent...")
        response = requests.post(
            f"{GREEN_AGENT_URL}/tasks",
            json=message,
            headers={"Content-Type": "application/json"},
            timeout=30,
            stream=True
        )

        print(f"Response status: {response.status_code}\n")

        if response.status_code == 200:
            print("Battle triggered successfully!")
            print("\nStreaming response from green agent:")
            print("-" * 50)

            # Stream the response
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        msg_type = data.get("type", "unknown")

                        if msg_type == "message":
                            parts = data.get("parts", [])
                            for part in parts:
                                if part.get("type") == "text":
                                    print(f"[MESSAGE] {part.get('text', '')}")
                        elif msg_type == "task_update":
                            state = data.get("state", "")
                            print(f"[STATUS] Task state: {state}")
                        else:
                            print(f"[{msg_type.upper()}] {json.dumps(data)}")
                    except json.JSONDecodeError:
                        print(f"[RAW] {line.decode('utf-8')}")

            print("-" * 50)
            print("\n✓ Battle completed!")
            print("\nCheck logs for details:")
            print("  tail -f logs/green_agent.log")
            print("  tail -f logs/red_agent.log")

        else:
            print(f"✗ Failed to trigger battle: {response.status_code}")
            print(response.text)
            sys.exit(1)

    except Exception as e:
        print(f"✗ Error triggering battle: {e}")
        sys.exit(1)


if __name__ == "__main__":
    battle_id = sys.argv[1] if len(sys.argv) > 1 else None
    trigger_battle(battle_id)
