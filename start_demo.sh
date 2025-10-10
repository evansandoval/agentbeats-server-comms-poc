#!/bin/bash

# Demo script to start green agent and local red agent for testing

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Check environment
if [ -z "$OPENAI_API_KEY" ]; then
    print_error "OPENAI_API_KEY not set!"
    echo "Please set your OpenAI API key:"
    echo "  export OPENAI_API_KEY='your-key-here'"
    exit 1
fi

print_header "AgentBeats Demo - Starting Components"

# Create logs directory
mkdir -p logs

# Start Green Agent
print_status "Starting Green Agent on port 9031..."
python -m agentbeats run green_agent_card.toml \
  --launcher_host 0.0.0.0 --launcher_port 9030 \
  --agent_host 0.0.0.0 --agent_port 9031 \
  --model_type openai --model_name gpt-4o-mini \
  --tool green_tools.py \
  > logs/green_agent.log 2>&1 &
GREEN_PID=$!
print_status "Green Agent started (PID: $GREEN_PID)"

# Wait for green agent to be ready
sleep 5

# Start Local Red Agent (with auto-proxy)
print_status "Starting Local Red Agent with auto-proxy on port 9021..."
python simple_local_agent.py > logs/red_agent.log 2>&1 &
RED_PID=$!
print_status "Local Red Agent started (PID: $RED_PID)"

# Wait for proxy to be ready
sleep 3

# Verify components are running
print_status "Verifying components..."

if ! curl -s http://localhost:9031/.well-known/agent.json > /dev/null; then
    print_error "Green agent not responding!"
    kill $GREEN_PID $RED_PID 2>/dev/null || true
    exit 1
fi
print_status "✓ Green agent is ready"

if ! curl -s http://localhost:9021/.well-known/agent.json > /dev/null; then
    print_error "Red agent proxy not responding!"
    kill $GREEN_PID $RED_PID 2>/dev/null || true
    exit 1
fi
print_status "✓ Red agent proxy is ready"

print_header "Components Running Successfully"
echo ""
print_status "Green Agent (Orchestrator):"
print_status "  - URL: http://localhost:9031"
print_status "  - Logs: tail -f logs/green_agent.log"
print_status "  - PID: $GREEN_PID"
echo ""
print_status "Red Agent (Local with Proxy):"
print_status "  - Proxy URL: http://localhost:9021"
print_status "  - Logs: tail -f logs/red_agent.log"
print_status "  - PID: $RED_PID"
echo ""

print_header "Next Steps"
echo ""
print_warning "To trigger a battle, you need to send a message to the green agent"
print_warning "telling it to communicate with the red agent."
echo ""
print_status "You can do this by:"
echo ""
echo "1. Using AgentBeats backend (if running):"
echo "   - Register agents to backend"
echo "   - Create a battle via backend API"
echo ""
echo "2. Direct A2A message to green agent:"
echo "   curl -X POST http://localhost:9031/tasks \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{"
echo "       \"task_id\": \"test_battle_1\","
echo "       \"message\": {"
echo "         \"parts\": [{"
echo "           \"type\": \"text\","
echo "           \"text\": \"Start battle. Red agent URL: http://localhost:9021/\""
echo "         }]"
echo "       }"
echo "     }'"
echo ""
echo "3. Use the trigger_battle.py script (see below)"
echo ""

print_header "To Stop All Components"
echo ""
echo "kill $GREEN_PID $RED_PID"
echo ""
echo "Or press Ctrl+C and run:"
echo "pkill -f 'agentbeats run green_agent_card'"
echo "pkill -f simple_local_agent"
echo ""

# Save PIDs to file for easy cleanup
echo "$GREEN_PID" > logs/green_agent.pid
echo "$RED_PID" > logs/red_agent.pid

print_status "PIDs saved to logs/*.pid for easy cleanup"
print_status ""
print_status "Press Ctrl+C to stop monitoring. Processes will continue running."
print_status "Use ./stop_demo.sh to stop all components."

# Monitor logs
trap "echo ''; print_warning 'Stopping log monitoring (agents still running)...'; exit 0" INT

echo ""
print_header "Monitoring Logs (Ctrl+C to exit)"
echo ""

tail -f logs/green_agent.log logs/red_agent.log
