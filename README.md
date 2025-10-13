# AgentBeats Local Agent Proxy - PoC

This proof of concept enables **local (offline) agents** to communicate with deployed AgentBeats agents via the A2A (Agent-to-Agent) protocol.

## Quick Commands

```bash
# Start local agent (Terminal 1)
python simple_local_agent.py

# Run test (Terminal 2)
python test_red_agent_only.py

# Check for zombie processes
ps aux | grep -E "(agentbeats|simple_local_agent)" | grep -v grep
lsof -i :9021 -i :9031

# Kill zombies
pkill -9 -f "agentbeats run"
pkill -9 -f "simple_local_agent"
```

📖 **For detailed terminal-based testing guide, see [TERMINAL_TESTING.md](TERMINAL_TESTING.md)**

## Current Status

**Last Updated:** 2025-10-12

### What's Working ✅

1. **Red Agent with Clean Developer UX**
   - Auto-starting proxy on port 9021
   - Framework (`AgentRunner`) handles all infrastructure
   - Agents only contain business logic (`AgentBase`)
   - A2A protocol compliance
   - Test script works: `python test_red_agent_only.py`

2. **Green Agent A2A Communication**
   - Running on port 9031
   - Has `talk_to_agent()` tool for A2A calls to other agents
   - Can orchestrate battles via LLM reasoning
   - Using gpt-4o-mini model

3. **Developer Experience**
   - Clean agent API - just implement `process_message()`
   - No proxy URLs, HTTP requests, or polling loops in agent code
   - Framework abstracts all infrastructure

### What Needs Testing 🚧

- Full green→red battle flow via `trigger_battle.py`
- End-to-end A2A communication with LLM orchestration

### TODO

- WebSocket support (currently uses polling at 3s intervals)
- Error handling and retry logic
- Authentication/authorization
- Production deployment guide

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Green Agent (LLM)                        │
│  - Battle orchestrator                                      │
│  - Has talk_to_agent(message, agent_url) tool             │
│  - Makes outbound A2A calls to red agent                   │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ A2A Protocol (POST /tasks)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Red Agent Proxy                           │
│  - A2A Server (/.well-known/agent.json, /tasks)           │
│  - Receives inbound A2A messages                           │
│  - Queues messages for local agent                         │
│  - Streams responses back in A2A format                    │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ Internal (hidden from developers)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                Framework (AgentRunner)                      │
│  - Polls proxy for messages                                │
│  - Calls agent.process_message()                           │
│  - Submits responses to proxy                              │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Local Red Agent (Your Code!)                   │
│  - Inherits from AgentBase                                 │
│  - Implements process_message() ONLY                       │
│  - Pure business logic - no infrastructure!                │
└─────────────────────────────────────────────────────────────┘
```

**Key Innovation:** Agent developers only write business logic. All infrastructure
(proxy communication, HTTP requests, A2A protocol, polling) is abstracted away.

## Quick Start

### Prerequisites

- Python 3.11+
- AgentBeats: `pip install agentbeats`
- OpenAI API key (only needed for green agent)

### Option A: Quick Test (Red Agent Only)

**Terminal 1 - Start Red Agent:**
```bash
python simple_local_agent.py
```

This single command:
- ✅ Starts the proxy server on port 9021
- ✅ Starts the local agent
- ✅ Loads the agent card
- ✅ Framework begins polling for messages

**Terminal 2 - Test Direct A2A Communication:**
```bash
python test_red_agent_only.py
```

This sends a test A2A message directly to the red agent and verifies the flow works.

### Option B: Full Green-Red Battle (Two Agent Setup)

**Terminal 1 - Start Green Agent (Orchestrator):**
```bash
# Load environment variables (for OpenAI API key)
source .env

