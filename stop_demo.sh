#!/bin/bash

# Stop all demo components

GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}[INFO]${NC} Stopping all demo components..."

# Stop by PID files
if [ -f logs/green_agent.pid ]; then
    GREEN_PID=$(cat logs/green_agent.pid)
    kill $GREEN_PID 2>/dev/null && echo "Stopped green agent (PID: $GREEN_PID)"
    rm logs/green_agent.pid
fi

if [ -f logs/red_agent.pid ]; then
    RED_PID=$(cat logs/red_agent.pid)
    kill $RED_PID 2>/dev/null && echo "Stopped red agent (PID: $RED_PID)"
    rm logs/red_agent.pid
fi

# Cleanup any remaining processes
pkill -f 'agentbeats run green_agent_card' 2>/dev/null
pkill -f 'simple_local_agent' 2>/dev/null
pkill -f 'red_agent_proxy' 2>/dev/null

echo -e "${GREEN}[INFO]${NC} All components stopped"
