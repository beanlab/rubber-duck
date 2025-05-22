import asyncio
from asyncio import timeout
from typing import Optional

from quest import step, wrap_steps, queue
import discord
from discord.ui import View, Select

from ..conversation.conversation import BasicSetupConversation
from ..utils.gen_ai import RetryableGenAI, RecordMessage, GPTMessage, RecordUsage, GenAIException, Sendable
from ..utils.logger import duck_logger
from ..utils.protocols import Message, SendMessage, IndicateTyping, AddReaction, ReportError
from ..views.assignment_selection_view import AssignmentSelectionView


class MultiPromptConversation:
    def __init__(self,
                 ai_client: RetryableGenAI,
                 record_message: RecordMessage,
                 record_usage: RecordUsage,
                 typing: IndicateTyping,
                 send_message: SendMessage,
                 report_error: ReportError,
                 add_reaction: AddReaction,
                 setup_conversation: BasicSetupConversation,
                 ):
        self._ai_client = ai_client
        wrap_steps(self._ai_client, ['get_completion'])

        self._record_message = step(record_message)
        self._record_usage = step(record_usage)

        self._typing = typing
        self._send_message = step(send_message)
        self._report_error = step(report_error)
        self._add_reaction: AddReaction = step(add_reaction)

        self._prompt_index = 0
        self._setup_conversation = step(setup_conversation)
        self._selected_assignment: Optional[str] = None

    async def _handle_assignment_selection(self, assignment: str):
        self._selected_assignment = assignment
        # Convert assignment name to folder name (e.g., "Project 1" -> "project_1")
        folder_name = assignment.lower().replace(' ', '_')
        print(f"Selected project folder: {folder_name}")
        return [folder_name]

    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):
        assignments = settings["assignment_names"]
        timeout = settings["timeout"]

        # Create and send the view with assignment selection
        view = AssignmentSelectionView(assignments, self._handle_assignment_selection, timeout=timeout)
        await self._send_message(thread_id, view=view)

        # Wait for assignment selection
        while not self._selected_assignment:
            await asyncio.sleep(0.1)
            if timeout > 0:
                timeout -= 0.1
                if timeout <= 0:
                    break

        if not self._selected_assignment:
            await self._send_message(thread_id, "No assignment selected. Please try again.")
            return

        # Continue with the selected assignment
        folder_name = await self._handle_assignment_selection(self._selected_assignment)
        return folder_name