# Start green agent on port 9031
python -m agentbeats run green_agent_card.toml   --launcher_host 0.0.0.0 --launcher_port 9030   --agent_host 0.0.0.0 --agent_port 9031   --model_type openai --model_name gpt-4o-mini   --tool green_tools.py 2>&1 | tee logs/green_output.txt
```

Expected output:
```
INFO: Green agent starting on port 9031
INFO: Loaded tools: talk_to_agent, evaluate_battle, generate_test_data
```

**Terminal 2 - Start Red Agent:**
```bash
python simple_local_agent.py 2>&1 | tee logs/red_output.txt
```

Expected output:
```
INFO: Starting proxy server on 0.0.0.0:9021
INFO: Loaded agent card: POC Red Agent (via Proxy)
INFO: Proxy server started successfully
INFO: AgentRunner initialized for SimpleRedAgent
```

**Terminal 3 - Trigger Battle:**
```bash
python trigger_battle.py 2>&1 | tee logs/launcher_output.txt
```

This triggers the green agent to use `talk_to_agent()` tool to send an A2A message to the red agent, demonstrating the full orchestration flow.

## File Structure

```
.
├── agent_base.py             # Abstract base class for agents (NEW!)
├── agent_runner.py           # Framework agent loop (NEW!)
├── proxy_wrapper.py          # Auto-proxy management + ProxyClient
├── red_agent_proxy.py        # A2A ↔ local agent bridge
│
├── simple_local_agent.py     # Example red agent (REFACTORED)
├── example_custom_agent.py   # Template for new agents (UPDATED)
├── red_agent_card.toml       # Red agent configuration
│
├── green_tools.py            # Green agent tools (with talk_to_agent!)
├── green_agent_card.toml     # Green agent configuration
│
├── test_red_agent_only.py    # Test script
├── start_demo.sh             # Start green + red agents
├── stop_demo.sh              # Utility to stop all processes
├── trigger_battle.py         # Trigger green→red battle (UPDATED)
│
├── README.md                 # Main documentation (includes status)
├── TERMINAL_TESTING.md       # Terminal-based testing guide
├── DEMO_GUIDE.md             # Quick 5-minute demo
├── TODO.md                   # Detailed task tracking
│
├── .env                      # API keys (gitignored)
├── .env.example              # API key template
├── .gitignore
└── requirements.txt          # Python dependencies
```

## Creating Your Own Local Agent

### Step 1: Create Agent Card

Create `my_agent_card.toml`:

```toml
name = "My Agent"
description = "What my agent does"
url = "http://localhost:9025/"
host = "0.0.0.0"
port = 9025
version = "1.0.0"
defaultInputModes = ["text"]
defaultOutputModes = ["text"]

[capabilities]
streaming = true

[[skills]]
id = "my_skill"
name = "My Skill"
description = "What my agent can do"
tags = ["custom"]
examples = ["Example task"]
```

### Step 2: Create Agent Code

Create `my_agent.py`:

```python
from typing import Dict, Any
from agent_base import AgentBase
from proxy_wrapper import run_with_proxy

class MyAgent(AgentBase):
    """
    Your custom agent - just business logic!

    No infrastructure code needed:
    - No proxy_url parameters
    - No poll_messages() or submit_response()
    - No HTTP requests
    - No polling loops

    Just implement process_message()!
    """

    def process_message(self, message: Dict[str, Any]) -> str:
        """
        Process a message and return your response.

        This is the ONLY method you need to implement!
        """
        # Extract message text
        msg_content = message.get("message", {})
        parts = msg_content.get("parts", [])
        text = " ".join(p.get("text", "") for p in parts if p.get("type") == "text")

        # Your business logic here!
        response = f"My agent processed: {text}"

        return response

if __name__ == "__main__":
    # Create agent (no parameters!)
    agent = MyAgent()

    # Run with framework (one line!)
    run_with_proxy(
        agent,
        agent_card_path="my_agent_card.toml",
        proxy_port=9025
    )
