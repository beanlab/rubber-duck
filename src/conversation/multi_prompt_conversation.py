import asyncio
from asyncio import timeout
from pathlib import Path
from typing import Optional

from quest import step, wrap_steps, queue

from .learning_objectives_tracker import LearningObjectivesTracker
from ..conversation.conversation import BasicSetupConversation
from ..utils.gen_ai import RetryableGenAI, RecordMessage, GPTMessage, RecordUsage, GenAIException, Sendable
from ..utils.logger import duck_logger
from ..utils.protocols import Message, SendMessage, IndicateTyping, AddReaction, ReportError
from ..utils.folder_utils import FolderUtils
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

        self._learning_objectives_tracker = LearningObjectivesTracker(ai_client)
        self._record_message = step(record_message)
        self._record_usage = step(record_usage)

        self._typing = typing
        self._send_message = step(send_message)
        self._report_error = step(report_error)
        self._add_reaction: AddReaction = step(add_reaction)

        self._token_present = False
        self._user_ready = False
        self._prompt_index = 0
        self._setup_conversation = step(setup_conversation)
        self._selected_assignment: Optional[str] = None
        self._folder_utils = FolderUtils()

    async def _handle_assignment_selection(self, assignment: str):
        self._selected_assignment = assignment
        # Convert assignment name to folder name (e.g., "Project 1" -> "project_1")
        folder_name = assignment.lower().replace(' ', '_')
        duck_logger.debug(f"Selected project folder: {folder_name}")
        return [folder_name]

    async def extract_assignment(self, assignments, thread_id, timeout):
        view = AssignmentSelectionView(assignments, self._handle_assignment_selection, timeout=timeout)
        await self._send_message(thread_id, view=view)

        try:
            # Wait for the user to select and confirm an assignment
            selected = await view.wait_for_selection()
            return await self._handle_assignment_selection(selected)
        except TimeoutError:
            raise TimeoutError("User did not select an assignment in time.")

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

    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):
        assignments = settings["assignment_names"]
        timeout = settings["timeout"]
        engine = settings["engine"]
        introduction = settings["introduction"]
        tools = settings.get("tool", [])  # Get tools from settings, default to empty list

        # Create and send the view with assignment selection
        folder_name = await self.extract_assignment(assignments, thread_id, timeout)

        prompts, learning_objectives = await self.get_prompts_and_objectives(folder_name, thread_id)
        
        self._learning_objectives_tracker(
            guild_id=initial_message['guild_id'],
            thread_id=thread_id,
            user_id=initial_message['author_id'],
            engine=engine,
            learning_objective_file_path="/prompts/project3_network_routing/learning_objects_pq2.yaml",
            prompt_file_path="/prompts/learning_objectives_prompt.txt"
        )

        await self._send_message(thread_id, f"Found selected assignment. Beginning conversation.")
        await self._send_message(thread_id, introduction)

        # Do a do short convo
        while prompts:  # don't remove the prompt early
            current_prompt = prompts.pop(0)
            prompt = Path(current_prompt).read_text(encoding="utf-8")
            message_history = await self._setup_conversation(thread_id, prompt,
                                                             initial_message)  # The prompt is stored in the message history
            async with queue('messages', None) as messages:
                while True:
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

                        missing_objectives = self._learning_objectives_tracker.get_missing_objectives(message['content'])

                        user_id = message['author_id']
                        guild_id = message['guild_id']

                        if self._learning_objectives_tracker.all_objectives_complete():
                            await self._orchestrate_messages("All objectives have been complete", guild_id, thread_id, user_id, [])
                            break

                        await self._orchestrate_messages(missing_objectives, guild_id, thread_id, user_id, [])

                        # TODO add a sub conversation -- ask the user what they would like to talk about next.
                            # Then ask a sub bot to have that conversation about that objective

                        # await self._record_message(
                        #     guild_id, thread_id, user_id, message_history[-1]['role'], message_history[-1]['content']
                        # )


                    except GenAIException:
                        await self._send_message(thread_id,
                                                 'I\'m having trouble processing your request.'
                                                 'The admins are aware. Please try again later.')
                        raise

    async def get_prompts_and_objectives(self, folder_name, thread_id):
        """Checks if the folder name is valid and returns the prompts and learning objectives"""
        prompts = self._folder_utils.get_text_files(folder_name)
        if not prompts:
            raise ValueError("No files found in the selected assignment.")
        else:
            duck_logger.debug(f"Found {len(prompts)} files in the selected assignment.")
        learning_objectives = self._folder_utils.get_yaml_files(folder_name)
        if not learning_objectives:
            raise ValueError("No learning objective YAML files found in the selected assignment.")
        else:
            duck_logger.debug(
                f"Found {len(learning_objectives)} learning objective YAML files in the selected assignment.")
            await self._send_message(thread_id, f"Found learning objectives. Beginning conversation.")
        return prompts, learning_objectives

    def _ready_for_next_set_of_learning_objectives(self):
        """Checks if the user typed continue and the object is completed"""
        if self._token_present & self._user_ready:
            self._token_present = False
            self._user_ready = False
            duck_logger.debug(f"User and prompt are ready. Advancing to next prompt.")

    def _check_objectives_complete(self, message_history) -> bool | None:
        """Checks if the user has completed the learning objectives"""
        most_recent_info = message_history[-1].get('content')
        if "Objective Complete!" in most_recent_info:
            duck_logger.debug("Objective Complete and token present")
            self._token_present = True

    def _confirm_user_ready(self, message_history) -> bool | None:
        """Checks if the user is ready to continue"""
        most_recent_info = message_history[-1].get('content')
        if "continue" in most_recent_info:
            duck_logger.debug("User is ready to continue")
            self._user_ready = True
