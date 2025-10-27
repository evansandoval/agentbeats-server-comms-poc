"""Agent proxy - HTTP to WebSocket adapter."""

import asyncio
import json
import uuid
from typing import Dict, Optional
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from websockets.client import connect as ws_connect
from websockets.client import WebSocketClientProtocol

from src.proxy.messages import (
    RegisterMessage,
    RegisterAckMessage,
    RequestEnvelope,
    ResponseEnvelope,
    ErrorMessage,
)


class AgentProxy:
    """
    Proxy adapter between local agent HTTP server and central WebSocket server.

    Exposes:
    - HTTP server on proxy_port with /agents/{target_agent_id}/* routes
    - WebSocket client connected to central server

    Behavior:
    - Outgoing: HTTP from local agent → WebSocket to server
    - Incoming: WebSocket from server → HTTP to local agent
    """

    def __init__(
        self,
        agent_id: str,
        local_agent_url: str,
        server_url: str,
        # For now, we hardcode these to be different
        # After dockerizing, we can hardcode a single port that all agents use for their own proxy
        proxy_port: int,
    ):
        self.agent_id = agent_id
        self.local_agent_url = local_agent_url.rstrip("/")
        self.server_url = server_url
        self.proxy_port = proxy_port

        self.ws: Optional[WebSocketClientProtocol] = None
        self.pending_responses: Dict[str, asyncio.Future] = {}
        self.http_client = httpx.AsyncClient(timeout=120.0)
        self.ws_task: Optional[asyncio.Task] = None

    def _log_header(self, emoji: str, title: str, **details):
        """Helper to print consistent log headers."""
        print(f"\n{'='*60}", flush=True)
        print(f"[PROXY:{self.agent_id}] {emoji} {title}", flush=True)
        for key, value in details.items():
            print(f"  {key}: {value}", flush=True)
        print(f"{'='*60}\n", flush=True)

    def _format_task_text(self, task_config: dict) -> str:
        """
        Format task config as XML-tagged text for tau-bench.
        Translates agent IDs to proxy URLs.
        """
        text_parts = []

        if "task" in task_config:
            text_parts.append(task_config["task"])

        # Add agent URLs - translate to proxy URLs
        if "agents" in task_config:
            for agent_id_key in task_config["agents"].keys():
                proxy_url = f"http://localhost:{self.proxy_port}/agents/{agent_id_key}/"
                text_parts.append(
                    f"<white_agent_url>\n{proxy_url}\n</white_agent_url>"
                )

        # Add env config
        if "env_config" in task_config:
            env_json = json.dumps(task_config["env_config"], indent=2)
            text_parts.append(f"<env_config>\n{env_json}\n</env_config>")

        return "\n".join(text_parts)

    async def _send_response_envelope(self, request_id: str, status_code: int,
                                     headers: dict, body_text: str):
        """Helper to create and send response envelope via WebSocket."""
        response_envelope = ResponseEnvelope(
            request_id=request_id,
            status_code=status_code,
            headers=headers,
            body_text=body_text,
        )
        await self.ws.send(json.dumps(response_envelope.model_dump()))

    async def connect_to_server(self):
        """Establish WebSocket connection and register with server."""
        ws_url = f"{self.server_url}/ws/{self.agent_id}"
        print(f"[{self.agent_id}] Connecting to server: {ws_url}")

        self.ws = await ws_connect(ws_url)

        # Send registration message
        reg_msg = RegisterMessage(agent_id=self.agent_id)
        await self.ws.send(json.dumps(reg_msg.model_dump()))

        # Wait for acknowledgment
        ack_data = await self.ws.recv()
        ack = RegisterAckMessage(**json.loads(ack_data))
        print(f"[{self.agent_id}] ✓ Registered with server: {ack.message}")

        # Start listening for incoming messages
        self.ws_task = asyncio.create_task(self._ws_message_loop())

    async def _ws_message_loop(self):
        """Listen for incoming WebSocket messages from server."""
        try:
            async for message in self.ws:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "start_task":
                    # Server initiating an evaluation - use A2A client to send to local agent
                    from src.proxy.messages import StartTaskMessage
                    start_task = StartTaskMessage(**data)
                    asyncio.create_task(self._handle_start_task(start_task))

                elif msg_type == "request":
                    # Server/agent sending request to our local agent
                    envelope = RequestEnvelope(**data)
                    asyncio.create_task(self._handle_incoming_request(envelope))

                elif msg_type == "response":
                    # Response to our outgoing request
                    envelope = ResponseEnvelope(**data)
                    self._complete_pending_request(envelope)

                elif msg_type == "error":
                    error = ErrorMessage(**data)
                    self._handle_error(error)

                else:
                    print(f"[{self.agent_id}] Unknown message type: {msg_type}")

        except Exception as e:
            print(f"[{self.agent_id}] WebSocket loop error: {e}")

    async def _handle_start_task(self, start_task):
        """
        Handle server-initiated task.
        Uses A2A client to send message to local agent.
        """
        print(f"[{self.agent_id}] ← Start task {start_task.task_id} from server")

        from src.my_util import my_a2a

        # Format task text using helper
        task_text = self._format_task_text(start_task.task_config)

        print(f"[{self.agent_id}] Sending task to local agent via A2A client")
        print(f"Task text:\n{task_text}")

        try:
            # Use A2A client to send message to local agent
            response = await my_a2a.send_message(self.local_agent_url, task_text)
            print(f"[{self.agent_id}] ✓ Task sent successfully to local agent")
            print(f"Response: {response}")
        except Exception as e:
            print(f"[{self.agent_id}] ✗ Error sending task to local agent: {e}")

    async def _handle_incoming_request(self, envelope: RequestEnvelope):
        """
        Handle incoming request from another agent via websocket with server.
        Uses httpx to forward HTTP request to local agent.
        """
        self._log_header(
            "📥", "RECEIVED from server via WebSocket",
            request_id=envelope.request_id,
            from_to=f"{envelope.from_agent} → To: local {self.agent_id} agent",
            method_path=f"{envelope.method} {envelope.path}"
        )

        try:
            # Forward to local agent using httpx with raw path to avoid encoding ":"
            from httpx import URL

            base_url = URL(self.local_agent_url)
            full_url = base_url.copy_with(raw_path=envelope.path.encode('utf-8'))

            response = await self.http_client.request(
                method=envelope.method,
                url=full_url,
                content=envelope.body_text.encode() if envelope.body_text else None,
                headers=envelope.headers,
            )

            # Send response back via WebSocket using helper
            await self._send_response_envelope(
                request_id=envelope.request_id,
                status_code=response.status_code,
                headers=dict(response.headers),
                body_text=response.text,
            )
            print(
                f"[{self.agent_id}] → Response {envelope.request_id}: "
                f"Status {response.status_code}"
            )

        except Exception as e:
            # Send error response using helper
            await self._send_response_envelope(
                request_id=envelope.request_id,
                status_code=500,
                headers={"Content-Type": "application/json"},
                body_text=json.dumps({"error": str(e)}),
            )
            print(f"[{self.agent_id}] ✗ Error handling request {envelope.request_id}: {e}")

    async def send_request_via_websocket(
        self, target_agent_id: str, method: str, path: str, headers: dict, body: bytes
    ) -> Response:
        """
        Send HTTP request to remote agent via WebSocket.
        Returns HTTP Response after receiving reply.
        """
        request_id = str(uuid.uuid4())

        # Create request envelope
        envelope = RequestEnvelope(
            request_id=request_id,
            from_agent=self.agent_id,
            to_agent=target_agent_id,
            method=method,
            path=path,
            headers=headers,
            body_text=body.decode() if body else None,
        )

        # Create future for response
        response_future = asyncio.Future()
        self.pending_responses[request_id] = response_future

        # Send via WebSocket
        self._log_header(
            "📤", "SENDING to server via WebSocket",
            request_id=request_id,
            from_to=f"{self.agent_id} → To: {target_agent_id}",
            method_path=f"{method} {path}"
        )

        await self.ws.send(json.dumps(envelope.model_dump(by_alias=True)))

        # Wait for response (with timeout)
        try:
            response_envelope = await asyncio.wait_for(response_future, timeout=120.0)

            return Response(
                content=response_envelope.body_text,
                status_code=response_envelope.status_code,
                headers=dict(response_envelope.headers),
            )

        except asyncio.TimeoutError:
            self.pending_responses.pop(request_id, None)
            print(f"[{self.agent_id}] ✗ Request {request_id} timed out")
            return Response(
                content=json.dumps({"error": "Request timed out"}),
                status_code=504,
                headers={"Content-Type": "application/json"},
            )

    def _complete_pending_request(self, envelope: ResponseEnvelope):
        """Complete a pending outgoing request with the response."""
        request_id = envelope.request_id
        future = self.pending_responses.pop(request_id, None)

        if future and not future.done():
            future.set_result(envelope)
            print(f"[{self.agent_id}] ✓ Response received for {request_id}")
        else:
            print(f"[{self.agent_id}] ⚠ No pending request for {request_id}")

    def _handle_error(self, error: ErrorMessage):
        """Handle error message from server."""
        print(f"[{self.agent_id}] ✗ Server error: {error.message}")

        if error.request_id:
            future = self.pending_responses.pop(error.request_id, None)
            if future and not future.done():
                # Complete with error response
                error_response = ResponseEnvelope(
                    request_id=error.request_id,
                    status_code=502,
                    headers={"Content-Type": "application/json"},
                    body_text=json.dumps(
                        {"error": error.error_code, "message": error.message}
                    ),
                )
                future.set_result(error_response)

    async def cleanup(self):
        """Clean up resources."""
        if self.ws_task:
            self.ws_task.cancel()
        if self.ws:
            await self.ws.close()
        await self.http_client.aclose()


