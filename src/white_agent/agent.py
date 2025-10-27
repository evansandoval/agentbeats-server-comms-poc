"""White agent implementation - the target agent being tested."""

import uvicorn
import dotenv
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentSkill, AgentCard, AgentCapabilities
from a2a.utils import new_agent_text_message
from litellm import completion


dotenv.load_dotenv()


def prepare_white_agent_card(url):
    skill = AgentSkill(
        id="task_fulfillment",
        name="Task Fulfillment",
        description="Handles user requests and completes tasks",
        tags=["general"],
        examples=[],
    )
    card = AgentCard(
        name="file_agent",
        description="Test agent from file",
        url=url,
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(),
        skills=[skill],
    )
    return card


class GeneralWhiteAgentExecutor(AgentExecutor):
    def __init__(self):
        self.ctx_id_to_messages = {}

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # parse the task
        print(f"\n{'='*60}", flush=True)
        print(f"[AGENT:white] ⚪ EXECUTING request", flush=True)
        print(f"  Context ID: {context.context_id}", flush=True)
        print(f"{'='*60}\n", flush=True)

        user_input = context.get_user_input()
        if context.context_id not in self.ctx_id_to_messages:
            self.ctx_id_to_messages[context.context_id] = []
        messages = self.ctx_id_to_messages[context.context_id]
        messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )
        response = completion(
            messages=messages,
            model="openai/gpt-4o",
            custom_llm_provider="openai",
            temperature=0.0,
        )
        next_message = response.choices[0].message.model_dump()  # type: ignore

        print(next_message["content"])
        messages.append(
            {
                "role": "assistant",
                "content": next_message["content"],
            }
        )
        await event_queue.enqueue_event(
            new_agent_text_message(
                next_message["content"], context_id=context.context_id
            )
        )

    async def cancel(self, context, event_queue) -> None:
        raise NotImplementedError


def start_white_agent(
    agent_name="general_white_agent",
    host="localhost",
    port=9002,
    server_url=None,
    agent_id=None,
    proxy_port=None,
):
    """
    Start white agent with optional proxy support.

    Args:
        agent_name: Name of the agent
        host: Host to bind agent HTTP server
        port: Port for agent HTTP server
        server_url: WebSocket URL of central server (e.g., ws://localhost:8000)
        agent_id: Agent identifier for registration
        proxy_port: Port for proxy HTTP server
    """
    print("Starting white agent...")

    # Start proxy if configuration provided
    if server_url and agent_id and proxy_port:
        print(f"White agent spawning proxy: agent_id={agent_id}, proxy_port={proxy_port}")
        import multiprocessing
        from src.proxy.agent_proxy import start_agent_proxy

        local_agent_url = f"http://{host}:{port}"
        p_proxy = multiprocessing.Process(
            target=start_agent_proxy,
            args=(agent_id, local_agent_url, server_url, proxy_port, host),
        )
        p_proxy.start()
        print(f"White agent proxy started (PID: {p_proxy.pid})")

    # Start agent HTTP server
    url = f"http://{host}:{port}"
    card = prepare_white_agent_card(url)

    request_handler = DefaultRequestHandler(
        agent_executor=GeneralWhiteAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=card,
        http_handler=request_handler,
    )

    uvicorn.run(app.build(), host=host, port=port)
