# Terminal-Based Testing Guide

This guide shows how to test the AgentBeats PoC using multiple terminals for easier process control.

## Why Terminal-Based Testing?

✅ **Easier to stop** - Just press `Ctrl+C` in each terminal
✅ **Better visibility** - See logs in real-time
✅ **No zombies** - Processes die when you close the terminal
✅ **Simpler debugging** - Each component isolated

## Step-by-Step Testing

### Step 1: Clean Up First

Before starting, check for orphaned processes from previous runs:

```bash
# Check what's running
ps aux | grep -E "(agentbeats|simple_local_agent|red_agent_proxy)" | grep -v grep

# Check ports
lsof -i :9021 -i :9031

# Kill any zombies
pkill -9 -f "agentbeats run"
pkill -9 -f "simple_local_agent"
```

### Step 2: Open Your Terminals

Open 3 terminal windows/tabs. Arrange them so you can see all at once.

```
┌──────────────────┬──────────────────┐
│   Terminal 1     │   Terminal 2     │
│   Local Agent    │   Test Script    │
│                  │                  │
├──────────────────┴──────────────────┤
│          Terminal 3 (Optional)      │
│          Logs                       │
└─────────────────────────────────────┘
```

### Step 3: Start Local Agent (Terminal 1)

```bash
cd /home/esand/agentbeat-server-comms
python simple_local_agent.py
```

**Expected output:**
```
INFO: Starting proxy server on 0.0.0.0:9021
INFO: Loaded agent card: POC Red Agent (via Proxy)
INFO: Proxy server started successfully
INFO: Red agent started!
INFO: Polling for messages every 1.0 seconds...
DEBUG: GET /poll_messages HTTP/1.1" 200
DEBUG: GET /poll_messages HTTP/1.1" 200
...
```

✅ **Success indicators:**
- "Proxy server started successfully"
- "Red agent started!"
- Continuous polling (GET /poll_messages every second)

❌ **If it fails:**
```bash
# Port in use error
Error: [Errno 98] Address already in use

# Solution: Kill process using port 9021
lsof -i :9021
kill -9 <PID>
```

### Step 4: Run Test (Terminal 2)

Wait until you see "Polling for messages" in Terminal 1, then:

```bash
cd /home/esand/agentbeat-server-comms
python test_red_agent_only.py
```

**Expected output:**
```
✓ Red agent proxy is ready
✓ Sending test message...
[STATUS] Task state: running
[MESSAGE] Red agent completed task for battle test_battle_1728576543...
[STATUS] Task state: completed
✓ Test completed successfully!
```

✅ **Success indicators:**
- All ✓ checkmarks
- "Task state: running" → "Task state: completed"
- Message contains "Red agent completed task for battle..."

**In Terminal 1, you should see:**
```
INFO: Received message from proxy
DEBUG: Extracted battle_id: test_battle_1728576543
INFO: Submitting response for battle_id test_battle_1728576543
DEBUG: POST /submit_response HTTP/1.1" 200
```

### Step 5: Watch Logs (Terminal 3 - Optional)

For more detailed debugging:

```bash
cd /home/esand/agentbeat-server-comms
tail -f logs/red_agent.log
```

You'll see:
- Proxy startup messages
- Agent initialization
- Each polling request
- Message reception and processing
- Response submission

### Step 6: Stop Everything

**Easy cleanup:**
1. Press `Ctrl+C` in Terminal 1 (Local Agent)
2. Press `Ctrl+C` in Terminal 3 (Logs, if running)
3. Terminal 2 (Test Script) already finished

**Verify cleanup:**
```bash
ps aux | grep -E "(simple_local_agent)" | grep -v grep
# Should show nothing

lsof -i :9021
# Should show nothing
```

## Testing Green Agent (Partial - Needs Backend)

If you want to test the green agent:

### Terminal 1 - Green Agent

```bash
cd /home/esand/agentbeat-server-comms
source .env  # Load OPENAI_API_KEY
python -m agentbeats run green_agent_card.toml \
  --launcher_host 0.0.0.0 --launcher_port 9030 \
  --agent_host 0.0.0.0 --agent_port 9031 \
  --model_type openai --model_name gpt-4o-mini \
  --tool green_tools.py
```

