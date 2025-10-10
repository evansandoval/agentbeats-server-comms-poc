# Quick Start: Single-Command Agent Deployment

This guide shows the **improved user experience** where you run a single command to start your local agent with automatic proxy handling.

## For Users: Running a Local Agent

### Step 1: Create Your Agent Card

Create a TOML file describing your agent (e.g., `my_agent_card.toml`):

```toml
name = "My Awesome Agent"
description = "Does cool stuff"
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
description = "What my agent does"
tags = ["custom"]
examples = ["Example usage"]
```

### Step 2: Create Your Agent Code

```python
# my_agent.py
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
        """Your agent logic here"""
        while True:
            messages = self.poll_messages()
            for msg in messages:
                # Process message
                response = f"Processed: {msg}"
                self.submit_response(response)
            time.sleep(1)

# Single command to run everything!
if __name__ == "__main__":
    agent = MyAgent()
    run_with_proxy(
        agent,
        agent_card_path="my_agent_card.toml",
        proxy_port=9025
    )
```

### Step 3: Run Your Agent

```bash
python my_agent.py
```

**That's it!** The proxy starts automatically in the background.

## What Happens Behind the Scenes

When you call `run_with_proxy()`:

1. ✅ Proxy server starts automatically on specified port
2. ✅ Agent card is loaded and served at `/.well-known/agent.json`
3. ✅ A2A endpoints (`/tasks`, `/reset`) are ready
4. ✅ Your agent's `run()` method is called
5. ✅ Green agent can now communicate via A2A protocol
6. ✅ Your agent polls `/poll_messages` and submits via `/submit_response`

## Examples

### Example 1: Using the Pre-built Red Agent

```bash
python simple_local_agent.py
```

This runs the example red agent with auto-proxy.

### Example 2: Custom Agent

```bash
python example_custom_agent.py
```

Shows how to create a custom agent from scratch.

### Example 3: Your Own Agent

See `example_custom_agent.py` for a full template you can copy and modify.

## User Requirements

Minimal! Users only need to:

1. ✅ Implement a class with `__init__(proxy_url)` and `run()` methods
2. ✅ Create an agent card TOML file
3. ✅ Call `run_with_proxy(agent, agent_card_path="...", proxy_port=...)`

**No manual proxy management needed!**

## API Reference

### `run_with_proxy(agent, agent_card_path, proxy_host, proxy_port)`

Runs a local agent with automatic proxy startup.

**Parameters:**
- `agent`: Your agent instance (must have a `run()` method)
- `agent_card_path`: Path to your agent card TOML file
- `proxy_host`: Host for proxy server (default: `"0.0.0.0"`)
- `proxy_port`: Port for proxy server (default: `9021`)

**Example:**
```python
agent = MyAgent()
run_with_proxy(agent, agent_card_path="my_card.toml", proxy_port=9025)
```

### Agent Class Requirements

Your agent class must implement:

```python
class MyAgent:
    def __init__(self, proxy_url: str = "http://localhost:PORT"):
        """Initialize with proxy URL"""
        self.proxy_url = proxy_url

    def run(self):
        """Main agent loop - called by run_with_proxy()"""
        # Your logic here
        pass
```

### Proxy Communication Endpoints

Your agent communicates with the proxy via:

**Poll for messages:**
```python
GET {proxy_url}/poll_messages
Returns: {"messages": [...]}
```

**Submit response:**
```python
POST {proxy_url}/submit_response
Body: {"response": "your response text"}
```

## Testing Your Setup

1. **Start your local agent:**
   ```bash
   python my_agent.py
   ```

2. **Verify proxy is running:**
   ```bash
   curl http://localhost:9025/.well-known/agent.json
   ```

3. **Send a test message:**
   ```bash
   curl -X POST http://localhost:9025/tasks \
     -H "Content-Type: application/json" \
     -d '{"task_id": "test", "message": {"parts": [{"type": "text", "text": "Hello!"}]}}'
   ```

4. **Check your agent logs** - you should see the message being processed!

## Running the Full Demo

To test the complete green agent ↔ red agent communication:

### Step 1: Set your OpenAI API key

```bash
export OPENAI_API_KEY='your-key-here'
```

### Step 2: Start all components

```bash
./start_demo.sh
```

This starts:
- Green agent on port 9031 (orchestrator)
- Red agent proxy on port 9021 (auto-started with local agent)

### Step 3: Trigger a battle

```bash
./trigger_battle.py
```

This sends a message to the green agent, which will:
1. Log the battle start
2. Send a message to the red agent
3. Receive and log the red agent's response
4. Report the battle end

### Step 4: Stop all components

```bash
./stop_demo.sh
```

Or use Ctrl+C and the PIDs shown in the output.

### View Logs

```bash
tail -f logs/green_agent.log   # Green agent activity
tail -f logs/red_agent.log      # Red agent activity
```

## Next Steps

- Modify `process_message()` in your agent to add custom logic
- Add error handling and retry logic
- Deploy to production by changing URLs/ports
- Create multiple local agents with different ports
