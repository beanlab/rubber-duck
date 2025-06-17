from pathlib import Path
from typing import TypedDict, Any, Coroutine
from quest import step, queue
import asyncio

from ..agents.hooks import UsageAgentHooks
from ..utils.config_types import GPTMessage
from ..utils.logger import duck_logger
from ..utils.protocols import Message
from ..agents.gen_ai import RecordMessage, RecordUsage, AgentClient, RetryableGenAI, GenAIException
from ..agents.agent_builder import _build_agents, _get_armory


class DesignWorkflowSettings(TypedDict):
    assignment_names: dict[str,Path]
    "assignment names will be numbered and correlated to a file path"
    introduction: str

class DesignWorkflow:
    def __init__(self,
                 name: str,
                 config: dict,
                 settings: DesignWorkflowSettings,
                 bot,
                 record_message: RecordMessage,
                 record_usage: RecordUsage
                 ):
        self.name = name
        self._config = config
        self._settings = settings
        self._bot = bot
        self._record_message = step(record_message)
        self._record_usage = step(record_usage)
        self._send_message = step(bot.send_message)
        self._add_reaction = step(bot.add_reaction)
        self._wait_for_user_timeout = settings.get('timeout', 300)

        # Set up the AI agent
        usage_hooks = UsageAgentHooks(record_usage)
        armory = _get_armory(config)
        agents = _build_agents(armory, usage_hooks, settings['agents'])
        ai_completion_retry_protocol = config['ai_completion_retry_protocol']

        self._genai_client = RetryableGenAI(
            AgentClient(agents[settings['agents'][0]['name']], bot.typing),
            bot.send_message,
            ai_completion_retry_protocol
        )

    async def _get_available_assignments(self, thread_id: int) -> dict[str, Path]:
        """Gets available assignments from settings"""
        assignments = self._settings.get("assignment_names", [])
        if not assignments:
            duck_logger.error("No assignments configured in settings")
            raise ValueError("No assignments configured")

        # Send numbered list of assignments
        message = "Please select an assignment by number:\n"
        for i, assignment in enumerate(assignments, 1):
            message += f"{i}. {assignment}\n"
        await self._send_message(thread_id, message)

        return assignments

    async def _handle_assignment_selection(self, thread_id: int, assignments: list[str]) -> str:
        """Handles the assignment selection process"""
        async with queue('messages', None) as messages:
            while True:
                try:
                    message: Message = await asyncio.wait_for(
                        messages.get(),
                        self._wait_for_user_timeout
                    )
                    
                    try:
                        selection = int(message['content'].strip())
                        if 1 <= selection <= len(assignments):
                            return assignments[selection - 1]
                        else:
                            await self._send_message(thread_id, f"Please enter a number between 1 and {len(assignments)}")
                    except ValueError:
                        await self._send_message(thread_id, "Please enter a valid number")
                        
                except asyncio.TimeoutError:
                    raise TimeoutError("No response received within the time limit")

    async def _get_and_send_ai_response(self, context, message_history):
        response = await self._genai_client.get_completion(
            {"thread_id": context.thread_id},
            message_history
        )
        if content := response.get('content'):
            await self._send_message(context.thread_id, content)
            return content
        else:
            await self._send_message(context.thread_id, "I'm having trouble processing your request. Please try again.")
            return None

    async def __call__(self, thread_id: int, initial_message: Message):
        await self._send_message(thread_id, self._settings['introduction'])

        # Get and display available assignments
        assignments = await self._get_available_assignments(thread_id)
        
        try:
            # Get user's assignment selection
            selected_assignment = await self._handle_assignment_selection(thread_id, assignments)
            await self._send_message(thread_id, f"Great! Let's discuss your design for: {selected_assignment}. Please describe your design or paste your code.")
        except TimeoutError:
            await self._send_message(thread_id, "No assignment was selected within the time limit. Please try again.")
            return

        # Initialize message history with the selected assignment context
        message_history = [
            GPTMessage(role='system', content=f"You are a design mentor helping students improve their designs for the assignment: {selected_assignment}.")
        ]

        # Main conversation loop
        async with queue('messages', None) as messages:
            while True:
                try:
                    try:
                        message: Message = await asyncio.wait_for(
                            messages.get(),
                            self._wait_for_user_timeout
                        )
                    except asyncio.TimeoutError:
                        break

                    # If the user sent a file, treat it as text if possible
                    user_content = message['content']
                    if len(message['file']) > 0:
                        # Just mention that file was received, or optionally try to read as text
                        user_content += "\n[File(s) attached, please paste relevant code or text if not already included.]"

                    message_history.append(GPTMessage(role='user', content=user_content))

                    await self._record_message(
                        message['guild_id'], thread_id, message['author_id'],
                        message_history[-1]['role'], message_history[-1]['content']
                    )

                    response = await self._get_and_send_ai_response(
                        message,
                        message_history
                    )

                    if response:
                        message_history.append(GPTMessage(role='assistant', content=response))

                except GenAIException:
                    await self._send_message(thread_id,
                                             'I\'m having trouble processing your request.'
                                             'The admins are aware. Please try again later.')
                    raise 