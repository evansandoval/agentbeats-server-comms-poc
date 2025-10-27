"""WebSocket message schemas for agent proxy communication."""

from typing import Literal, Optional, Dict
from pydantic import BaseModel, Field


class RegisterMessage(BaseModel):
    """Agent registration message sent when proxy connects to server."""

    type: Literal["register"] = "register"
    agent_id: str = Field(..., description="Unique identifier for this agent")


class RegisterAckMessage(BaseModel):
    """Acknowledgment from server after successful registration."""

    type: Literal["register_ack"] = "register_ack"
    agent_id: str
    message: str = "Registration successful"


class RequestEnvelope(BaseModel):
    """HTTP request wrapped for WebSocket transport."""

    type: Literal["request"] = "request"
    request_id: str = Field(..., description="Unique ID for request/response matching")
    from_agent: str = Field(..., alias="from", description="Source agent ID")
    to_agent: str = Field(..., alias="to", description="Target agent ID")
    method: str = Field(..., description="HTTP method (GET, POST, etc.)")
    path: str = Field(..., description="HTTP path (e.g., /v1/message:send)")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    body_text: Optional[str] = Field(None, description="Request body as text")
    body_b64: Optional[str] = Field(
        None, description="Request body as base64 (for binary data)"
    )

    class Config:
        populate_by_name = True


class ResponseEnvelope(BaseModel):
    """HTTP response wrapped for WebSocket transport."""

    type: Literal["response"] = "response"
    request_id: str = Field(..., description="ID matching the original request")
    status_code: int = Field(..., description="HTTP status code")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    body_text: Optional[str] = Field(None, description="Response body as text")
    body_b64: Optional[str] = Field(
        None, description="Response body as base64 (for binary data)"
    )


class ErrorMessage(BaseModel):
    """Error message for routing failures or other issues."""

    type: Literal["error"] = "error"
    request_id: Optional[str] = Field(None, description="Related request ID if applicable")
    error_code: str = Field(..., description="Error code (e.g., AGENT_OFFLINE)")
    message: str = Field(..., description="Human-readable error message")


class StartTaskMessage(BaseModel):
    """Server-initiated task for local agent (proxy will send via A2A)."""

    type: Literal["start_task"] = "start_task"
    task_id: str = Field(..., description="Unique task identifier")
    task_config: dict = Field(..., description="Task configuration to send to agent")


# Union type for all WebSocket messages
WebSocketMessage = (
    RegisterMessage
    | RegisterAckMessage
    | RequestEnvelope
    | ResponseEnvelope
    | ErrorMessage
    | StartTaskMessage
)
