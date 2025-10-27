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
                    # Server initiating a task - use A2A client to send to local agent
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
        import json

        task_config = start_task.task_config

        # Build task text in XML tags format (tau-bench style)
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

        task_text = "\n".join(text_parts)

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
        Handle incoming request from server - forward to local agent.
        Performs URL translation: inject proxy URLs for agent references.
        """
        print(
            f"[{self.agent_id}] ← Incoming request {envelope.request_id}: "
            f"{envelope.from_agent} → local agent ({envelope.method} {envelope.path})"
        )

        try:
            # Parse body and translate agent references
            body_text = envelope.body_text
            if body_text:
                # Body is already A2A format from server
                # We need to extract the text, translate URLs, and re-wrap
                from a2a.types import SendMessageRequest
                import re

                try:
                    # Parse A2A message
                    a2a_msg = SendMessageRequest.model_validate_json(body_text)

                    # Extract text from message parts
                    text_content = ""
                    if a2a_msg.params and a2a_msg.params.message:
                        for part in a2a_msg.params.message.parts:
                            if hasattr(part, 'text') and part.text:
                                text_content += part.text

                    # Translate <target_agent_id>X</target_agent_id> to <white_agent_url>http://...</white_agent_url>
                    def replace_agent_id(match):
                        agent_id = match.group(1)
                        proxy_url = f"http://localhost:{self.proxy_port}/agents/{agent_id}/"
                        return f"<white_agent_url>\n{proxy_url}\n</white_agent_url>"

                    translated_text = re.sub(
                        r'<target_agent_id>(.*?)</target_agent_id>',
                        replace_agent_id,
                        text_content
                    )

                    # Update the text in the A2A message
                    if a2a_msg.params and a2a_msg.params.message and a2a_msg.params.message.parts:
                        from a2a.types import Part, TextPart
                        a2a_msg.params.message.parts = [Part(TextPart(text=translated_text))]

                    # Serialize back to JSON
                    body_text = a2a_msg.model_dump_json()
                    print(f"[{self.agent_id}] Translated agent URLs in A2A message")

                except Exception as e:
                    print(f"[{self.agent_id}] Warning: Could not parse as A2A message: {e}")
                    # Keep original body_text if parsing fails

            # Forward to local agent
            # Use httpx.URL with raw_path to prevent encoding the colon
            from httpx import URL

            base_url = URL(self.local_agent_url)
            # Construct URL with raw path (no encoding)
            full_url = base_url.copy_with(raw_path=envelope.path.encode('utf-8'))

            print(f"[{self.agent_id}] sending request to {full_url}")

            response = await self.http_client.request(
                method=envelope.method,
                url=full_url,
                content=body_text.encode() if body_text else None,
                headers=envelope.headers,
            )

            # Send response back via WebSocket
            response_envelope = ResponseEnvelope(
                request_id=envelope.request_id,
                status_code=response.status_code,
                headers=dict(response.headers),
                body_text=response.text,
            )

            await self.ws.send(json.dumps(response_envelope.model_dump()))
            print(
                f"[{self.agent_id}] → Response {envelope.request_id}: "
                f"Status {response.status_code}"
            )

        except Exception as e:
            # Send error response
            error_envelope = ResponseEnvelope(
                request_id=envelope.request_id,
                status_code=500,
                headers={"Content-Type": "application/json"},
                body_text=json.dumps({"error": str(e)}),
            )
            await self.ws.send(json.dumps(error_envelope.model_dump()))
            print(f"[{self.agent_id}] ✗ Error handling request {envelope.request_id}: {e}")

    def _translate_agent_urls(self, body_text: str) -> str:
        """
        Translate agent references in message body to proxy URLs.

        Handles both JSON format and XML-tag format.

        JSON Example:
        Input:  {"agents": {"white-1": {"agent_id": "white-1"}}}
        Output: {"agents": {"white-1": {"agent_id": "white-1", "url": "http://localhost:9101/agents/white-1"}}}

        XML Example:
        Input:  {"agents": {"white-1": {...}}, "task": "..."}
        Output: Formatted as XML tags with <white_agent_url>...</white_agent_url>
        """
        try:
            body = json.loads(body_text)

            # Special handling for green agent's tau-bench format
            # It expects XML tags, not JSON
            if "agents" in body and "env_config" in body:
                # This is a tau-bench task - format with XML tags
                agents_dict = body.get("agents", {})

                # Build the text message with XML tags
                text_parts = []

                if "task" in body:
                    text_parts.append(body["task"])

                # Add agent URLs as XML tags
                for agent_id in agents_dict.keys():
                    proxy_url = f"http://localhost:{self.proxy_port}/agents/{agent_id}/"
                    text_parts.append(
                        f"<white_agent_url>\n{proxy_url}\n</white_agent_url>"
                    )

                # Add env config as XML tag
                if "env_config" in body:
                    env_json = json.dumps(body["env_config"], indent=2)
                    text_parts.append(
                        f"<env_config>\n{env_json}\n</env_config>"
                    )

                return "\n".join(text_parts)

            # Standard JSON handling
            # Pattern 1: "agents" dict with agent_id keys
            if "agents" in body and isinstance(body["agents"], dict):
                for agent_id, agent_info in body["agents"].items():
                    if isinstance(agent_info, dict):
                        # Inject proxy URL for this agent
                        agent_info["url"] = (
                            f"http://localhost:{self.proxy_port}/agents/{agent_id}"
                        )

            # Pattern 2: Direct target_agent_id field
            if "target_agent_id" in body:
                target_id = body["target_agent_id"]
                body["target_agent_url"] = (
                    f"http://localhost:{self.proxy_port}/agents/{target_id}"
                )

            return json.dumps(body)

        except json.JSONDecodeError:
            # Not JSON, return as-is
            return body_text

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
        await self.ws.send(json.dumps(envelope.model_dump(by_alias=True)))
        print(
            f"[{self.agent_id}] → Outgoing request {request_id}: "
            f"local agent → {target_agent_id} ({method} {path})"
        )

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
