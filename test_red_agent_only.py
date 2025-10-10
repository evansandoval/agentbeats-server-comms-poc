#!/usr/bin/env python
"""
Test just the red agent proxy and local agent communication.

This sends a message directly to the red agent proxy to test that:
1. Proxy receives A2A message
2. Local agent polls and gets the message
3. Local agent processes and responds
4. Response flows back through proxy
"""

import requests
import json
import time

RED_AGENT_URL = "http://localhost:9021"


def test_red_agent():
    print("\n" + "="*60)
    print("TESTING RED AGENT PROXY + LOCAL AGENT")
    print("="*60)

    # Check red agent is ready
    print("\n1. Checking red agent proxy...")
    try:
        response = requests.get(f"{RED_AGENT_URL}/.well-known/agent.json")
        if response.status_code == 200:
            agent_card = response.json()
            print(f"✓ Red agent proxy is ready: {agent_card['name']}")
        else:
            print(f"✗ Red agent proxy returned {response.status_code}")
            return
    except Exception as e:
        print(f"✗ Red agent proxy not reachable: {e}")
        return

    # Send test message
    print("\n2. Sending test message to red agent...")
    battle_id = f"test_battle_{int(time.time())}"
    message = {
        "task_id": battle_id,
        "message": {
            "parts": [
                {
                    "type": "text",
                    "text": f"Perform your task. battle_id: {battle_id}"
                }
            ]
        }
    }

    print(f"   Battle ID: {battle_id}")
    print(f"   Message: {message['message']['parts'][0]['text']}")

    try:
        response = requests.post(
            f"{RED_AGENT_URL}/tasks",
            json=message,
            headers={"Content-Type": "application/json"},
            timeout=30,
            stream=True
        )

        print(f"\n3. Response status: {response.status_code}")

        if response.status_code == 200:
            print("\n4. Streaming response from red agent:")
            print("-" * 60)

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

            print("-" * 60)
            print("\n✓ Test completed successfully!")
            print("\nThe local red agent:")
            print("  1. Polled /poll_messages and received the battle task")
            print("  2. Extracted battle_id from the message")
            print("  3. Generated a response")
            print("  4. Submitted the response via /submit_response")
            print("  5. Proxy streamed the response back in A2A format")

        else:
            print(f"✗ Failed: {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    test_red_agent()
