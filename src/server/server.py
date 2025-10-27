"""Central WebSocket server for routing messages between agents."""

import asyncio
import json
import uuid
from typing import Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn

from src.proxy.messages import (
    RegisterMessage,
    RegisterAckMessage,
    RequestEnvelope,
    ResponseEnvelope,
    ErrorMessage,
)


class AgentServer:
    """Central server managing WebSocket connections and message routing."""

    def __init__(self):
        self.agents: Dict[str, WebSocket] = {}  # agent_id -> WebSocket
        self.pending: Dict[str, WebSocket] = {}  # request_id -> origin WebSocket
        self.lock = asyncio.Lock()  # For thread-safe dict operations

    async def register_agent(self, agent_id: str, websocket: WebSocket) -> None:
        """Register a new agent connection."""
        async with self.lock:
            if agent_id in self.agents:
                print(f"Warning: Agent {agent_id} already registered, replacing connection")
            self.agents[agent_id] = websocket
            print(f"✓ Agent '{agent_id}' registered. Active agents: {list(self.agents.keys())}")

    async def unregister_agent(self, agent_id: str) -> None:
        """Remove agent from active connections."""
        async with self.lock:
            if agent_id in self.agents:
                del self.agents[agent_id]
                print(f"✗ Agent '{agent_id}' disconnected. Active agents: {list(self.agents.keys())}")

    async def handle_request(
        self, envelope: RequestEnvelope, origin_ws: WebSocket
    ) -> None:
        """Route request to target agent and track pending responses."""
        target_agent = envelope.to_agent
        request_id = envelope.request_id

        # Check if target agent is online
        async with self.lock:
            target_ws = self.agents.get(target_agent)

        if not target_ws:
            # Send error back to origin
            error = ErrorMessage(
                request_id=request_id,
                error_code="AGENT_OFFLINE",
                message=f"Target agent '{target_agent}' is not connected",
            )
            await origin_ws.send_json(error.model_dump())
            print(f"✗ Request {request_id}: Target '{target_agent}' offline")
            return

        # Track pending request
        async with self.lock:
            self.pending[request_id] = origin_ws

        # Forward request to target
        try:
            await target_ws.send_json(envelope.model_dump(by_alias=True))
            print(
                f"→ Request {request_id}: {envelope.from_agent} → {envelope.to_agent} "
                f"({envelope.method} {envelope.path})"
            )
        except Exception as e:
            # Failed to send, clean up and notify origin
            async with self.lock:
                self.pending.pop(request_id, None)
            error = ErrorMessage(
                request_id=request_id,
                error_code="SEND_FAILED",
                message=f"Failed to forward request: {str(e)}",
            )
            await origin_ws.send_json(error.model_dump())
            print(f"✗ Request {request_id}: Send failed - {e}")

    async def handle_response(self, envelope: ResponseEnvelope) -> None:
        """Route response back to original requester."""
        request_id = envelope.request_id

        # Find original requester
        async with self.lock:
            origin_ws = self.pending.pop(request_id, None)

        if not origin_ws:
            print(f"✗ Response {request_id}: No pending request found (may have timed out)")
            return

        # Send response back
        try:
            await origin_ws.send_json(envelope.model_dump())
            print(f"← Response {request_id}: Status {envelope.status_code}")
        except Exception as e:
            print(f"✗ Response {request_id}: Failed to send back - {e}")

    async def send_task_to_agent(
        self, agent_id: str, task_body: dict, path: str = "/v1/message:send"
    ) -> Optional[str]:
        """
        Server-initiated task to an agent.
        Sends StartTaskMessage to proxy, which will use A2A client locally.
        Returns task_id if sent successfully, None otherwise.
        """
        async with self.lock:
            target_ws = self.agents.get(agent_id)

        if not target_ws:
            print(f"✗ Cannot send task: Agent '{agent_id}' not connected")
            return None

        from src.proxy.messages import StartTaskMessage

        task_id = str(uuid.uuid4())
        start_task_msg = StartTaskMessage(
            task_id=task_id,
            task_config=task_body,
        )

        try:
            await target_ws.send_json(start_task_msg.model_dump())
            print(f"⇒ Task {task_id}: server → {agent_id} (via start_task)")
            return task_id
        except Exception as e:
            print(f"✗ Task send failed: {e}")
            return None


# Global server instance
server = AgentServer()
app = FastAPI(title="A2A Agent Proxy Server")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        {
            "status": "healthy",
            "active_agents": list(server.agents.keys()),
            "pending_requests": len(server.pending),
        }
    )


@app.get("/agents")
async def list_agents():
    """List all connected agents."""
    return JSONResponse({"agents": list(server.agents.keys())})


@app.post("/tasks/send")
async def send_task_endpoint(request: dict):
    """
    HTTP endpoint to send a task to an agent.

    Body:
    {
        "agent_id": "green",
        "task_body": {...},
        "path": "/v1/message:send"  # optional
    }
    """
    agent_id = request.get("agent_id")
    task_body = request.get("task_body")
    path = request.get("path", "/v1/message:send")

    if not agent_id or not task_body:
        return JSONResponse(
            {"error": "Missing required fields: agent_id, task_body"},
            status_code=400
        )

    request_id = await server.send_task_to_agent(agent_id, task_body, path)

    if request_id:
        return JSONResponse({"status": "sent", "request_id": request_id})
    else:
        return JSONResponse(
            {"error": f"Agent '{agent_id}' not connected"},
            status_code=404
        )


@app.websocket("/ws/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for agent connections."""
    await websocket.accept()
    print(f"🔌 WebSocket connection from agent '{agent_id}'")

    try:
        # Wait for registration message
        data = await websocket.receive_json()
        reg_msg = RegisterMessage(**data)

        if reg_msg.agent_id != agent_id:
            error = ErrorMessage(
                error_code="ID_MISMATCH",
                message=f"Agent ID mismatch: path={agent_id}, message={reg_msg.agent_id}",
            )
            await websocket.send_json(error.model_dump())
            await websocket.close()
            return

        # Register agent
        await server.register_agent(agent_id, websocket)

        # Send acknowledgment
        ack = RegisterAckMessage(agent_id=agent_id)
        await websocket.send_json(ack.model_dump())

        # Handle messages
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "request":
                envelope = RequestEnvelope(**data)
                await server.handle_request(envelope, websocket)

            elif msg_type == "response":
                envelope = ResponseEnvelope(**data)
                await server.handle_response(envelope)

            elif msg_type == "error":
                error = ErrorMessage(**data)
                print(f"⚠ Error from {agent_id}: {error.message}")

            else:
                print(f"⚠ Unknown message type from {agent_id}: {msg_type}")

    except WebSocketDisconnect:
        await server.unregister_agent(agent_id)
    except Exception as e:
        print(f"✗ Error handling {agent_id}: {e}")
        await server.unregister_agent(agent_id)
        try:
            await websocket.close()
        except:
            pass


def start_server(host: str = "localhost", port: int = 8000):
    """Start the WebSocket server."""
    print(f"Starting A2A Proxy Server on ws://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
