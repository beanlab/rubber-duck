import asyncio
import json
from pathlib import Path
from typing import Protocol, List

from agents import Agent, ModelSettings, Runner, RunContextWrapper, handoff
from quest import step, queue, wrap_steps

from ..armory.agent_tools import AgentTools
from ..armory.armory import Armory
from ..utils.gen_ai import GPTMessage, RecordMessage, RecordUsage, GenAIException, Sendable, GenAIClient
from ..utils.protocols import Message, SendMessage, ReportError, IndicateTyping, AddReaction


class HaveConversation(Protocol):
    async def __call__(self, thread_id: int, engine: str, message_history: list[GPTMessage], timeout: int = 600): ...


class BasicSetupConversation:
    def __init__(self, record_message):
        self._record_message = step(record_message)

    async def __call__(self, thread_id: int, prompt: str, initial_message: Message) -> list[GPTMessage]:
        message_history = [GPTMessage(role='system', content=prompt)]
        user_id = initial_message['author_id']
        guild_id = initial_message['guild_id']

        await self._record_message(
            guild_id, thread_id, user_id, message_history[0]['role'], message_history[0]['content'])
        return message_history


class AgentSetupConversation:
    def __init__(self, record_message):
        self._record_message = step(record_message)

    async def __call__(self, thread_id: int, initial_message: Message) -> list[GPTMessage]:
        message_history = [GPTMessage(role='system',
                                      content="Introduce yourself and what you can do to the user using the talk_to_user tool"),
                           GPTMessage(role='user', content="Hi")]
        user_id = initial_message['author_id']
        guild_id = initial_message['guild_id']

        await self._record_message(
            guild_id, thread_id, user_id, message_history[0]['role'], message_history[0]['content'])
        await self._record_message(
            guild_id, thread_id, user_id, message_history[1]['role'], message_history[1]['content'])
        return message_history


class AgentConversation:
    def __init__(self,
                 ai_agent: GenAIClient,
                 record_message: RecordMessage,
                 send_message: SendMessage,
                 report_error: ReportError,
                 add_reaction: AddReaction,
                 wait_for_user_timeout
                 ):
        self._ai_client = wrap_steps(ai_agent, ['get_completion'])

        self._record_message = step(record_message)

        self._send_message = step(send_message)
        self._report_error = step(report_error)
        self._add_reaction: AddReaction = step(add_reaction)

        self._wait_for_user_timeout = wait_for_user_timeout

    async def _orchestrate_messages(self, sendables: [Sendable], guild_id: int, thread_id: int, user_id: int,
                                    message_history: list[GPTMessage]):
        for sendable in sendables:
            if isinstance(sendable, str):
                await self._record_message(
                    guild_id, thread_id, user_id, 'assistant', sendable)
                await self._send_message(thread_id, message=sendable)
                message_history.append(GPTMessage(role='assistant', content=sendable))

            else:  # tuple of str, BytesIO -> i.e. an image
                await self._record_message(
                    guild_id, thread_id, user_id, 'assistant', f'<image {sendable[0]}>')
                await self._send_message(thread_id, file=sendable)
                message_history.append(GPTMessage(role='assistant', content=f'<image {sendable[0]}>'))

    async def __call__(self, thread_id: int, initial_message: Message):

        # prompt_file = settings["prompt_file"]
        # if prompt_file:
        #     prompt = Path(prompt_file).read_text(encoding="utf-8")
        # else:
        #     prompt = initial_message['content']
        #
        # # Get engine and timeout from duck settings, falling back to defaults if not set
        # engine = settings["engine"]
        # timeout = settings["timeout"]
        # tools = settings.get('tools', [])
        # introduction = settings.get("introduction", "Hi, how can I help you?")

        if 'duck' in initial_message['content']:
            await self._add_reaction(initial_message['channel_id'], initial_message['message_id'], "🦆")

        message_history = []

        introduction = self._ai_client.introduction or "Hi, how can I help you?"
        await self._send_message(thread_id, introduction)

        async with queue('messages', None) as messages:
            while True:
                try:  # catch all errors
                    try:
                        # Waiting for a response from the user
                        message: Message = await asyncio.wait_for(messages.get(), self._wait_for_user_timeout)

                    except asyncio.TimeoutError:  # Close the thread if the conversation has closed
                        break

                    if len(message['file']) > 0:
                        await self._send_message(
                            thread_id,
                            "I'm sorry, I can't read file attachments. "
                            "Please resend your message with the relevant parts of your file included in the message."
                        )
                        continue

                    message_history.append(GPTMessage(role='user', content=message['content']))

                    user_id = message['author_id']
                    guild_id = message['guild_id']

                    await self._record_message(
                        guild_id, thread_id, user_id, message_history[-1]['role'], message_history[-1]['content']
                    )

                    sendables = await self._ai_client.get_completion(
                        guild_id,
                        initial_message['channel_id'],
                        thread_id,
                        user_id,
                        engine,
                        message_history,
                        tools
                    )

                    await self._orchestrate_messages(sendables, guild_id, thread_id, user_id, message_history)

                except GenAIException:
                    await self._send_message(thread_id,
                                             'I\'m having trouble processing your request.'
                                             'The admins are aware. Please try again later.')
                    raise


