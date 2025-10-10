# TODO List - AgentBeats Local Agent PoC

## Critical Issues 🔴

### 1. Green Agent Integration
**Status:** ❌ Broken
**Issue:** Green agent returns 404 on `/tasks` endpoint
**Why:** AgentBeats agents don't expose standard A2A `/tasks` - they require backend coordination

**Options to fix:**
- [ ] **Option A:** Start AgentBeats backend and use proper orchestration
  ```bash
  python -m agentbeats run_backend --port 8080
  # Then register agents and create battles via backend API
  ```

- [ ] **Option B:** Update green agent to expose `/tasks` directly
  - Requires modifying AgentBeats or wrapping green agent in custom server

- [ ] **Option C:** Use different orchestration method
  - Direct agent-to-agent calls without backend
  - May lose battle tracking features

**Files affected:**
- `trigger_battle.py` - Currently expects `/tasks` endpoint
- `start_demo.sh` - Green agent startup works but can't receive triggers
- `green_agent_card.toml` - May need routing configuration

**Priority:** HIGH - Blocks full demo

---

### 2. WebSocket Support
**Status:** ⚠️ Works but inefficient
**Issue:** Local agent polls every 1 second - wastes resources

**Why polling sucks:**
- CPU usage even when idle
- 1-second latency minimum
- Unnecessary network traffic

**Migration plan:**
- [ ] Add WebSocket endpoint to proxy: `ws://localhost:9021/ws`
- [ ] Update `simple_local_agent.py` to use WebSocket client
- [ ] Keep HTTP polling as fallback for compatibility
- [ ] Add connection retry logic

**Files to modify:**
- `red_agent_proxy.py` - Add WebSocket endpoint
- `simple_local_agent.py` - Replace `poll_messages()` with WebSocket
- `proxy_wrapper.py` - May need threading updates

**Priority:** MEDIUM - Current polling works but not scalable

---

## High Priority Features 🟡

### 3. Error Handling & Retries
**Status:** ❌ Missing
**Issue:** No handling for network failures, timeouts, or crashes

**Needed:**
- [ ] Exponential backoff for polling failures
- [ ] Retry logic for A2A message sending
- [ ] Graceful degradation when proxy dies
- [ ] Circuit breaker pattern for repeated failures
- [ ] Dead letter queue for undeliverable messages

**Example implementation:**
```python
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(5))
def poll_messages(self):
    # Polling logic with auto-retry
    pass
```

**Priority:** HIGH - Production requirement

---

### 4. Authentication & Security
**Status:** ❌ None
**Issue:** Anyone can send messages to proxy or local agent

**Threats:**
- Unauthorized agents sending malicious messages
- Man-in-the-middle attacks
- Message tampering

**Solutions:**
- [ ] Add JWT authentication for A2A messages
- [ ] HTTPS/TLS for all communication
- [ ] API key for local agent ↔ proxy
- [ ] Message signing/verification
- [ ] Rate limiting

**Files to modify:**
- `red_agent_proxy.py` - Add auth middleware
- `simple_local_agent.py` - Include auth tokens
- New file: `auth.py` - Auth utilities

**Priority:** HIGH - Security critical

---

### 5. Battle State Management
**Status:** ⚠️ Partial
**Issue:** No persistent state, battles lost on restart

**Needed:**
- [ ] Database for battle state (SQLite/PostgreSQL)
- [ ] Persist message queue across restarts
- [ ] Battle history and results
- [ ] Agent performance metrics

**Schema:**
```sql
CREATE TABLE battles (
    id TEXT PRIMARY KEY,
    status TEXT,
    created_at TIMESTAMP,
    completed_at TIMESTAMP,
    result JSON
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    battle_id TEXT,
    sender TEXT,
    content JSON,
    timestamp TIMESTAMP
);
```

**Priority:** MEDIUM - Needed for production

---

## Medium Priority Improvements 🟢

### 6. Multiple Local Agents
**Status:** ⚠️ One at a time
**Issue:** Can only run one local agent per proxy

**Features needed:**
- [ ] Dynamic port allocation
- [ ] Agent registry
- [ ] Load balancing across agents
- [ ] Agent discovery

**Architecture:**
```
[Proxy Manager :9000]
    ├─ [Proxy :9021] → [Local Agent 1]
    ├─ [Proxy :9022] → [Local Agent 2]
    └─ [Proxy :9023] → [Local Agent 3]
```