```

### Step 3: Run It

```bash
python my_agent.py
```

That's it! The framework handles:
- Starting the proxy server
- Polling for messages
- Calling your `process_message()` method
- Submitting responses
- A2A protocol details

**You just write the business logic!**

## How It Works

### 1. Proxy Server (`red_agent_proxy.py`)

Implements three interfaces:

**A2A Server Interface:**
- `GET /.well-known/agent.json` - Serves agent card
- `POST /tasks` - Receives A2A messages, returns streaming responses

**Launcher Interface:** (for AgentBeats backend)
- `POST /reset` - Receives battle context
- Notifies backend when ready

**Local Agent Interface:**
- `GET /poll_messages` - Local agent polls for new messages
- `POST /submit_response` - Local agent submits responses

### 2. Framework Components

**`agent_base.py`** - Abstract base class
- Defines single method: `process_message(message) -> str`
- Agent developers inherit and implement business logic only

**`agent_runner.py`** - Agent execution loop
- Polls proxy for messages
- Calls agent's `process_message()` method
- Submits responses back to proxy
- Hidden from agent developers

**`proxy_wrapper.py`** - Infrastructure management
- `ProxyClient` class: Handles proxy communication
- `run_with_proxy()` function: Orchestrates everything

### 3. Message Flow

```
1. Green Agent (LLM) calls talk_to_agent(message, red_agent_url)
2. A2A message arrives at red proxy: POST /tasks
3. Proxy queues message internally
4. AgentRunner polls: GET /poll_messages
5. AgentRunner calls agent.process_message()
6. AgentRunner submits: POST /submit_response
7. Proxy streams response back to green agent in A2A format
```

**Key Point:** Steps 3-6 are completely hidden from agent developers!

## Testing

### Terminal-Based Testing (Recommended)

Using separate terminals gives you better process control and makes it easier to stop components.

#### Step 1: Check for Orphaned Processes

Before starting, clean up any zombie processes:

```bash
# Check for running agent processes
ps aux | grep -E "(agentbeats|simple_local_agent|red_agent_proxy)"

# Check specific ports
lsof -i :9021 -i :9031

# Kill zombie processes if found
pkill -9 -f "agentbeats run"
pkill -9 -f "simple_local_agent"
```

#### Step 2: Terminal Layout

Open 3 terminals:

**Terminal 1 - Local Red Agent:**
```bash
python simple_local_agent.py
```

Expected output:
```
INFO: Starting proxy server on 0.0.0.0:9021
INFO: Loaded agent card: POC Red Agent (via Proxy)
INFO: Proxy server started successfully
INFO: Red agent started!
INFO: Polling for messages...
```

**Terminal 2 - Test Script:**
```bash
python test_red_agent_only.py
```

Expected output:
```
✓ Red agent proxy is ready
✓ Sending test message...
[STATUS] Task state: running
[MESSAGE] Red agent completed task for battle test_battle_XXX...
[STATUS] Task state: completed
✓ Test completed successfully!
```

**Terminal 3 - Logs (Optional):**
```bash
tail -f logs/red_agent.log
```

You'll see:
- Proxy startup
- Agent polling
- Message received and processed
- Response submitted

#### Step 3: Stop Everything

Just press `Ctrl+C` in each terminal. Much easier than hunting down PIDs!

### Automated Testing (Alternative)

If you prefer scripts:

```bash
# Start everything
./start_demo.sh

# Run test
python test_red_agent_only.py

# Stop everything
./stop_demo.sh
```

**Note:** The automated approach can leave zombie processes. Use `ps aux | grep agent` to verify cleanup.

## API Reference

### `run_with_proxy(agent, agent_card_path, proxy_host, proxy_port, poll_interval)`

Runs a local agent with automatic proxy startup and framework handling.

**Parameters:**
- `agent` - Your agent instance (must inherit from `AgentBase`)
- `agent_card_path` - Path to TOML agent card
- `proxy_host` - Proxy bind address (default: `"0.0.0.0"`)
- `proxy_port` - Proxy port (default: `9021`)
- `poll_interval` - Seconds between message polls (default: `3.0`)

**Example:**
```python
from agent_base import AgentBase
from proxy_wrapper import run_with_proxy

class MyAgent(AgentBase):
    def process_message(self, message):
        return "my response"

