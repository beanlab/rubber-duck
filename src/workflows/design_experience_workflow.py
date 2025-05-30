from quest import step, queue
import asyncio
from pathlib import Path


from ..conversation.learning_objectives_tracker import LearningObjectivesTracker
from ..utils.config_types import LearningObjectiveSettings
from ..utils.file_utils import process_attachments
from ..utils.logger import duck_logger
from ..utils.protocols import Message
from ..views.assignment_selection_view import AssignmentSelectionView

class DesignExperienceWorkflow:
    def __init__(self,
                 send_message,
                 get_channel,
                 fetch_guild,
                 learning_objective_tracker: LearningObjectivesTracker,
                 ):
        self._send_message = step(send_message)
        self._get_channel = get_channel
        self._get_guild = fetch_guild
        self._learning_objective_tracker = learning_objective_tracker

    async def _handle_assignment_selection(self, assignment: str):
        self._selected_assignment = assignment
        # Convert assignment name to folder name (e.g., "Project 1" -> "project_1")
        folder_name = assignment.lower().replace(' ', '_')
        duck_logger.debug(f"Selected project folder: {folder_name}")
        return folder_name

    async def _extract_assignment(self, assignments, thread_id, timeout):
        view = AssignmentSelectionView(assignments, self._handle_assignment_selection, timeout=timeout)
        await self._send_message(thread_id, view=view)

        try:
            # Wait for the user to select and confirm an assignment
            selected = await view.wait_for_selection()
            return await self._handle_assignment_selection(selected)
        except TimeoutError:
            raise TimeoutError("User did not select an assignment in time.")

    async def __call__(self, thread_id: int, settings, initial_message: Message):
        # Settings are prepared.
        assignments = settings["assignment_names"]
        timeout = settings["timeout"]

        # Create and send the view with assignment selection
        folder_name = await self._extract_assignment(assignments, thread_id, timeout) # Wrap in a step.

        await self._send_message(thread_id, "Welcome to the Design Experience! Please send us your design_experience.md file to get started.")

        # Wait for the design_experience.md file
        async with queue('messages', None) as messages:
            while True:
                try:
                    message: Message = await asyncio.wait_for(messages.get(), timeout)
                    
                    # Check if message has attachments
                    if not message['file']:
                        await self._send_message(thread_id, "Please upload a markdown file (.md) with your design experience.")
                        continue

                    # Process attachments
                    processed_files = await process_attachments(message['file'])
                    
                    # Look for any markdown file
                    markdown_file = None
                    for filename, file_content in processed_files:
                        if filename.endswith('.md'):
                            markdown_file = file_content
                            break
                    
                    if not markdown_file:
                        await self._send_message(thread_id, "Please upload a markdown file (.md) with your design experience.")
                        continue

                    # Process the markdown file
                    markdown_file.seek(0)
                    content = markdown_file.read().decode('utf-8')

                    # Initialize learning objectives tracker with the markdown content
                    learning_objective_file = f"prompts/{folder_name}/learning_topics.yaml"
                    prompt_file = "prompts/learning_objectives.txt"
                    
                    # Check if files exist
                    if not Path(learning_objective_file).exists():
                        duck_logger.error(f"Learning objectives file not found: {learning_objective_file}")
                        await self._send_message(thread_id, "Sorry, there was an error processing your submission. The learning objectives file is missing.")
                        break
                        
                    if not Path(prompt_file).exists():
                        duck_logger.error(f"Prompt file not found: {prompt_file}")
                        await self._send_message(thread_id, "Sorry, there was an error processing your submission. The prompt file is missing.")
                        break
                    
                    # Create settings object
                    settings:LearningObjectiveSettings = {
                        'learning_objective_file_path': learning_objective_file,
                        'prompt_file_path': prompt_file
                    }
                    
                    # Initialize the tracker with the current context
                    await self._learning_objective_tracker(thread_id, initial_message, settings)

                    # Send the markdown content to the tracker
                    missing_objectives = await self._learning_objective_tracker.get_missing_objectives(content)
                    if missing_objectives:
                        await self._send_message(thread_id, f"Here are the objectives that need more attention:\n{missing_objectives}")
                    else:
                        await self._send_message(thread_id, "Great job! You've covered all the learning objectives.")
                    
                    break

                except asyncio.TimeoutError:
                    await self._send_message(thread_id, "No file was uploaded within the time limit. Please try again.")
                    break
        self._send_message(thread_id, "Welcome to the Design Experience!")
        # Learning objectives tracker is initialized and returns a list of topic objects.
        # The workflow will then iterate through the objectives.
        # While iterating the code will get sent to state token manager which will check if the user has a token signaling they are ready to proceed or switch topics.
        # Once finished the workflow will say thank you for completing the experience and approve them to go and code.
