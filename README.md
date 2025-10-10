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
📊 **For current system status, see [CURRENT_STATUS.md](CURRENT_STATUS.md)**

## What This PoC Demonstrates

✅ **Working:**
- Local agent with auto-starting proxy server
- A2A protocol communication (streaming responses)
- Message polling and response submission
- Battle ID extraction and task completion

🚧 **TODO:**
- Green agent integration (requires AgentBeats backend)
- Full battle orchestration flow
- WebSocket support (currently uses polling)
- Authentication/authorization
- Error handling and retries
- Production deployment

## Architecture

```
[Any A2A Agent]
      │
      │ A2A Protocol (HTTP/JSON)
      │ POST /tasks with streaming response
      ▼
┌─────────────────┐       ┌──────────────────┐
│  Red Agent      │◄──────┤  Local Red       │
│  Proxy          │ HTTP  │  Agent           │
│  (localhost:    │──────►│  (Python)        │
│   9021)         │       └──────────────────┘
└─────────────────┘
    │
    │ Implements:
    │ 1. A2A Server (/.well-known/agent.json, /tasks)
    │ 2. Launcher Interface (/reset)
    │ 3. Local Communication (/poll_messages, /submit_response)
    │
```

## Quick Start

### Prerequisites

- Python 3.11+
- AgentBeats: `pip install agentbeats`
- OpenAI API key (only needed for green agent)

### 1. Run the Local Agent (Auto-Proxy)

```bash
python simple_local_agent.py
```

This single command:
- ✅ Starts the proxy server on port 9021
- ✅ Starts the local agent
- ✅ Loads the agent card
- ✅ Begins polling for messages

### 2. Test the Communication

```bash
python test_red_agent_only.py
```

This sends a test A2A message and verifies the complete flow works.

## File Structure

```
.
├── red_agent_card.toml       # Agent configuration
├── red_agent_proxy.py        # A2A ↔ local agent bridge
├── proxy_wrapper.py          # Auto-proxy management
├── simple_local_agent.py     # Example local agent (WORKING)
├── example_custom_agent.py   # Template for new agents
├── test_red_agent_only.py    # Test script
│
├── green_agent_card.toml     # TODO: needs backend integration
├── green_tools.py            # TODO: needs backend integration
├── start_demo.sh             # TODO: green agent startup incomplete
├── stop_demo.sh              # Utility to stop all processes
├── trigger_battle.py         # TODO: needs /tasks endpoint fix
│
├── README.md                 # Main documentation
├── TERMINAL_TESTING.md       # Terminal-based testing guide (recommended)
├── CURRENT_STATUS.md         # Current system status & running processes
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
import time
import requests
from proxy_wrapper import run_with_proxy

class MyAgent:
    def __init__(self, proxy_url="http://localhost:9025"):
        self.proxy_url = proxy_url

    def poll_messages(self):
        response = requests.get(f"{self.proxy_url}/poll_messages")
        return response.json().get("messages", [])

    def submit_response(self, text):
        requests.post(
            f"{self.proxy_url}/submit_response",
            json={"response": text}
        )

    def run(self):
        while True:
            for msg in self.poll_messages():
                # Your logic here!
                response = f"Processed: {msg}"
                self.submit_response(response)
            time.sleep(1)

if __name__ == "__main__":
    agent = MyAgent()
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

That's it! Your agent is now A2A-compatible.

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

### 2. Auto-Proxy Wrapper (`proxy_wrapper.py`)

The `run_with_proxy()` function:
1. Loads your agent card
2. Starts proxy server in background thread
3. Calls your agent's `run()` method

### 3. Message Flow

```
1. A2A message arrives at proxy: POST /tasks
2. Proxy queues message internally
3. Local agent polls: GET /poll_messages
4. Local agent processes message
5. Local agent submits response: POST /submit_response
6. Proxy streams response back to caller in A2A format
```

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

### `run_with_proxy(agent, agent_card_path, proxy_host, proxy_port)`

Runs a local agent with automatic proxy startup.

**Parameters:**
- `agent` - Your agent instance (must have `run()` method)
- `agent_card_path` - Path to TOML agent card
- `proxy_host` - Proxy bind address (default: `"0.0.0.0"`)
- `proxy_port` - Proxy port (default: `9021`)

**Example:**
```python
agent = MyAgent()
run_with_proxy(agent, "my_card.toml", proxy_port=9025)
```

### Agent Class Requirements

```python
class MyAgent:
    def __init__(self, proxy_url: str):
        """Must accept proxy_url parameter"""
        self.proxy_url = proxy_url

    def run(self):
        """Main loop - called by run_with_proxy()"""
        pass
```

### Proxy Endpoints

**For local agents:**
```python
# Poll for messages
GET {proxy_url}/poll_messages
Returns: {"messages": [...]}

# Submit response
POST {proxy_url}/submit_response
Body: {"response": "your text"}
```

**For A2A agents:**
```python
# Get agent card
GET {proxy_url}/.well-known/agent.json

# Send message
POST {proxy_url}/tasks
Body: {"task_id": "...", "message": {...}}
Returns: Streaming NDJSON response
```

## Known Issues & TODOs

### High Priority

- [ ] **Green agent `/tasks` endpoint** - Currently returns 404
  - AgentBeats agents use different routing than standard A2A
  - Need to integrate with AgentBeats backend or update trigger script

- [ ] **Error handling** - No retry logic or timeout handling
  - Add exponential backoff for polling
  - Handle proxy crashes gracefully

- [ ] **WebSocket support** - Currently uses polling (1 second interval)
  - Replace HTTP polling with WebSocket for real-time communication
  - More efficient for high-frequency messages

### Medium Priority

- [ ] **Authentication** - No security currently
  - Add OAuth/JWT for A2A messages
  - Secure local agent ↔ proxy communication

- [ ] **Battle orchestration** - Green agent needs backend
  - Set up AgentBeats backend server
  - Register agents properly
  - Implement full battle flow

- [ ] **Multiple agent support** - Only one local agent at a time
  - Support multiple local agents with different ports
  - Dynamic port allocation

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
