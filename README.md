# A2A Agent Proxy Architecture

WebSocket-based proxy architecture enabling A2A-compliant agents on different machines to communicate through a central server.

## Overview

This project implements a distributed agent communication system where agents communicate via HTTP+JSON (A2A standard) while being transparently routed through WebSocket proxies. This enables:

- **Server-initiated tasks**: Central server can assign work to agents
- **Cross-machine communication**: Agents run on different machines/containers
- **A2A compliance**: Standard HTTP+JSON semantics preserved
- **Transparent proxying**: Agents don't know they're using WebSocket routing

## Architecture

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

### Key Design Principle

**Proxies use A2A client for local communication, WebSocket for remote communication.**

- **Local**: Proxy ↔ Agent = A2A HTTP client (uses `my_a2a.send_message()`)
- **Remote**: Proxy ↔ Server = WebSocket envelopes

This avoids URL encoding issues and maintains proper A2A message format.

## Installation

```bash
uv sync
```

## Quick Start

Launch complete evaluation with WebSocket proxy routing:

```bash
uv run python main.py launch
```

This starts:
1. Central WebSocket server on `ws://localhost:8000`
2. Green agent + proxy (agent: `localhost:9001`, proxy: `localhost:9101`)
3. White agent + proxy (agent: `localhost:9002`, proxy: `localhost:9102`)
4. Server-initiated task assignment to green agent

## Configuration

Before running, configure `.env` with:
```
OPENAI_API_KEY=your_key_here
```

## Project Structure

```
src/
├── server/
│   ├── __init__.py
│   └── server.py           # WebSocket router
├── proxy/
│   ├── __init__.py
│   ├── messages.py         # Pydantic message schemas
│   └── agent_proxy.py      # HTTP/WS adapter
├── green_agent/
│   └── agent.py            # Assessment manager agent
├── white_agent/
│   └── agent.py            # Target agent being tested
├── my_util/                # A2A utility functions
└── launcher.py             # Evaluation coordinator
```

## Components

### 1. Central WebSocket Server (`src/server/server.py`)

**Purpose**: Routes messages between agents

**Endpoints**:
- `WS /ws/{agent_id}` - WebSocket connection for agent proxies
- `GET /health` - Health check with active agents list
- `GET /agents` - List connected agents
- `POST /tasks/send` - Server-initiated task assignment

**State Management**:
- `agents: Dict[agent_id, WebSocket]` - Active agent connections
- `pending: Dict[request_id, WebSocket]` - In-flight requests for response routing

**Message Types**:
- `register` - Agent proxy registers with server
- `start_task` - Server assigns task to agent (proxy handles A2A conversion)
- `request` - Forward HTTP request between agents
- `response` - Return response to requesting agent
- `error` - Error notifications

### 2. Agent Proxy (`src/proxy/agent_proxy.py`)

**Purpose**: Bidirectional adapter between local A2A agent and WebSocket server

**Dual Interface**:
- **HTTP Server**: Exposes `/agents/{target_agent_id}/*` endpoints for outgoing requests
- **WebSocket Client**: Maintains connection to central server

**Key Features**:
- **Server-Initiated Tasks**: Receives `start_task` messages, formats with proxy URLs, sends via A2A client
- **Outgoing Requests**: HTTP from agent → WebSocket envelope → server
- **Incoming Requests**: WebSocket envelope → HTTP to local agent
- **Response Correlation**: Matches responses to requests using `request_id` and asyncio Futures

### 3. Agents

**Green Agent** (`src/green_agent/agent.py`):
- Assessment manager that tests other agents
- Accepts `server_url`, `agent_id`, `proxy_port` parameters
- Spawns proxy subprocess on startup
- Uses standard A2A client code (`my_a2a.send_message()`)

**White Agent** (`src/white_agent/agent.py`):
- Target agent being tested
- Same proxy-spawning modifications as green agent
- Self-contained, runs A2A HTTP server

## Message Schemas

All WebSocket messages use Pydantic schemas defined in `src/proxy/messages.py`:

### Registration
```json
{
  "type": "register",
  "agent_id": "green"
}
```

### Start Task (Server → Proxy)
```json
{
  "type": "start_task",
  "task_id": "uuid-1234",
  "task_config": {
    "task": "Your task is...",
    "agents": {"white-1": {...}},
    "env_config": {...}
  }
}
```

### Request Envelope (Inter-Agent Communication)
```json
{
  "type": "request",
  "request_id": "uuid-1234",
  "from": "green",
  "to": "white-1",
  "method": "POST",
  "path": "/v1/message:send",
  "headers": {"Content-Type": "application/json"},
  "body_text": "{...A2A message...}"
}
```

### Response Envelope
```json
{
  "type": "response",
  "request_id": "uuid-1234",
  "status_code": 200,
  "headers": {"Content-Type": "application/json"},
  "body_text": "{...A2A response...}"
}
```

## Message Flows

### Initialization

1. **Server starts**: `ws://localhost:8000`
2. **Green agent starts**:
   - Spawns proxy subprocess
   - Proxy connects to server via WebSocket
   - Proxy sends `{"type": "register", "agent_id": "green"}`
   - Agent starts HTTP server on `localhost:9001`
   - Proxy starts HTTP server on `localhost:9101`
3. **White agent starts**: Same pattern as green
4. **Server state**: `agents = {"green": <ws1>, "white-1": <ws2>}`

### Server-Initiated Task

