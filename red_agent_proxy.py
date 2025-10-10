"""
Red Agent Proxy Server

This proxy acts as a bridge between the AgentBeats A2A protocol and a local red agent.
It implements:
1. Launcher Interface - handles /reset endpoint for battle context
2. A2A Server Interface - serves agent card and handles A2A message streaming
3. Local Agent Communication - provides polling endpoints for local agent
"""

import asyncio
import json
import logging
import tomli
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import httpx
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BattleContext(BaseModel):
    """Battle context received from launcher"""
    battle_id: str
    backend_url: str
    agent_id: Optional[str] = None
    other_data: Optional[Dict[str, Any]] = None


class MessageQueue:
    """Simple message queue for local agent communication"""
    def __init__(self):
        self.messages = []
        self.responses = []
        self.lock = asyncio.Lock()

    async def add_message(self, message: Dict[str, Any]):
        async with self.lock:
            self.messages.append(message)
            logger.info(f"Added message to queue: {message}")

    async def get_messages(self) -> list:
        async with self.lock:
            messages = self.messages.copy()
            self.messages.clear()
            return messages

    async def add_response(self, response: str):
        async with self.lock:
            self.responses.append(response)
            logger.info(f"Added response to queue: {response}")

    async def get_response(self) -> Optional[str]:
        async with self.lock:
            if self.responses:
                return self.responses.pop(0)
            return None


# Initialize FastAPI app
app = FastAPI(title="Red Agent Proxy")

# Global state
battle_context: Optional[BattleContext] = None
message_queue = MessageQueue()
agent_card: Optional[Dict[str, Any]] = None


def load_agent_card(card_path: str = "red_agent_card.toml") -> Dict[str, Any]:
    """Load agent card from TOML file and convert to A2A format"""
    with open(card_path, "rb") as f:
        card_toml = tomli.load(f)

    # Convert to A2A agent card JSON format
    a2a_card = {
        "name": card_toml["name"],
        "url": card_toml["url"],
        "version": card_toml["version"],
        "description": card_toml["description"],
        "capabilities": card_toml.get("capabilities", {}),
        "skills": card_toml.get("skills", [])
    }
    return a2a_card


# ============================================================================
# LAUNCHER INTERFACE
# ============================================================================

@app.post("/reset")
async def reset_agent(request: Request):
    """
    Launcher interface: Reset agent with battle context.
    This is called by BeatsAgentLauncher when starting a new battle.
    """
    global battle_context

    try:
        data = await request.json()
        logger.info(f"Received reset request: {data}")

        battle_context = BattleContext(
            battle_id=data.get("battle_id", ""),
            backend_url=data.get("backend_url", ""),
            agent_id=data.get("agent_id"),
            other_data=data
        )

        logger.info(f"Battle context updated: {battle_context}")

        # Notify backend that agent is ready
        if battle_context.backend_url and battle_context.agent_id:
            await notify_backend_ready(
                battle_context.backend_url,
                battle_context.agent_id
            )

        return {"status": "restarting"}

    except Exception as e:
        logger.error(f"Error in reset endpoint: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


async def notify_backend_ready(backend_url: str, agent_id: str):
    """Notify backend that agent is ready"""
    try:
        async with httpx.AsyncClient() as client:
            url = f"{backend_url}/agents/{agent_id}"
            await client.put(url, json={"ready": True})
            logger.info(f"Notified backend that agent {agent_id} is ready")
    except Exception as e:
        logger.error(f"Failed to notify backend: {e}")


# ============================================================================
# A2A SERVER INTERFACE
# ============================================================================

@app.get("/.well-known/agent.json")
async def get_agent_card():
    """Serve agent card for A2A protocol discovery"""
    if agent_card is None:
        return JSONResponse(
            status_code=500,
            content={"error": "Agent card not loaded"}
        )
    return JSONResponse(content=agent_card)


@app.post("/tasks")
async def handle_a2a_message(request: Request):
    """
    Handle A2A streaming message request.
    This endpoint receives messages from other agents via A2A protocol.
    """
    try:
        data = await request.json()
        logger.info(f"Received A2A message: {data}")

        # Extract message content
        message_content = data.get("message", {})
        task_id = data.get("task_id", f"task_{datetime.now().timestamp()}")

        # Add to message queue for local agent
        await message_queue.add_message({
            "task_id": task_id,
            "message": message_content,
            "timestamp": datetime.now().isoformat()
        })

        # Return streaming response
        async def stream_response():
            """Stream A2A response back to caller"""
            # Wait for local agent to respond (with timeout)
            max_wait = 30  # 30 seconds timeout
            wait_time = 0
            response_text = None

            while wait_time < max_wait:
                response_text = await message_queue.get_response()
                if response_text:
                    break
                await asyncio.sleep(0.5)
                wait_time += 0.5

            if response_text is None:
                response_text = "Timeout: Local agent did not respond"

            # Stream response in A2A format
            # Send task update
            yield json.dumps({
                "type": "task_update",
                "task_id": task_id,
                "state": "running"
            }) + "\n"

            # Send message
            yield json.dumps({
                "type": "message",
                "task_id": task_id,
                "parts": [{"type": "text", "text": response_text}]
            }) + "\n"

            # Send completion
            yield json.dumps({
                "type": "task_update",
                "task_id": task_id,
                "state": "completed"
            }) + "\n"

        return StreamingResponse(
            stream_response(),
            media_type="application/x-ndjson"
        )

    except Exception as e:
        logger.error(f"Error handling A2A message: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# ============================================================================
# LOCAL AGENT COMMUNICATION
# ============================================================================

@app.get("/poll_messages")
async def poll_messages():
    """Endpoint for local agent to poll for messages"""
    messages = await message_queue.get_messages()
    return {"messages": messages}


@app.post("/submit_response")
async def submit_response(request: Request):
    """Endpoint for local agent to submit responses"""
    try:
        data = await request.json()
        response_text = data.get("response", "")
        await message_queue.add_response(response_text)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error submitting response: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# ============================================================================
# MAIN
# ============================================================================

@app.on_event("startup")
async def startup():
    """Load agent card on startup"""
    global agent_card
    try:
        agent_card = load_agent_card("red_agent_card.toml")
        logger.info(f"Loaded agent card: {agent_card['name']}")
    except Exception as e:
        logger.error(f"Failed to load agent card: {e}")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9021,
        log_level="info"
    )
