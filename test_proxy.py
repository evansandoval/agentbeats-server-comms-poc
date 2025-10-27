"""Simple test to verify proxy architecture components."""

import asyncio
import multiprocessing
import time
from src.server.server import start_server
from src.proxy.agent_proxy import start_agent_proxy


async def test_server_startup():
    """Test that server starts and responds to health checks."""
    print("Testing server startup...")

    # Start server in subprocess
    p_server = multiprocessing.Process(target=start_server, args=("localhost", 8000))
    p_server.start()

    # Wait for server to start
    await asyncio.sleep(3)

    # Check health endpoint
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health")
            print(f"Health check response: {response.json()}")
            assert response.status_code == 200
            print("✓ Server health check passed")
    finally:
        p_server.terminate()
        p_server.join()
        print("✓ Server terminated")


async def test_proxy_registration():
    """Test that proxy can register with server."""
    print("\nTesting proxy registration...")

    # Start server
    p_server = multiprocessing.Process(target=start_server, args=("localhost", 8000))
    p_server.start()
    await asyncio.sleep(3)

    # Start a mock agent (just a simple HTTP server)
    from fastapi import FastAPI
    import uvicorn

    def start_mock_agent():
        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        uvicorn.run(app, host="localhost", port=9001)

    p_agent = multiprocessing.Process(target=start_mock_agent)
    p_agent.start()
    await asyncio.sleep(2)

    # Start proxy
    p_proxy = multiprocessing.Process(
        target=start_agent_proxy,
        args=("test-agent", "http://localhost:9001", "ws://localhost:8000", 9101),
    )
    p_proxy.start()
    await asyncio.sleep(3)

    # Check server's agent list
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/agents")
            agents = response.json()
            print(f"Registered agents: {agents}")
            assert "test-agent" in agents["agents"]
            print("✓ Proxy registration successful")
    finally:
        p_proxy.terminate()
        p_agent.terminate()
        p_server.terminate()
        for p in [p_proxy, p_agent, p_server]:
            p.join()
        print("✓ All processes terminated")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("A2A Proxy Architecture - Basic Tests")
    print("=" * 60)

    try:
        await test_server_startup()
        await test_proxy_registration()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
