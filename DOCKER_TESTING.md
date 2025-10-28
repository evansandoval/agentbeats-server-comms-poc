# Docker Testing Guide

## Architecture Overview

The Docker deployment creates three isolated containers:
- **a2a-server**: Central WebSocket router (port 8000 exposed to host)
- **a2a-green-agent**: Green agent + proxy (ports 9000/9001 internal only)
- **a2a-white-agent**: White agent + proxy (ports 9000/9001 internal only)

**Key Design**: All agents use standardized ports (agent: 9000, proxy: 9001) because each container has its own isolated `localhost`. Agent ports are NOT exposed to the host, ensuring all communication flows through the server's WebSocket connections.

## How Evaluation Works

The system is **reactive**, not proactive:

1. **Startup**: All containers start and agents register with the server, but no evaluation runs
2. **Task Trigger**: You send a POST request to `http://localhost:8000/tasks/send` with task configuration
3. **Server Routes**: Server sends `start_task` message to green agent's proxy via WebSocket
4. **Proxy Converts**: Green proxy uses A2A client to POST the task to green agent's HTTP endpoint
5. **Evaluation Begins**: Green agent's `TauGreenAgentExecutor.execute()` method runs
6. **Inter-Agent Communication**: Green agent sends messages to white agent via proxy URLs, all routed through server

## Prerequisites

1. Docker installed and running
2. Docker Compose installed (or Docker Desktop which includes it)
3. `.env` file with `OPENAI_API_KEY=your_key_here`

## Testing Steps

### 1. Validate Configuration

```bash
# Check docker-compose.yml syntax
docker-compose config

# Verify .env file exists
cat .env
```

### 2. Build Images

```bash
# Build all images (this may take 5-10 minutes first time)
docker-compose build

# Verify images were created
docker images | grep a2a
```

Expected output should show 2 images:
- One for the server
- One for the agents (shared by green and white)

### 3. Start Services

```bash
# Start all services in foreground (see logs in terminal)
docker-compose up

# OR start in background
docker-compose up -d

# If background, view logs
docker-compose logs -f
```

### 4. Verify Services are Running

```bash
# Check container status
docker-compose ps

# Should show 3 containers: server, green-agent, white-agent
# All should be "Up" or "healthy"
```

### 5. Test Server Health

```bash
# Check server health endpoint
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "active_agents": ["green", "white-1"],
#   "pending_requests": 0
# }
```

### 6. Test Agent Registration

Check logs to verify both agents registered:

```bash
docker-compose logs server | grep "registered"

# Should see:
# ✓ Agent 'green' registered. Active agents: ['green']
# ✓ Agent 'white-1' registered. Active agents: ['green', 'white-1']
```

### 7. Send Test Task

```bash
curl -X POST http://localhost:8000/tasks/send \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "green",
    "task_body": {
      "task": "Your task is to instantiate tau-bench to test the following agent.",
      "agents": {
        "white-1": {
          "agent_id": "white-1",
          "description": "Target agent to test"
        }
      },
      "env_config": {
        "env": "retail",
        "user_strategy": "llm",
        "user_model": "openai/gpt-4o",
        "user_provider": "openai",
        "task_split": "test",
        "task_ids": [1]
      }
    }
  }'

# Expected response:
# {"status":"sent","request_id":"<some-uuid>"}
```

### 8. Monitor Task Execution

Watch logs for message flow:

```bash
# Green agent logs
docker-compose logs -f green-agent

# White agent logs
docker-compose logs -f white-agent

# Server routing logs
docker-compose logs -f server
```

Look for:
- 🟢 Green agent receiving task
- 📤 Green proxy sending request to white
- 🔄 Server routing messages
- 📥 White proxy receiving request
- ⚪ White agent processing
- Response flowing back

### 9. Cleanup

```bash
# Stop all services
docker-compose down

# Remove images (optional)
docker-compose down --rmi all

# Remove volumes (optional)
docker-compose down -v
```

## Troubleshooting

### Issue: Containers not starting

```bash
# Check detailed logs
docker-compose logs

# Check specific container
docker logs a2a-green-agent
docker logs a2a-white-agent
docker logs a2a-proxy-server
```

### Issue: Agents not registering with server

```bash
# Verify network connectivity
docker-compose exec green-agent ping -c 2 server

# Check server is listening
docker-compose exec server netstat -tlnp | grep 8000
```

### Issue: "OPENAI_API_KEY not set" errors

```bash
# Verify .env file exists and has the key
cat .env

# Verify environment variable in container
docker-compose exec green-agent env | grep OPENAI
```

### Issue: Port conflicts

If port 8000 is already in use on the host:

```bash
# Check what's using port 8000
lsof -i :8000

# Option 1: Stop conflicting services
# Option 2: Modify docker-compose.yml to use different host port
# Example: Change "8000:8000" to "8001:8000" in server's ports section
# This maps host port 8001 to container port 8000
```

**Note**: Agent and proxy ports (9000, 9001) are NOT exposed to the host in the Docker deployment, so there's no risk of port conflicts for them. All agents use the same internal ports since each container has isolated localhost.

### Issue: Build failures

```bash
# Clean rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up
```

## Testing Checklist

- [ ] `docker-compose config` validates without errors
- [ ] `docker-compose build` completes successfully
- [ ] All 3 containers start: server, green-agent, white-agent
- [ ] Health check passes: `curl http://localhost:8000/health`
- [ ] Both agents appear in active_agents list
- [ ] Task send via `/tasks/send` returns success
- [ ] Logs show complete message flow (green → server → white → server → green)
- [ ] No error messages in any container logs
- [ ] `docker-compose down` cleanly stops all services

## Performance Notes

- First build: 5-10 minutes (downloading base images, installing dependencies)
- Subsequent builds: 1-2 minutes (using cache)
- Startup time: ~10-15 seconds for all services to be healthy
- Agent registration: ~2-3 seconds after startup

## Known Issues

### LLM Output Format Errors

**Symptom**: Evaluation crashes mid-run with `KeyError: 'json'`

**Cause**: White agent (powered by LLM) sometimes returns responses without proper `<json>...</json>` tags due to nondeterministic LLM output formatting.

**Workaround**: Restart the evaluation. The LLM usually formats correctly on subsequent attempts.

**Status**: Fix planned - will add error handling, fallback JSON extraction, and retry logic. See README.md "Known Issues and TODOs" section for details.

### Docker Build Cache

**Symptom**: Code changes don't appear in running containers

**Cause**: Docker caches layers, including the Python code copy step

**Solution**: Use `docker-compose build --no-cache` to force a clean rebuild

**Tip**: If you're only changing Python code, the cached build is usually fine since the code is installed with `pip install -e .` (editable mode). Only use `--no-cache` if you're certain the cache is stale.

## Next Steps

Once basic testing passes:

1. **Scale testing**: Run multiple white agents
   ```bash
   docker-compose up --scale white-agent=3
   ```

2. **Production deployment**: Use separate docker-compose files for dev/prod

3. **Monitoring**: Add logging/metrics services (Prometheus, Grafana)

4. **CI/CD**: Integrate into GitHub Actions or similar

5. **Cloud deployment**: Deploy to AWS ECS, GCP Cloud Run, or Kubernetes