# FastAPI app factory
def create_proxy_app(proxy: AgentProxy) -> FastAPI:
    """Create FastAPI app for the proxy HTTP server."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: connect to server
        await proxy.connect_to_server()
        yield
        # Shutdown: cleanup
        await proxy.cleanup()

    app = FastAPI(
        title=f"Agent Proxy - {proxy.agent_id}",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health():
        """Proxy health check."""
        return JSONResponse(
            {
                "agent_id": proxy.agent_id,
                "status": "healthy",
                "ws_connected": proxy.ws is not None and proxy.ws.open,
            }
        )

    @app.api_route(
        "/agents/{target_agent_id}/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    )
    async def route_to_remote_agent(
        target_agent_id: str, path: str, request: Request
    ):
        """
        Route HTTP requests to remote agents via WebSocket.

        URL pattern: /agents/{target_agent_id}/v1/message:send
        Extracts target_agent_id and forwards via WebSocket.
        """
        proxy._log_header(
            "🔵", "ENTRY: HTTP from local agent",
            method=request.method,
            target=target_agent_id,
            path=f"/{path}"
        )

        # Read request details
        body = await request.body()
        headers = dict(request.headers)

        # Send via WebSocket to target agent
        response = await proxy.send_request_via_websocket(
            target_agent_id=target_agent_id,
            method=request.method,
            path=f"/{path}",
            headers=headers,
            body=body,
        )

        proxy._log_header(
            "🟢", "EXIT: Returning to local agent",
            status=response.status_code
        )

        return response

    return app


def start_agent_proxy(
    agent_id: str,
    local_agent_url: str,
    server_url: str,
    proxy_port: int,
    host: str = "localhost",
):
    """
    Start agent proxy server.

    Args:
        agent_id: Unique identifier for this agent
        local_agent_url: URL of local agent's HTTP server (e.g., http://localhost:9001)
        server_url: WebSocket URL of central server (e.g., ws://localhost:8000)
        proxy_port: Port to expose HTTP server on
        host: Host to bind to
    """
    proxy = AgentProxy(
        agent_id=agent_id,
        local_agent_url=local_agent_url,
        server_url=server_url,
        proxy_port=proxy_port,
    )

    app = create_proxy_app(proxy)

    print(f"Starting proxy for '{agent_id}' on http://{host}:{proxy_port}")
    uvicorn.run(app, host=host, port=proxy_port)


if __name__ == "__main__":
    # Example usage
    start_agent_proxy(
        agent_id="test-agent",
        local_agent_url="http://localhost:9001",
        server_url="ws://localhost:8000",
        proxy_port=9101,
    )
