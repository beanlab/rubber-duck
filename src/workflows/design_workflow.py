from pathlib import Path
from typing import TypedDict, List
from quest import step, queue, wrap_steps
import asyncio

from ..agents.gen_ai import RecordMessage, RecordUsage, RetryableGenAI, GenAIException, AgentClient
from ..conversation.conversation import AGENT_NAME, AGENT_MESSAGE
from ..utils.config_types import GPTMessage, DuckContext, AgentMessage
from ..utils.logger import duck_logger
from ..utils.protocols import Message


class DesignWorkflowSettings(TypedDict):
    introduction: str
    assignment_names: dict[str, Path]
    agents: List[dict]
    timeout: int
    file_size_limit: int
    file_type_ext: List[str]


class DesignWorkflow:
    def __init__(
            self,
            name: str,
            ai_completion_retry_protocol: dict,
            settings: DesignWorkflowSettings,
            bot,
            record_message: RecordMessage,
            record_usage: RecordUsage
    ):
        self._name = name
        self._settings = settings
        self._bot = bot
        self._record_message = record_message
        self._record_usage = record_usage

    @step
    async def _send_message(self, thread_id, content=None, file=None):
        """Send a message to the thread"""
        return await self._bot.send_message(thread_id, content, file)

    @step
    async def _get_available_assignments(self, thread_id):
        """Get and display available assignments"""
        assignments = list(self._settings['assignment_names'].keys())
        await self._send_message(
            thread_id,
            'Please select an assignment by number:\n' +
            '\n'.join(f"{i+1}. {name}" for i, name in enumerate(assignments))
        )
        return assignments

    @step
    async def _handle_assignment_selection(self, thread_id, assignments):
        """Handle user's assignment selection"""
        async with queue('messages', None) as messages:
            while True:
                try:
                    message = await asyncio.wait_for(
                        messages.get(),
                        self._settings['timeout']
                    )
                    try:
                        selection = int(message['content'])
                        if 1 <= selection <= len(assignments):
                            selected_name = assignments[selection - 1]
                            selected_path = self._settings['assignment_names'][selected_name]
                            return selected_name, selected_path
                        else:
                            await self._send_message(thread_id,
                                                    f"Please enter a number between 1 and {len(assignments)}")
                    except ValueError:
                        await self._send_message(thread_id, "Please enter a valid number")
                except asyncio.TimeoutError:
                    raise TimeoutError("No assignment selected within time limit")

    @step
    async def _get_and_send_ai_response(
            self,
            context: DuckContext,
            agent_name: str,
            message_history: list[GPTMessage]
    ) -> tuple[AGENT_NAME, AGENT_MESSAGE]:
        """Get AI response and send it to the user"""
        response: AgentMessage = await self._ai_clients[agent_name].get_completion(
            context,
            message_history,
        )

        if file := response.get('file'):
            await self._send_message(context.thread_id, file=file)
            return file['filename']

        if content := response.get('content'):
            await self._send_message(context.thread_id, content)
            return response['agent_name'], content

        raise NotImplementedError(f'AI completion had neither content nor file.')

    @step
    async def __call__(self, context):
        """Main entry point for the design workflow"""
        thread_id = context.thread_id

        await self._send_message(thread_id, self._settings['introduction'])

        # Get and display available assignments
        assignments = await self._get_available_assignments(thread_id)
        
        try:
            # Get user's assignment selection
            selected_name, selected_path = await self._handle_assignment_selection(thread_id, assignments)
            await self._send_message(thread_id,
                                    f"Great! Let's discuss your design for: {selected_name}. How are you storing your information?")
        except TimeoutError:
            await self._send_message(thread_id, "No assignment was selected within the time limit. Please try again.")
            return

        # Read the assignment file
        try:
            with open(selected_path, 'r', encoding='utf-8') as f:
                assignment_content = f.read()
        except Exception as e:
            duck_logger.error(f"Failed to read assignment file {selected_path}: {e}")
            raise

        # Initialize message history with the selected assignment context and content
        message_history = [
            GPTMessage(role='system',
                        content=f"""You are a design mentor helping students improve their designs for the assignment: {selected_name}.
                        Here is the assignment description:
                        {assignment_content}
                        Please help the student think through their design by asking thoughtful questions and providing guidance.""")
        ]

        # Main conversation loop
        async with queue('messages', None) as messages:
            while True:
                try:  # catch GenAIException
                    try:  # Timeout
                        message: Message = await asyncio.wait_for(
                            messages.get(),
                            self._settings['timeout']
                        )

                    except asyncio.TimeoutError:
                        break

                    if len(message['file']) > 0:
                        await self._send_message(
                            context.thread_id,
                            "I'm sorry, I can't read file attachments. "
                            "Please resend your message with the relevant parts of your file included in the message."
                        )
                        continue

                    message_history.append(GPTMessage(role='user', content=message['content']))

                    await self._record_message(
                        context.guild_id, context.thread_id, context.author_id, message_history[-1]['role'],
                        message_history[-1]['content']
                    )

                    agent_name, response = await self._get_and_send_ai_response(
                        context=context,
                        agent_name=self._settings['agents'][0]['name'],
                        message_history=message_history
                    )

                    message_history.append(GPTMessage(role='assistant', content=response))

                except GenAIException:
                    await self._send_message(context.thread_id,
                                             'I\'m having trouble processing your request.'
                                             'The admins are aware. Please try again later.')
                    raise