**Expected:**
```
INFO: Starting agent on http://0.0.0.0:9031
INFO: Starting launcher on http://0.0.0.0:9030
```

### Terminal 2 - Red Agent

```bash
cd /home/esand/agentbeat-server-comms
python simple_local_agent.py
```

### Terminal 3 - Trigger (Currently Broken)

```bash
cd /home/esand/agentbeat-server-comms
python trigger_battle.py
```

**Current status:** ❌ Returns 404
**Why:** Green agent doesn't expose standard A2A `/tasks` endpoint
**TODO:** Needs AgentBeats backend integration

## Common Issues & Solutions

### Issue 1: Port Already in Use

```
Error: [Errno 98] Address already in use
```

**Solution:**
```bash
# Find the process
lsof -i :9021

# Kill it
kill -9 <PID>

# Or use pkill
pkill -9 -f "simple_local_agent"
```

### Issue 2: Agent Not Receiving Messages

**Check proxy is running:**
```bash
curl http://localhost:9021/.well-known/agent.json
```

Should return agent card JSON.

**Check agent is polling:**
```bash
tail logs/red_agent.log | grep "poll_messages"
```

Should show continuous GET requests.

### Issue 3: Test Script Hangs

If `test_red_agent_only.py` hangs:

1. Check proxy is ready (see Issue 2)
2. Look for errors in Terminal 1
3. Check logs: `tail logs/red_agent.log`
4. Try manual curl:
   ```bash
   curl -X POST http://localhost:9021/tasks \
     -H "Content-Type: application/json" \
     -d '{"task_id":"manual","message":{"parts":[{"type":"text","text":"test. battle_id: 123"}]}}'
   ```

### Issue 4: Zombie Processes

After stopping, processes still running:

```bash
# Nuclear option - kill everything
pkill -9 -f "agentbeats"
pkill -9 -f "simple_local_agent"
pkill -9 -f "red_agent_proxy"

# Verify
ps aux | grep -E "(agentbeats|agent)" | grep -v grep
```

## Advanced Testing Scenarios

### Multiple Messages

Send several messages rapidly:

```bash
# Terminal 2
for i in {1..5}; do
  python test_red_agent_only.py &
done
wait
```

Watch Terminal 1 to see queue handling.

### Direct A2A Call

Skip the test script, use curl:

```bash
curl -X POST http://localhost:9021/tasks \
  -H "Content-Type: application/json" \
  -H "Accept: application/x-ndjson" \
  -d '{
    "task_id": "manual_test_1",
    "message": {
      "parts": [
        {"type": "text", "text": "Manual test. battle_id: manual_123"}
      ]
    }
  }'
```

Should return streaming NDJSON:
```json
{"type":"task_update","state":"running"}
{"type":"message","parts":[{"type":"text","text":"Red agent completed task for battle manual_123..."}]}
{"type":"task_update","state":"completed"}
```

### Custom Response Logic

Edit `simple_local_agent.py`:

```python
def process_message(self, message):
    text = extract_text(message)
    battle_id = self.extract_battle_id(text)

    # Add custom logic
    if "urgent" in text.lower():
        return f"🚨 URGENT: Completed battle {battle_id} immediately!"
    else:
        return f"Red agent completed task for battle {battle_id} (standard priority)"
```

Restart Terminal 1, test again.

## Summary: Full Workflow

```bash
# Terminal prep
cd /home/esand/agentbeat-server-comms

# Clean up
pkill -9 -f "agentbeats"
pkill -9 -f "simple_local_agent"

# Terminal 1: Start agent
python simple_local_agent.py

# Terminal 2: Wait for "Polling", then test
python test_red_agent_only.py

# Terminal 3 (optional): Watch logs
tail -f logs/red_agent.log

# Stop: Ctrl+C in each terminal
```

## Next Steps

- [ ] Replace polling with WebSocket (real-time)
- [ ] Add authentication (JWT/OAuth)
- [ ] Implement green agent integration via backend
- [ ] Add error handling and retries
- [ ] Deploy with Docker

See `TODO.md` for complete task list.