**Priority:** MEDIUM - Nice to have

---

### 7. Monitoring & Observability
**Status:** ❌ None
**Issue:** No visibility into system health

**Metrics needed:**
- Message latency (end-to-end)
- Proxy throughput (messages/sec)
- Agent response time
- Error rates
- Queue depth

**Tools:**
- [ ] Prometheus metrics endpoint
- [ ] Grafana dashboards
- [ ] Structured logging (JSON)
- [ ] Distributed tracing (OpenTelemetry)

**Example:**
```python
from prometheus_client import Counter, Histogram

messages_received = Counter('messages_received_total', 'Messages received')
response_time = Histogram('response_time_seconds', 'Response time')
```

**Priority:** MEDIUM - Operations requirement

---

### 8. Configuration Management
**Status:** ⚠️ Hardcoded
**Issue:** Ports, URLs hardcoded in multiple files

**Better approach:**
```yaml
# config.yaml
proxy:
  host: 0.0.0.0
  port: 9021

agent:
  poll_interval: 1.0
  timeout: 30

logging:
  level: INFO
  file: logs/agent.log
```

**Files to modify:**
- All Python files to load from config
- Add `config.yaml` support
- Environment variable overrides

**Priority:** MEDIUM - Maintainability

---

## Low Priority / Nice-to-Have 🔵

### 9. Docker Support
**Status:** ❌ None

**Deliverables:**
- [ ] `Dockerfile` for proxy
- [ ] `Dockerfile` for local agent
- [ ] `docker-compose.yml` for full stack
- [ ] Docker Hub images

**Example:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "simple_local_agent.py"]
```

**Priority:** LOW - Deployment convenience

---

### 10. Agent Templates & CLI
**Status:** ⚠️ Manual process

**Goal:** Make it easy to scaffold new agents

```bash
# Proposed CLI
agentbeats-local create my_agent --port 9025
# Creates:
#   my_agent.py
#   my_agent_card.toml
#   tests/test_my_agent.py
```

**Priority:** LOW - Developer experience

---

### 11. Testing Suite
**Status:** ⚠️ Only manual testing

**Needed:**
- [ ] Unit tests for proxy
- [ ] Integration tests for message flow
- [ ] Load tests (concurrent messages)
- [ ] Chaos testing (network failures)

**Tools:**
- pytest for unit/integration
- locust for load testing
- toxiproxy for chaos testing

**Priority:** LOW - Quality assurance

---

### 12. Documentation
**Status:** ⚠️ Partial

**Missing:**
- [ ] API reference (OpenAPI/Swagger)
- [ ] Architecture diagrams (C4 model)
- [ ] Deployment guide (AWS/GCP/Azure)
- [ ] Troubleshooting runbook
- [ ] Video tutorials

**Priority:** LOW - User onboarding

---

## Research / Exploration 🔬

### 13. Alternative Transports
**Status:** 💡 Idea

**Options to explore:**
- gRPC instead of HTTP/JSON
- MQTT for pub/sub
- Redis Streams for queueing
- Kafka for high throughput

**Priority:** RESEARCH - Future optimization

---

### 14. Agent Marketplace
**Status:** 💡 Idea

**Vision:**
- Repository of reusable agents
- One-click deployment
- Rating/review system
- Monetization

**Priority:** RESEARCH - Long-term vision

---

## Quick Wins (Do These First) ⚡

1. **Add `.env` example** (5 min)
   ```bash
   cp .env .env.example
   echo "OPENAI_API_KEY=your-key-here" > .env.example
   ```

2. **Add requirements.txt** (5 min)
   ```bash
   pip freeze > requirements.txt
   ```

3. **Fix stop_demo.sh to kill zombies** (10 min)
   ```bash
   pkill -9 -f "agentbeats run"
   pkill -9 -f "simple_local_agent"
   ```

4. **Add health check endpoint** (15 min)
   ```python
   @app.get("/health")
   def health():
       return {"status": "ok", "timestamp": datetime.now()}
   ```

5. **Add version info** (10 min)
   ```python
   __version__ = "0.1.0-poc"
   @app.get("/version")
   def version():
       return {"version": __version__}
   ```

---

## Progress Tracking

- ❌ Not started
- ⚠️ Partially done
- ✅ Complete
- 💡 Idea/research
- 🔴 Critical
- 🟡 High priority
- 🟢 Medium priority
- 🔵 Low priority

**Last updated:** 2025-10-10
