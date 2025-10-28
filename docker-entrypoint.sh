#!/bin/bash
set -e

echo "Starting ${AGENT_TYPE} agent..."
echo "  Agent: ${AGENT_HOST}:${AGENT_PORT}"
echo "  Proxy: ${AGENT_HOST}:${PROXY_PORT}"
echo "  Server: ${SERVER_URL}"
echo "  Agent ID: ${AGENT_ID}"

if [ "$AGENT_TYPE" = "green" ]; then
    exec python -c "
from src.green_agent.agent import start_green_agent
import os

start_green_agent(
    agent_name=os.environ.get('AGENT_NAME', 'tau_green_agent'),
    host=os.environ.get('AGENT_HOST', '0.0.0.0'),
    port=int(os.environ.get('AGENT_PORT', '9000')),
    server_url=os.environ.get('SERVER_URL'),
    agent_id=os.environ.get('AGENT_ID', 'green'),
    proxy_port=int(os.environ.get('PROXY_PORT', '9001')),
)
"
elif [ "$AGENT_TYPE" = "white" ]; then
    exec python -c "
from src.white_agent.agent import start_white_agent
import os

start_white_agent(
    agent_name=os.environ.get('AGENT_NAME', 'general_white_agent'),
    host=os.environ.get('AGENT_HOST', '0.0.0.0'),
    port=int(os.environ.get('AGENT_PORT', '9000')),
    server_url=os.environ.get('SERVER_URL'),
    agent_id=os.environ.get('AGENT_ID', 'white-1'),
    proxy_port=int(os.environ.get('PROXY_PORT', '9001')),
)
"
else
    echo "Error: Unknown AGENT_TYPE '${AGENT_TYPE}'. Must be 'green' or 'white'."
    exit 1
fi
