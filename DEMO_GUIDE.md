# Quick Demo Guide

## Complete End-to-End Test

### 1. Setup
```bash
# Set your OpenAI API key
export OPENAI_API_KEY='your-key-here'
```

### 2. Start Everything
```bash
./start_demo.sh
```

**What happens:**
- ✅ Green agent starts on port 9031
- ✅ Local red agent starts with auto-proxy on port 9021
- ✅ Logs are written to `logs/` directory

### 3. Trigger Battle
```bash
./trigger_battle.py
```

**What happens:**
1. Script checks both agents are ready
2. Sends battle message to green agent
3. Green agent receives message and calls red agent via A2A
4. Red agent proxy forwards to local red agent
5. Local red agent processes and responds
6. Response flows back through proxy to green agent
7. Green agent completes and logs results

### 4. Watch the Magic
```bash
# In one terminal
tail -f logs/green_agent.log

# In another terminal
tail -f logs/red_agent.log
```

You'll see:
- Green agent receiving battle instructions
- Green agent making A2A call to red agent
- Red agent proxy receiving and forwarding message
- Local red agent processing message
- Response flowing back

### 5. Stop Everything
```bash
./stop_demo.sh
```

## Architecture Flow

```
[trigger_battle.py]
      │
      │ HTTP POST /tasks
      ▼
[Green Agent :9031]
      │
      │ A2A Protocol
      │ POST /tasks with battle message
      ▼
[Red Agent Proxy :9021]
      │
      │ Internal message queue
      ▼
[Local Red Agent]
  - Polls /poll_messages
  - Processes message
  - Submits via /submit_response
      │
      │ Response flows back up
      ▼
[Green Agent receives response]
```

## Troubleshooting

### Green agent won't start
- Check `OPENAI_API_KEY` is set
- Check port 9031 is available: `lsof -i :9031`
- View logs: `cat logs/green_agent.log`

### Red agent won't start
- Check port 9021 is available: `lsof -i :9021`
- View logs: `cat logs/red_agent.log`
- Check `red_agent_card.toml` exists

### Battle trigger fails
- Ensure both agents are running
- Check agents respond:
  ```bash
  curl http://localhost:9031/.well-known/agent.json
  curl http://localhost:9021/.well-known/agent.json
  ```

### No communication happening
- Check green agent logs for A2A calls
- Check red agent logs for received messages
- Verify URLs match in green agent's message to red agent

## Next: Create Your Own Agent

1. Copy `example_custom_agent.py`
2. Modify `process_message()` with your logic
3. Create your own agent card TOML
4. Run with `run_with_proxy()`

See `README.md` for full details!
