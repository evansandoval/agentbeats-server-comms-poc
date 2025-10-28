# Multi-stage Dockerfile for A2A Agent Proxy Architecture
# Supports building: server, green-agent, white-agent

# ==============================================================================
# Base Stage: Common dependencies
# ==============================================================================
FROM python:3.13-slim AS base

# Install uv by copying from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install system dependencies (git needed for tau-bench from git)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python dependencies
RUN uv pip install --system -e .

# ==============================================================================
# Server Stage: WebSocket router only
# ==============================================================================
FROM base AS server

EXPOSE 8000

# Health check using the /health endpoint
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "src.server.server:app", "--host", "0.0.0.0", "--port", "8000"]

# ==============================================================================
# Agent Stage: Agents with auto-spawning proxy
# ==============================================================================
FROM base AS agent

# Agents will use standardized ports across all containers
# Since each container has isolated localhost, all agents can use same ports
# Default values (can be overridden in docker-compose.yml):
ENV AGENT_TYPE=green
ENV AGENT_NAME=tau_green_agent
ENV AGENT_HOST=0.0.0.0
ENV AGENT_PORT=9000
ENV PROXY_PORT=9001
ENV SERVER_URL=ws://server:8000
ENV AGENT_ID=green

# Expose standardized agent and proxy ports
EXPOSE 9000 9001

# No health check for agents - they don't expose /health endpoint
# The server's health check verifies agent registration via WebSocket
HEALTHCHECK NONE

# Entry point script that routes to appropriate agent
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

CMD ["/docker-entrypoint.sh"]
