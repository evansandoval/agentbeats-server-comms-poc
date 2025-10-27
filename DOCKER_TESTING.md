# Docker Testing Guide

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

If ports 8000, 9001, 9002, 9101, or 9102 are already in use:

```bash
# Check what's using the ports
lsof -i :8000
lsof -i :9001

# Option 1: Stop conflicting services
# Option 2: Modify docker-compose.yml to use different host ports
# Example: "8001:8000" maps host port 8001 to container port 8000
```

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
