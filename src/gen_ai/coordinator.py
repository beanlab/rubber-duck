from typing import Optional, Literal

from education.scratch.Duck_Agent.agent import Agent
from education.scratch.Duck_Agent.context import Context, Message
from education.scratch.Duck_Agent.tools import ToolRegistry


class ConversationSession:
    def __init__(self):
        self.agent_contexts: dict[str, Context] = {}
        self.current_agent_name: Optional[str] = None
        self.conversation_active: bool = True

    def get_context(self, agent_name: str) -> Context:
        if agent_name not in self.agent_contexts:
            self.agent_contexts[agent_name] = Context()
        return self.agent_contexts[agent_name]

    def reset(self):
        self.agent_contexts.clear()
        self.current_agent_name = None
        self.conversation_active = True


class AgentCoordinator:
    def __init__(self):
        self.agents = {}

    def register_agent(self, agent: Agent):
        self.agents[agent.get_agent_name()] = agent

    def setup_handoffs(self, tool_registry: ToolRegistry):
        for agent_name, agent in self.agents.items():
            handoff_tools = []
            for target_agent_name in agent.handoff_agent_names:
                if target_agent_name in self.agents:
                    target_agent = self.agents[target_agent_name]
                    handoff_tool = agent._create_handoff_tool(
                        target_agent_name,
                        target_agent._handoff_description,
                        tool_registry
                    )
                    handoff_tools.append(handoff_tool)

            agent.add_handoff_tools(handoff_tools)

    def get_initialized_context(self, agent_name: str, session: ConversationSession) -> Context:
        context = session.get_context(agent_name)
        agent = self.agents[agent_name]

        if not context.get_items():
            context.update(Message(role='system', content=agent._prompt))
            context.update(Message(role='developer',
                                   content="It is mandatory to greet the user and talk to them using the talk_to_user tool."))
            context.update(Message(role='user', content="Hi"))

        return context

    def start_conversation(self, initial_agent, message=None) -> ConversationSession:
        session = ConversationSession()
        session.current_agent_name = initial_agent.get_agent_name()
        current_message = message or Message(role='user', content="Hi")

        while session.conversation_active:
            current_agent = self.agents[session.current_agent_name]
            context = self.get_initialized_context(session.current_agent_name, session)

            result = current_agent.run_single_iteration(current_message, context)

            if result.type == "end":
                print(f"Conversation ended: {result.message}")
                break
            elif result.type == "handoff":
                self._handle_handoff(result, session)
                current_message = Message(role='user', content=result.handoff_message)
            elif result.type == "continue":
                current_message = None

        return session

    def _handle_handoff(self, handoff_result, session: ConversationSession):
        old_agent_name = session.current_agent_name
        new_agent_name = handoff_result.target_agent

        old_agent = self.agents[old_agent_name]

        old_context = session.get_context(old_agent_name)
        new_context = self.get_initialized_context(new_agent_name, session)

        handoff_summary = old_agent.summarize_context_for_handoff(old_context, new_agent_name)
        new_context.update(Message(role="system", content=handoff_summary))

        session.current_agent_name = new_agent_name


class Result:
    def __init__(self, result_type: Literal["continue", "handoff", "end"], message: str = "", target_agent: str = "",
                 handoff_message: str = ""):
        self.type = result_type
        self.message = message
        self.target_agent = target_agent
        self.message = handoff_message