agent = MyAgent()
run_with_proxy(agent, "my_card.toml", proxy_port=9025)
```

### Agent Class Requirements

```python
from typing import Dict, Any
from agent_base import AgentBase

class MyAgent(AgentBase):
    def process_message(self, message: Dict[str, Any]) -> str:
        """
        ONLY method you need to implement!

        Args:
            message: Dict with 'task_id', 'message', 'timestamp'

        Returns:
            str: Your response text
        """
        # Your business logic here
        return "my response"
```

### Green Agent Tools

**`talk_to_agent(message: str, agent_url: str) -> str`**

Green agent (LLM) uses this tool to send A2A messages to other agents:

```python
# Example: Green agent calling red agent
response = talk_to_agent(
    message="Perform your task. battle_id: battle_123",
    agent_url="http://localhost:9021"
)
```

### Proxy Endpoints (Internal - Hidden from Developers)

**A2A Server Interface:**
```python
# Get agent card
GET {proxy_url}/.well-known/agent.json

# Send A2A message
POST {proxy_url}/tasks
Body: {"task_id": "...", "message": {...}}
Returns: Streaming NDJSON response
```

**Local Agent Interface (used by framework):**
```python
# Poll for messages (AgentRunner uses this)
GET {proxy_url}/poll_messages
Returns: {"messages": [...]}

# Submit response (AgentRunner uses this)
POST {proxy_url}/submit_response
Body: {"response": "your text"}
```

**Developers never call these directly!**

## Recent Updates

✅ **Completed:**
- Abstract base class (`AgentBase`) for clean developer UX
- Framework agent loop (`AgentRunner`) handles all infrastructure
- `talk_to_agent()` tool for green agent A2A communication
- Refactored all examples to use new architecture
- Complete abstraction of proxy URLs from agent code

## Known Issues & TODOs

### High Priority

- [ ] **Error handling** - No retry logic or timeout handling
  - Add exponential backoff for polling
  - Handle proxy crashes gracefully

- [ ] **WebSocket support** - Currently uses polling (3 second interval)
  - Replace HTTP polling with WebSocket for real-time communication
  - More efficient for high-frequency messages

### Medium Priority

- [ ] **Authentication** - No security currently
  - Add OAuth/JWT for A2A messages
  - Secure local agent ↔ proxy communication

- [ ] **Multiple agent support** - Only one local agent at a time
  - Support multiple local agents with different ports
  - Dynamic port allocation

- [ ] **Battle orchestration testing** - Test full green→red flow
  - Verify `talk_to_agent()` tool works end-to-end
  - Test battle coordination scenarios

### Low Priority

- [ ] **Logging improvements** - Better structured logging
- [ ] **Metrics/monitoring** - Track message latency, success rates
- [ ] **Deployment guide** - Docker, cloud deployment instructions
- [ ] **Agent discovery** - Auto-register with backend

## Troubleshooting

### Proxy won't start

```bash
# Check if port is in use
lsof -i :9021

# Kill process using port
kill -9 <PID>
```

### Agent not receiving messages

1. Check proxy is running:
   ```bash
   curl http://localhost:9021/.well-known/agent.json
   ```

2. Check agent is polling:
   ```bash
   tail -f logs/red_agent.log | grep "poll_messages"
   ```

3. Send test message:
   ```bash
   python test_red_agent_only.py
   ```

### Port conflicts

Change port in:
- Agent card TOML file (`port =`)
- Agent initialization (`proxy_url="http://localhost:PORT"`)
- `run_with_proxy()` call (`proxy_port=PORT`)

## Contributing

This is a proof of concept. Known limitations:
- Polling instead of WebSocket
- No authentication
- Minimal error handling
- Green agent integration incomplete

Pull requests welcome for TODOs listed above!

## References

- [AgentBeats GitHub](https://github.com/agentbeats/agentbeats)
- [A2A Protocol](https://a2a-protocol.org/)
- [A2A Specification](https://github.com/a2aproject/A2A)

## License

MIT (or match AgentBeats license)
