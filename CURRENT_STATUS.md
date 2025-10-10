# Current System Status

**Last Updated:** 2025-10-10

## Running Processes

```
PID     COMMAND
112077  Green Agent (launcher)
112093  Green Agent (agent server)
112151  Red Agent (with auto-proxy)
```

## Port Allocation

| Port | Service | Status |
|------|---------|--------|
| 9021 | Red Agent Proxy | ✅ Running (PID 112151) |
| 9031 | Green Agent | ✅ Running (PID 112093) |
| 9030 | Green Agent Launcher | ✅ Running (PID 112077) |

## Quick Health Check

```bash
# Check processes
ps aux | grep -E "(agentbeats|simple_local_agent)" | grep -v grep

# Check ports
lsof -i :9021 -i :9031 -i :9030

# Test red agent
curl http://localhost:9021/.well-known/agent.json

# Test green agent
curl http://localhost:9031/.well-known/agent.json
```

## What's Working ✅

1. **Red Agent + Proxy**
   - Auto-starting proxy on port 9021
   - Local agent polling for messages
   - A2A protocol compliance
   - Test script works: `python test_red_agent_only.py`

2. **Green Agent**
   - Running on port 9031
   - Agent card accessible
   - Using gpt-4o-mini model

## What's Not Working ❌

1. **Green → Red Communication**
   - Green agent doesn't expose standard `/tasks` endpoint
   - Need AgentBeats backend for proper orchestration
   - `trigger_battle.py` returns 404

## How to Stop Everything

```bash
# Option 1: Kill by PID
kill -9 112077 112093 112151

# Option 2: Kill by name
pkill -9 -f "agentbeats"
pkill -9 -f "simple_local_agent"

# Option 3: Use script
./stop_demo.sh
```

## How to Restart

### Terminal-Based (Recommended)

**Terminal 1 - Red Agent:**
```bash
python simple_local_agent.py
```

**Terminal 2 - Green Agent (optional):**
```bash
source .env
python -m agentbeats run green_agent_card.toml \
  --launcher_host 0.0.0.0 --launcher_port 9030 \
  --agent_host 0.0.0.0 --agent_port 9031 \
  --model_type openai --model_name gpt-4o-mini \
  --tool green_tools.py
```

**Terminal 3 - Test:**
```bash
python test_red_agent_only.py
```

### Script-Based

```bash
./start_demo.sh
```

## Testing Commands

```bash
# Test red agent only (WORKS)
python test_red_agent_only.py

# Try green → red battle (DOESN'T WORK YET)
python trigger_battle.py

# Direct A2A test
curl -X POST http://localhost:9021/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_id":"test","message":{"parts":[{"type":"text","text":"test. battle_id: 123"}]}}'
```

## Logs

```bash
# Watch red agent logs
tail -f logs/red_agent.log

# Watch green agent logs
tail -f logs/green_agent.log
```

## Next Steps

See `TODO.md` for full task list. High priority items:

1. ✅ **Terminal-based testing guide** - DONE (see TERMINAL_TESTING.md)
2. ❌ **Green agent integration** - Needs AgentBeats backend
3. ❌ **WebSocket support** - Replace polling
4. ❌ **Authentication** - Add security
5. ❌ **Error handling** - Add retries

## Documentation

- **README.md** - Main documentation
- **TERMINAL_TESTING.md** - Terminal-based testing (recommended!)
- **DEMO_GUIDE.md** - 5-minute quick start
- **TODO.md** - Complete task tracking
- **CURRENT_STATUS.md** - This file (system status)