class RunAgents:
    def __init__(self, spoke_agents: dict[str, Agent], head_agent: Agent, message_history: list,
                 initial_message: Message, thread_id: int, record_usage: RecordUsage, typing):
        self._spoke_agents = spoke_agents
        self._head_agent = head_agent
        self._message_history = message_history
        self._initial_message = initial_message
        self._thread_id = thread_id
        self._record_usage = record_usage
        self._typing = typing
        self._current_agent = head_agent

    def _find_last_agent_conversation(self) -> Agent:
        last_agent = self._head_agent
        it = iter(self._message_history)
        for entry in it:
            if entry.get("type") == "function_call" and entry.get("name", "").startswith("transfer_to_"):
                try:
                    output = next(it, None)
                    name_dict = json.loads(output.get("output", ""))
                    last_agent = self._spoke_agents.get(name_dict['assistant'], self._head_agent)
                except StopIteration:
                    return self._head_agent
        return last_agent

    def _make_on_handoff(self, target_agent: Agent):
        async def _on_handoff(ctx: RunContextWrapper[None]):
            await self._record_usage(
                self._initial_message['guild_id'],
                self._initial_message['channel_id'],
                self._thread_id,
                self._initial_message['author_id'],
                self._current_agent.model,
                ctx.usage.__dict__['input_tokens'],
                ctx.usage.__dict__['output_tokens'],
                ctx.usage.__dict__.get('cached_tokens', 0),
                ctx.usage.__dict__.get('reasoning_tokens', 0)
            )
            self._current_agent = target_agent

        return _on_handoff

    def _create_handoffs(self):
        dispatch_handoff = handoff(
            agent=self._head_agent,
            on_handoff=self._make_on_handoff(self._head_agent)
        )

        for agent in self._spoke_agents.values():
            agent.handoffs.append(dispatch_handoff)
            self._head_agent.handoffs.append(handoff(agent=agent, on_handoff=self._make_on_handoff(agent)))

    async def run(self):
        self._create_handoffs()
        try:

            await self._typing.__aenter__()
            await Runner.run(self._find_last_agent_conversation(),
                             self._message_history,
                             max_turns=100)
        except Exception as e:
            return


class BasicAgentConversation:

    def __init__(self,
                 record_message: RecordMessage,
                 record_usage: RecordUsage,
                 send_message: SendMessage,
                 setup_conversation: AgentSetupConversation,
                 typing: IndicateTyping,
                 armory: Armory
                 ):
        self._record_message = step(record_message)
        self._record_usage = step(record_usage)
        self._send_message = step(send_message)
        self._setup_conversation = step(setup_conversation)
        self._typing = typing
        self._armory = armory
        self._current_agent = None

    def create_agents(self, settings: dict) -> tuple[Agent, List[Agent]]:
        def build_agent(config: dict) -> Agent:
            return Agent(
                name=config["name"],
                handoff_description=config["handoff_prompt"],
                instructions=Path(config["prompt"]).read_text(encoding="utf-8"),
                tools=[
                    self._armory.get_specific_tool_metadata(tool)
                    for tool in config["tools"]
                    if tool in self._armory.get_all_tool_names()
                ],
                model=config["engine"],
                model_settings=ModelSettings(tool_choice="required"),
            )

        return build_agent(settings["head_agent"]), [
            build_agent(agent) for agent in settings.get("spoke_agents", [])
        ]

    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):
        typing = self._typing(thread_id)
        agent_tools = AgentTools(self._record_message, self._send_message, typing, initial_message['guild_id'],
                                 thread_id, initial_message['author_id'], settings["timeout"])

        self._armory.scrub_tools(agent_tools)

        message_history = await self._setup_conversation(thread_id, initial_message)

        head_agent, spoke_agents = self.create_agents(settings)

        spoke_agents = {
            agent.name: agent for agent in spoke_agents
        }

        run_agents = RunAgents(spoke_agents, head_agent, message_history, initial_message, thread_id,
                               self._record_usage, typing)

        await run_agents.run()
