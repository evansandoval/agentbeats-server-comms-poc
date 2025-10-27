# A2A Agent Proxy Architecture

This document describes the WebSocket-based proxy architecture that enables A2A-compliant agents on different machines to communicate through a central server.

## Architecture Overview

```
┌─────────────────┐       ┌──────────────┐       ┌─────────────────┐
│ Green Agent     │ HTTP  │ Green Proxy  │  WS   │ Central Server  │
│ (localhost:9001)│<─────>│(localhost:9101)│<────>│ (localhost:8000)│
└─────────────────┘       └──────────────┘       └─────────────────┘
                                                          │
                                                          │ WS
                                                          ▼
┌─────────────────┐       ┌──────────────┐       ┌─────────────────┐
│ White Agent     │ HTTP  │ White Proxy  │  WS   │                 │
│ (localhost:9002)│<─────>│(localhost:9102)│<────>│                 │
└─────────────────┘       └──────────────┘       └─────────────────┘
```

## Components

### 1. Central WebSocket Server (`src/server/server.py`)

**Purpose**: Routes messages between agents

**Endpoints**:
- `WS /ws/{agent_id}` - WebSocket connection for agent proxies
- `GET /health` - Health check
- `GET /agents` - List connected agents

**State Management**:
- `AGENTS: Dict[agent_id, WebSocket]` - Active agent connections
- `PENDING: Dict[request_id, WebSocket]` - In-flight requests

**Message Types**:
- `register` - Agent proxy registers with server
- `request` - Forward HTTP request to target agent
- `response` - Return response to requesting agent
- `error` - Error notifications

### 2. Agent Proxy (`src/proxy/agent_proxy.py`)

**Purpose**: Bidirectional HTTP ↔ WebSocket adapter

**Dual Interface**:
- **HTTP Server**: Exposes `/agents/{target_agent_id}/*` endpoints
- **WebSocket Client**: Maintains connection to central server

**Key Features**:
- **URL Translation**: Automatically injects proxy URLs into agent references
- **Request Routing**: Extracts target from URL path, routes via WebSocket
- **Response Correlation**: Matches responses to requests using `request_id`

**Example Flow**:
```python
# Green agent calls (thinks it's calling white agent directly):
POST http://localhost:9101/agents/white-1/v1/message:send

# Proxy extracts target "white-1", forwards via WebSocket to server
# Server routes to white-1's proxy
# White proxy forwards to local white agent
# Response flows back the same path
```

### 3. Modified Agents

**Green Agent** (`src/green_agent/agent.py`):
- Accepts `server_url`, `agent_id`, `proxy_port` parameters
- Spawns proxy subprocess on startup
- No other changes - uses existing A2A client code

**White Agent** (`src/white_agent/agent.py`):
- Same modifications as green agent
- Self-contained, runs A2A HTTP server

## Message Schemas (`src/proxy/messages.py`)

### Registration
```json
{
  "type": "register",
  "agent_id": "green"
}
```

### Request Envelope
```json
{
  "type": "request",
  "request_id": "uuid-1234",
  "from": "green",
  "to": "white-1",
  "method": "POST",
  "path": "/v1/message:send",
  "headers": {"Content-Type": "application/json"},
  "body_text": "{...}"
}
```

### Response Envelope
```json
{
  "type": "response",
  "request_id": "uuid-1234",
  "status_code": 200,
  "headers": {"Content-Type": "application/json"},
  "body_text": "{...}"
}
```

## Complete Message Flow

### Initialization
1. **Server starts**: `ws://localhost:8000`
2. **Green agent starts**:
   - Spawns proxy subprocess
   - Proxy connects to server via WebSocket
   - Proxy sends `{"type": "register", "agent_id": "green"}`
   - Agent starts HTTP server on `localhost:9001`
   - Proxy starts HTTP server on `localhost:9101`
3. **White agent starts**: Same pattern as green
4. **Server state**: `AGENTS = {"green": <ws1>, "white-1": <ws2>}`

