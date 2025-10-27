"""Launcher module - initiates and coordinates the evaluation process."""

import multiprocessing
import json
import asyncio
import time
from src.green_agent.agent import start_green_agent
from src.white_agent.agent import start_white_agent
from src.server.server import start_server
from src.my_util import my_a2a


async def wait_server_ready(server_url: str, timeout: int = 10) -> bool:
    """Wait for server to be ready by checking health endpoint."""
    import httpx

    health_url = server_url.replace("ws://", "http://") + "/health"
    retry_cnt = 0

    async with httpx.AsyncClient() as client:
        while retry_cnt < timeout:
            retry_cnt += 1
            try:
                response = await client.get(health_url)
                if response.status_code == 200:
                    print(f"✓ Server is ready at {server_url}")
                    return True
            except Exception:
                pass
            print(f"Waiting for server... {retry_cnt}/{timeout}")
            await asyncio.sleep(1)

    return False


async def send_task_via_server(server_url: str, target_agent: str, task_body: dict):
    """Send task to agent via server's HTTP endpoint."""
    import httpx

    print(f"Sending task to '{target_agent}' via server...")

    # Convert ws:// to http:// for REST endpoint
    http_url = server_url.replace("ws://", "http://")
    endpoint = f"{http_url}/tasks/send"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                endpoint,
                json={
                    "agent_id": target_agent,
                    "task_body": task_body,
                    "path": "/v1/message:send"
                }
            )

            if response.status_code == 200:
                result = response.json()
                request_id = result.get("request_id")
                print(f"✓ Task sent with request_id: {request_id}")
                return request_id
            else:
                print(f"✗ Failed to send task: {response.text}")
                return None

        except Exception as e:
            print(f"✗ Error sending task: {e}")
            return None


async def launch_evaluation():
    """
    Launch the complete A2A proxy evaluation workflow.

    Flow:
    1. Start central WebSocket server
    2. Start green agent (auto-spawns proxy)
    3. Start white agent (auto-spawns proxy)
    4. Server initiates task to green agent
    5. Monitor and cleanup
    """
    print("=" * 60)
    print("A2A Agent Proxy Evaluation Launcher")
    print("=" * 60)

    # Configuration
    server_host = "localhost"
    server_port = 8000
    server_url = f"ws://{server_host}:{server_port}"

    green_agent_id = "green"
    green_agent_host = "localhost"
    green_agent_port = 9001
    green_proxy_port = 9101

    white_agent_id = "white-1"
    white_agent_host = "localhost"
    white_agent_port = 9002
    white_proxy_port = 9102

    # 1. Start central server
    print("\n[1/4] Starting central WebSocket server...")
    p_server = multiprocessing.Process(
        target=start_server, args=(server_host, server_port)
    )
    p_server.start()
    print(f"Server process started (PID: {p_server.pid})")

    # Wait for server to be ready
    if not await wait_server_ready(server_url):
        print("✗ Server failed to start")
        p_server.terminate()
        return

    # Give server a moment to fully initialize
    await asyncio.sleep(1)

    # 2. Start green agent with proxy
    print("\n[2/4] Starting green agent with proxy...")
    p_green = multiprocessing.Process(
        target=start_green_agent,
        kwargs={
            "agent_name": "tau_green_agent",
            "host": green_agent_host,
            "port": green_agent_port,
            "server_url": server_url,
            "agent_id": green_agent_id,
            "proxy_port": green_proxy_port,
        },
    )
    p_green.start()
    print(f"Green agent process started (PID: {p_green.pid})")

    # Wait for green agent to be ready
    green_url = f"http://{green_agent_host}:{green_agent_port}"
    if not await my_a2a.wait_agent_ready(green_url):
        print("✗ Green agent failed to start")
        p_green.terminate()
        p_server.terminate()
        return
    print("✓ Green agent is ready")

    # Wait for green proxy to be ready
    await asyncio.sleep(2)

    # 3. Start white agent with proxy
    print("\n[3/4] Starting white agent with proxy...")
    p_white = multiprocessing.Process(
        target=start_white_agent,
        kwargs={
            "agent_name": "general_white_agent",
            "host": white_agent_host,
            "port": white_agent_port,
            "server_url": server_url,
            "agent_id": white_agent_id,
            "proxy_port": white_proxy_port,
        },
    )
    p_white.start()
    print(f"White agent process started (PID: {p_white.pid})")

    # Wait for white agent to be ready
    white_url = f"http://{white_agent_host}:{white_agent_port}"
    if not await my_a2a.wait_agent_ready(white_url):
        print("✗ White agent failed to start")
        p_white.terminate()
        p_green.terminate()
        p_server.terminate()
        return
    print("✓ White agent is ready")

    # Wait for white proxy to be ready
    await asyncio.sleep(2)

    # 4. Server initiates task to green agent
    print("\n[4/4] Server sending task to green agent...")

    task_config = {
        "env": "retail",
        "user_strategy": "llm",
        "user_model": "openai/gpt-4o",
        "user_provider": "openai",
        "task_split": "test",
        "task_ids": [1],
    }

    task_body = {
        "task": "Your task is to instantiate tau-bench to test the following agent.",
        "agents": {
            white_agent_id: {
                "agent_id": white_agent_id,
                "description": "Target agent to test",
            }
        },
        "env_config": task_config,
    }

    # Send task via server
    await send_task_via_server(server_url, green_agent_id, task_body)

    # 5. Monitor execution
    print("\n" + "=" * 60)
    print("Evaluation running... (This may take a while)")
    print("Monitor the logs above for progress")
    print("=" * 60)

    # Wait for evaluation to complete
    # In a real system, we'd monitor task status via server API
    # For now, just wait a reasonable amount of time
    print("\nWaiting for evaluation to complete...")

    # Wait for green agent process to complete or timeout
    timeout = 300  # 5 minutes
    start_time = time.time()

    while p_green.is_alive() and (time.time() - start_time) < timeout:
        await asyncio.sleep(5)
        elapsed = int(time.time() - start_time)
        print(f"... still running ({elapsed}s elapsed)")

    if p_green.is_alive():
        print("\n⚠ Evaluation timed out, terminating processes...")
    else:
        print("\n✓ Evaluation completed")

    # Cleanup
    print("\nTerminating processes...")
    for p, name in [(p_green, "green"), (p_white, "white"), (p_server, "server")]:
        if p.is_alive():
            p.terminate()
            p.join(timeout=5)
            if p.is_alive():
                p.kill()
            print(f"✓ {name} terminated")

    print("\n" + "=" * 60)
    print("Evaluation complete. All processes terminated.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(launch_evaluation())