```
1. Server → Green Proxy (WebSocket):
   StartTaskMessage {
     task_config: {
       "task": "Test this agent",
       "agents": {"white-1": {...}},
       "env_config": {...}
     }
   }

2. Green Proxy:
   - Receives start_task message
   - Formats text with XML tags:
     """
     Your task is to instantiate tau-bench...
     <white_agent_url>
     http://localhost:9101/agents/white-1/
     </white_agent_url>
     <env_config>
     {...}
     </env_config>
     """
   - Uses my_a2a.send_message(local_agent_url, task_text)

3. Green Agent:
   - Receives proper A2A message
   - Parses XML tags
   - Extracts white_agent_url: "http://localhost:9101/agents/white-1/"
```

### Inter-Agent Communication

```
1. Green Agent calls:
   my_a2a.send_message("http://localhost:9101/agents/white-1/", message)

2. Green Proxy receives HTTP:
   POST /agents/white-1/v1/message:send
   - Extracts target: "white-1" from URL path
   - Creates RequestEnvelope(from="green", to="white-1", ...)
   - Sends via WebSocket to server

3. Server routes to White's proxy:
   - Stores pending[request_id] = green's WebSocket
   - Forwards to white-1's WebSocket

4. White Proxy receives RequestEnvelope:
   - Uses httpx with raw_path to forward to localhost:9002/v1/message:send
   - Avoids URL encoding the colon

5. White Agent processes:
   - Returns A2A response

6. White Proxy wraps response:
   - Creates ResponseEnvelope
   - Sends via WebSocket to server

7. Server routes back to Green's proxy:
   - Looks up pending[request_id]
   - Forwards to green's WebSocket

8. Green Proxy returns HTTP response:
   - Completes pending future
   - Returns to green agent's waiting HTTP call
```

## Running Individual Components

### Start server only
```bash
uv run python main.py server
```

### Start green agent only
```bash
uv run python main.py green
```

### Start white agent only
```bash
uv run python main.py white
```

### Start with proxy from Python

**Green agent with proxy**:
```python
from src.green_agent import start_green_agent
start_green_agent(
    server_url="ws://localhost:8000",
    agent_id="green",
    proxy_port=9101
)
```

**White agent with proxy**:
```python
from src.white_agent import start_white_agent
start_white_agent(
    server_url="ws://localhost:8000",
    agent_id="white-1",
    proxy_port=9102
)
```

## Development

### Docker Deployment

The proxy architecture allows agents to be deployed in separate containers or machines while maintaining A2A compatibility. Each agent container runs two processes:
- **Agent process**: Standard A2A HTTP server
- **Proxy process**: WebSocket adapter (auto-started by agent)

Example Dockerfile pattern:
```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["python", "-m", "src.green_agent.agent"]  # Proxy auto-starts
```

### Testing

Run basic proxy architecture tests:
```bash
uv run python test_proxy.py
```

### Debugging

Use the health endpoint to check server state:
```bash
curl http://localhost:8000/health
```

Returns:
```json
{
  "status": "healthy",
  "active_agents": ["green", "white-1"],
  "pending_requests": 0
}
```

## Key Design Decisions

1. **A2A client for local communication**: Proxies use `my_a2a.send_message()` to talk to local agents, avoiding httpx URL encoding issues with colons in paths like `/v1/message:send`

2. **WebSocket for remote communication**: Inter-proxy communication uses WebSocket envelopes with JSON serialization

3. **Server-initiated tasks**: Server sends `start_task` message with simple task config, proxy handles A2A conversion and URL translation

4. **URL-based routing**: `/agents/{agent_id}/*` pattern enables deterministic addressing - green agent can call `http://localhost:9101/agents/white-1/v1/message:send` without knowing white's actual location

5. **Proxy URL injection**: Server sends agent IDs in task config, proxy translates to local proxy URLs (e.g., `white-1` → `http://localhost:9101/agents/white-1/`)

6. **Self-starting proxies**: Agents spawn their own proxy subprocess for deployment simplicity - one container = agent + proxy

7. **Minimal agent changes**: Only startup function signatures changed, core agent logic remains untouched

8. **Future-based response correlation**: Proxies use `asyncio.Future` with `pending_responses` dict to convert bidirectional WebSocket streaming into synchronous-looking HTTP request/response cycles

## Advantages

- ✅ **A2A-compliant**: Maintains HTTP+JSON semantics
- ✅ **Server-initiated communication**: Server can assign tasks to agents
- ✅ **Distributed deployment**: Agents can run on different machines/containers
- ✅ **Transparent proxying**: Agents don't know they're using WebSocket routing
- ✅ **Bidirectional communication**: Full request/response cycles preserved
- ✅ **No URL encoding issues**: Uses A2A client locally, httpx with `raw_path` for remote
- ✅ **Scalable**: Can be extended with pub/sub or message queues
- ✅ **Works across network boundaries**: Containers, machines, cloud deployments

## Example: Tau-Bench Assessment

This codebase demonstrates the architecture with Tau-Bench, a standardized agent assessment framework:

1. **Server** sends task to **Green Agent** (assessment manager)
2. **Green** parses task, extracts **White Agent** URL from XML tags
3. **Green** calls White via proxy: `POST http://localhost:9101/agents/white-1/v1/message:send`
4. **Green's proxy** wraps request in WebSocket envelope, sends to server
5. **Server** routes to White's proxy via WebSocket
6. **White's proxy** forwards to local White agent via HTTP
7. **White** processes and responds
8. Response flows back through: White's proxy → Server → Green's proxy → Green agent

The entire flow is transparent to both agents - they just use standard A2A HTTP calls.

## License

See LICENSE file for details.
