# Demo Guide - AgentBeats Local Agent PoC

## What Works ✅

This PoC demonstrates a **local agent** communicating via the A2A protocol through an auto-starting proxy.

### Working Flow:

```
[Test Script] → [Proxy :9021] → [Local Agent] → Response flows back
```

## Quick Demo (5 minutes)

### 1. Start the Local Agent

```bash
python simple_local_agent.py
```

You'll see:
```
INFO: Starting proxy server on 0.0.0.0:9021
INFO: Loaded agent card: POC Red Agent (via Proxy)
INFO: Proxy server started successfully
INFO: Red agent started!
```

### 2. Test Communication

In another terminal:

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

### 3. Watch the Logs

```bash
tail -f logs/red_agent.log
```

You'll see:
1. Agent polling every second
2. Message received from proxy
3. Battle ID extracted
4. Response generated and submitted

### 4. Stop Everything

```bash
./stop_demo.sh
```

Or press `Ctrl+C` in the terminal running the agent.

## What This Demonstrates

✅ **A2A Protocol** - Full streaming message/response format
✅ **Auto-Proxy** - Single command starts everything
✅ **Message Polling** - Local agent polls /poll_messages
✅ **Battle ID Extraction** - Regex parsing from message text
✅ **Response Streaming** - NDJSON format back to caller

## What Doesn't Work Yet 🚧

❌ **Green Agent Integration** - Can't trigger via green agent
  - Issue: Green agent doesn't expose `/tasks` endpoint
  - Workaround: Use `test_red_agent_only.py` to test directly
  - TODO: Integrate with AgentBeats backend

❌ **Full Battle Flow** - No orchestration yet
  - TODO: Set up AgentBeats backend
  - TODO: Register agents with backend
  - TODO: Trigger battles through backend API

❌ **WebSocket** - Uses polling (1 sec interval)
  - TODO: Replace with WebSocket for real-time

## Architecture Details

### Proxy Server Components

**1. A2A Interface** (for other agents to call us)
```python
POST /tasks → Receives A2A messages
GET /.well-known/agent.json → Agent card
```

**2. Local Interface** (for our local agent)
```python
GET /poll_messages → Agent polls for work
POST /submit_response → Agent submits results
```

**3. Launcher Interface** (for AgentBeats backend)
```python
POST /reset → Receives battle context
Notifies backend when ready
```

### Message Flow

```
1. External agent sends: POST /tasks
   {
     "task_id": "battle_123",
     "message": {
       "parts": [{"type": "text", "text": "Do task. battle_id: 123"}]
     }
   }

2. Proxy queues message internally

3. Local agent polls: GET /poll_messages
   Returns: {"messages": [{...}]}

4. Local agent processes:
   - Extracts: battle_id = "123"
   - Generates: "Red agent completed task for battle 123..."

5. Local agent submits: POST /submit_response
   {"response": "Red agent completed..."}

6. Proxy streams back to caller:
   {"type": "task_update", "state": "running"}
   {"type": "message", "parts": [{"type": "text", "text": "..."}]}
   {"type": "task_update", "state": "completed"}
```

## Testing Scenarios

### Scenario 1: Basic Message Flow

```bash
# Terminal 1
python simple_local_agent.py

# Terminal 2
python test_red_agent_only.py
```

Verifies: Proxy → Local Agent → Response

### Scenario 2: Direct A2A Call

```bash
# With agent running, send manual A2A message:
curl -X POST http://localhost:9021/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "test_1",
    "message": {
      "parts": [
        {"type": "text", "text": "Test task. battle_id: manual_123"}
      ]
    }
  }'
```

Verifies: Raw A2A protocol compatibility

### Scenario 3: Multiple Messages

```bash
# Send multiple messages rapidly
for i in {1..5}; do
  python test_red_agent_only.py &
done
wait
```

Verifies: Queue handling, concurrency

## Customization Examples

### Example 1: Change Response Logic

Edit `simple_local_agent.py`:

```python
def process_message(self, message):
    # Your custom logic here!
    text = extract_text(message)

    if "urgent" in text.lower():
        return "URGENT: Task completed immediately!"
    else:
        return f"Standard processing: {text}"
```

### Example 2: Different Port

```python
# Change all references from 9021 to 9025
agent = SimpleRedAgent(proxy_url="http://localhost:9025")
run_with_proxy(agent, "my_card.toml", proxy_port=9025)
```

### Example 3: Add Logging

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(message)s',
    filename='my_agent.log'
)
```

## Common Issues

### Issue: Port already in use

```bash
Error: [Errno 98] Address already in use
```

**Solution:**
```bash
lsof -i :9021
kill -9 <PID>
# Or choose different port
```

### Issue: Agent not receiving messages

**Check 1:** Proxy running?
```bash
curl http://localhost:9021/.well-known/agent.json
```

**Check 2:** Agent polling?
```bash
tail -f logs/red_agent.log | grep "poll_messages"
```

**Check 3:** Send test message
```bash
python test_red_agent_only.py
```

### Issue: Green agent 404

```bash
POST /tasks HTTP/1.1" 404 Not Found
```

**Why:** AgentBeats agents use different routing
**Workaround:** Use `test_red_agent_only.py` instead
**TODO:** Fix `trigger_battle.py` to use correct endpoint

## Next Steps

### To Make Production-Ready

1. **Add WebSocket** - Replace polling
2. **Add Auth** - JWT/OAuth for security
3. **Add Retries** - Exponential backoff
4. **Add Monitoring** - Metrics, health checks
5. **Deploy** - Docker, cloud hosting

### To Complete Green Agent Integration

1. **Start AgentBeats backend**:
   ```bash
   python -m agentbeats run_backend
   ```

2. **Register agents**:
   ```bash
   # TODO: Use backend API to register both agents
   ```

3. **Create battle**:
   ```bash
   # TODO: Use backend API to trigger battle
   ```

## Useful Commands

```bash
# Start agent
python simple_local_agent.py

# Test communication
python test_red_agent_only.py

# View logs
tail -f logs/red_agent.log

# Check proxy
curl http://localhost:9021/.well-known/agent.json

# Stop everything
./stop_demo.sh

# Check what's using ports
lsof -i :9021 -i :9031
```

## Files to Modify

**To create your own agent:**
- Copy `simple_local_agent.py` → `my_agent.py`
- Copy `red_agent_card.toml` → `my_agent_card.toml`
- Edit `process_message()` method
- Update port numbers

**Don't modify:**
- `proxy_wrapper.py` (core infrastructure)
- `red_agent_proxy.py` (core infrastructure)

## Success Criteria

You know it's working when:
1. ✅ `python simple_local_agent.py` starts without errors
2. ✅ You see "Proxy server started successfully"
3. ✅ You see "Red agent started!"
4. ✅ Logs show polling: `GET /poll_messages HTTP/1.1" 200`
5. ✅ Test script returns message: "Red agent completed task..."

## Resources

- **AgentBeats Docs**: https://github.com/agentbeats/agentbeats
- **A2A Protocol**: https://a2a-protocol.org/
- **This PoC**: `README.md` for full details
