import ast
import asyncio

from pathlib import Path
from typing import Protocol

from agents import Agent, ModelSettings, Runner, RunContextWrapper, handoff
from quest import step, queue, wrap_steps

from ..armory.agent_tools import AgentTools
from ..armory.armory import Armory
from ..utils.gen_ai import RetryableGenAI, GPTMessage, RecordMessage, RecordUsage, GenAIException, Sendable
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
        message_history = [GPTMessage(role='system', content="Introduce yourself and what you can do to the user using the talk_to_user tool"), GPTMessage(role='user', content="Hi")]
        user_id = initial_message['author_id']
        guild_id = initial_message['guild_id']

        await self._record_message(
            guild_id, thread_id, user_id, message_history[0]['role'], message_history[0]['content'])
        await self._record_message(
            guild_id, thread_id, user_id, message_history[1]['role'], message_history[1]['content'])
        return message_history

class BasicPromptConversation:
    def __init__(self,
                 ai_client: RetryableGenAI,
                 record_message: RecordMessage,
                 record_usage: RecordUsage,
                 send_message: SendMessage,
                 report_error: ReportError,
                 add_reaction: AddReaction,
                 setup_conversation: BasicSetupConversation,
                 ):
        self._ai_client = wrap_steps(ai_client, ['get_completion'])

        self._record_message = step(record_message)
        self._record_usage = step(record_usage)

        self._send_message = step(send_message)
        self._report_error = step(report_error)
        self._add_reaction: AddReaction = step(add_reaction)

        self._setup_conversation = step(setup_conversation)

    async def _orchestrate_messages(self, sendables: [Sendable], guild_id: int, thread_id: int, user_id: int, message_history: list[GPTMessage]):
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

    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):

        prompt_file = settings["prompt_file"]
        if prompt_file:
            prompt = Path(prompt_file).read_text(encoding="utf-8")
        else:
            prompt = initial_message['content']

        # Get engine and timeout from duck settings, falling back to defaults if not set
        engine = settings["engine"]
        timeout = settings["timeout"]
        tools = settings.get('tools', [])
        introduction = settings.get("introduction", "Hi, how can I help you?")

        if 'duck' in initial_message['content']:
            await self._add_reaction(initial_message['channel_id'], initial_message['message_id'], "🦆")

        message_history = await self._setup_conversation(thread_id, prompt, initial_message)

        await self._send_message(thread_id, introduction)

        async with queue('messages', None) as messages:
            while True:
                # TODO - if the conversation is getting long, and the user changes the subject
                #  prompt them to start a new conversation (and close this one)

                try:  # catch all errors
                    try:
                        # Waiting for a response from the user
                        message: Message = await asyncio.wait_for(messages.get(), timeout)

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

    def find_last_agent_conversation(self, logs: list[dict], agents_dict: dict[str, Agent], head_agent: str) -> Agent:
        if logs is None or len(logs) <= 2:
            return agents_dict[head_agent]
        for entry in reversed(logs):
            if entry.get("type") == "function_call_output":
                output_str = entry.get("output", "")
                try:
                    output_dict = ast.literal_eval(output_str)
                    if "assistant" in output_dict:
                        last_agent_name = output_dict["assistant"].lower().replace(" ", "_")
                        return agents_dict[last_agent_name]
                except Exception:
                    continue
        return agents_dict[head_agent]

    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):

        agent_tools = AgentTools(self._record_message, self._send_message, self._typing, initial_message['guild_id'], thread_id, initial_message['author_id'], settings["timeout"])

        self._armory.scrub_tools(agent_tools)

        head_agent = settings["head_agent"]
        head_agent_name = head_agent["name"]
        head_agent_prompt = Path(head_agent["prompt"]).read_text(encoding="utf-8")
        head_agent_handoff_prompt = head_agent["handoff_prompt"]
        head_agent_tools = [self._armory.get_specific_tool_metadata(tool) for tool in head_agent["tools"] if tool in self._armory.get_all_tool_names()]
        head_agent_engine = head_agent["engine"]

        spoke_agents = settings["spoke_agents"]

        message_history = await self._setup_conversation(thread_id, initial_message)

        agent_dict = {}

        dispatch_agent = Agent(
            name=head_agent_name,
            handoff_description=head_agent_handoff_prompt,
            instructions=head_agent_prompt,
            tools=head_agent_tools,
            model=head_agent_engine,
            model_settings=ModelSettings(tool_choice="required"),
        )

        self._current_agent = dispatch_agent

        for agent in spoke_agents:
            agent_name = agent["name"]
            agent_prompt = Path(agent["prompt"]).read_text(encoding="utf-8")
            agent_handoff_prompt = agent["handoff_prompt"]
            agent_tools = [self._armory.get_specific_tool_metadata(tool) for tool in agent["tools"] if tool in self._armory.get_all_tool_names()]
            agent_engine = agent["engine"]

            agent_dict[agent_name] = Agent(
                name=agent_name,
                handoff_description=agent_handoff_prompt,
                instructions=agent_prompt,
                tools=agent_tools,
                model=agent_engine,
                model_settings=ModelSettings(tool_choice="required"),
            )


        def make_on_handoff(target_agent: Agent):
            async def _on_handoff(ctx: RunContextWrapper[None]):
                await self._record_usage(
                    initial_message['guild_id'],
                    initial_message['channel_id'],
                    thread_id,
                    initial_message['author_id'],
                    self._current_agent.model,
                    ctx.usage.__dict__['input_tokens'],
                    ctx.usage.__dict__['output_tokens'],
                    ctx.usage.__dict__.get('cached_tokens', 0),
                    ctx.usage.__dict__.get('reasoning_tokens', 0)
                )
                self._current_agent = target_agent
            return _on_handoff

        dispatch_handoff = handoff(
            agent=dispatch_agent,
            on_handoff=make_on_handoff(dispatch_agent)
        )

        for agent in agent_dict.values():
            agent.handoffs.append(dispatch_handoff)
            dispatch_agent.handoffs.append(handoff(agent=agent, on_handoff=make_on_handoff(agent)))

        agent_dict[head_agent_name] = dispatch_agent
        try:
            await Runner.run(self.find_last_agent_conversation(message_history, agent_dict, head_agent_name),
                                  message_history,
                                  max_turns=100)
        except Exception as e:
            return