### Server-Initiated Task
```
Server → Green's WebSocket:
  RequestEnvelope(from="server", to="green", body={
    "agents": {"white-1": {"agent_id": "white-1"}}
  })

Green Proxy receives:
  - Translates to: {"agents": {"white-1": {"url": "http://localhost:9101/agents/white-1"}}}
  - Forwards HTTP POST to green agent (localhost:9001)

Green Agent receives task:
  - Sees white agent URL: http://localhost:9101/agents/white-1
  - Makes HTTP call (thinks it's calling white agent directly)
```

### Inter-Agent Communication
```
Green Agent:
  POST http://localhost:9101/agents/white-1/v1/message:send

Green Proxy:
  - Receives HTTP request
  - Extracts target: "white-1" from URL path
  - Creates RequestEnvelope(from="green", to="white-1")
  - Sends via WebSocket to server

Server:
  - Routes to white-1's WebSocket
  - Stores PENDING[request_id] = green's WebSocket

White Proxy:
  - Receives RequestEnvelope
  - Converts to HTTP POST
  - Forwards to localhost:9002/v1/message:send

White Agent:
  - Processes request
  - Returns HTTP response

White Proxy:
  - Wraps in ResponseEnvelope
  - Sends via WebSocket to server

Server:
  - Looks up PENDING[request_id]
  - Forwards to green's WebSocket

Green Proxy:
  - Converts to HTTP response
  - Returns to waiting green agent
```

## URL Translation

The proxy automatically translates agent references in incoming messages:

**Before (from server/remote agent)**:
```json
{
  "agents": {
    "white-1": {
      "agent_id": "white-1",
      "description": "Target agent"
    }
  }
}
```

**After (forwarded to local agent)**:
```json
{
  "agents": {
    "white-1": {
      "agent_id": "white-1",
      "description": "Target agent",
      "url": "http://localhost:9101/agents/white-1"
    }
  }
}
```

This maintains the illusion that agents are communicating directly via HTTP URLs.

## Running the System

### Install Dependencies
```bash
uv sync
```

### Test Basic Proxy Architecture
```bash
uv run python test_proxy.py
```

### Run Complete Evaluation with Proxy
```bash
uv run python main.py launch-proxy
```

### Run Individual Components

**Start server**:
```bash
uv run python main.py server
```

**Start green agent with proxy**:
```python
from src.green_agent import start_green_agent
start_green_agent(
    server_url="ws://localhost:8000",
    agent_id="green",
    proxy_port=9101
)
```

**Start white agent with proxy**:
```python
from src.white_agent import start_white_agent
start_white_agent(
    server_url="ws://localhost:8000",
    agent_id="white-1",
    proxy_port=9102
)
```

## Docker Deployment (Future)

Each component will run in its own container:
- Server container: Central router
- Green agent container: Runs agent + proxy (2 processes)
- White agent container: Runs agent + proxy (2 processes)

All communicate via Docker bridge network.

## Key Design Decisions

1. **URL-based routing**: `/agents/{agent_id}/*` pattern eliminates need for message parsing
2. **Dynamic URL translation**: Proxies inject URLs on-the-fly for seamless agent experience
3. **Server-initiated flow**: Server controls task assignment and orchestration
4. **Self-starting proxies**: Agents spawn their own proxy subprocess for deployment simplicity
5. **Minimal agent changes**: Only startup signatures changed, core logic untouched
6. **HTTP semantics preserved**: Full request/response cycle maintained through WebSocket transport

## Advantages

- ✅ A2A-compliant (HTTP+JSON)
- ✅ Server can initiate requests to agents
- ✅ Preserves HTTP semantics exactly
- ✅ Supports ephemeral conversations
- ✅ Scalable via pub/sub or in-memory queue
- ✅ Agents don't know they're using proxies
- ✅ Works across network boundaries (containers, machines)

## Files

```
src/
├── server/
│   ├── __init__.py
│   └── server.py           # WebSocket router
├── proxy/
│   ├── __init__.py
│   ├── messages.py         # Pydantic schemas
│   └── agent_proxy.py      # HTTP/WS adapter
├── green_agent/
│   └── agent.py            # Modified startup
├── white_agent/
│   └── agent.py            # Modified startup
└── launcher.py             # Updated with proxy flow
test_proxy.py               # Basic tests
PROXY_ARCHITECTURE.md       # This file
```
