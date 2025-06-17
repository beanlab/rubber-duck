from quest import wrap_steps
from pathlib import Path
import yaml
import json

from src.utils.config_types import LearningObjectiveSettings

from ..utils.gen_ai import GPTMessage
from src.utils.logger import duck_logger

class LearningObjective:
    def __init__(self, principles: list[str]):
        self.principles = principles

    def __str__(self):
        return "\n  - " + "\n  - ".join(self.principles)

class LearningObjectivesTracker:
    def __init__(self, ai_client):
        self._ai_client = ai_client
        wrap_steps(self._ai_client, ['get_completion'])

        self._guild_id = None
        self._thread_id = None
        self._user_id = None
        self._engine = None

    async def __call__(self, thread_id, initial_message, settings: LearningObjectiveSettings):
        self._learning_objective = self._get_learning_objectives_from_file(settings['learning_objective_file_path'])
        self._thread_id = thread_id
        self._guild_id = initial_message['guild_id']
        self._parent_channel_id = initial_message['channel_id']
        self._user_id = initial_message['author_id']
        self._engine = initial_message.get('engine', 'gpt-4')  # Default to gpt-4 if not specified

        self._prompt = self._get_prompt(settings['prompt_file_path'])
        
        # Format learning objectives as a flat list for the AI
        objectives_list = [principle.lower() for principle in self._learning_objective.principles]
        objectives_str = "\n".join(f"- {obj}" for obj in objectives_list)
        self._message_history = [
            GPTMessage(role='system', content=self._prompt),
            GPTMessage(role="system", content=f"Learning Objectives:\n{objectives_str}")
        ]

    def _get_learning_objectives_from_file(self, file_path: str):
        duck_logger.debug("Attempting to read learning objectives from file: %s", file_path)
        with open(file_path, 'r') as topics_file:
            topics_list = yaml.load(topics_file, Loader=yaml.SafeLoader)

        all_principles = []

        def helper(item):
            if isinstance(item, dict):
                # If the item has topic_principles, add them to our list
                if 'topic_principles' in item:
                    all_principles.extend(item['topic_principles'])
                # If the item is a dictionary with a list value, process each item in the list
                for value in item.values():
                    if isinstance(value, list):
                        for sub_item in value:
                            helper(sub_item)
            elif isinstance(item, list):
                # If the item is a list, process each item in the list
                for sub_item in item:
                    helper(sub_item)

        # Process each top-level dictionary in the list
        for item in topics_list:
            helper(item)

        # Create a single LearningObjective with all principles
        learning_objective = LearningObjective(principles=all_principles)
        duck_logger.debug(f"Extracted learning objectives: {learning_objective}")
        return learning_objective

    def _get_prompt(self, prompt_file_path):
        return Path(prompt_file_path).read_text(encoding="utf-8")

    def _create_partial_and_complete_lists(self, chat_results: list[dict]) -> None | str:
        missing_objectives = [
            (principle, result.get('reason', 'No reason provided'))
            for principle, result in zip(self._learning_objective.principles, chat_results)
            if not result.get('mentioned', False)
        ]

        partial_objectives = [
            (principle, result.get('reason', 'No reason provided'))
            for principle, result in zip(self._learning_objective.principles, chat_results)
            if result.get('mentioned', False) and not result.get('met', False)
        ]

        if missing_objectives:
            duck_logger.debug(f"Missing objectives: {missing_objectives}")
            missing_str = "Objectives that need to be addressed:\n" + "\n".join(f"- {obj}\n  Reason: {reason}" for obj, reason in missing_objectives)
        if partial_objectives:
            duck_logger.debug(f"Partial objectives: {partial_objectives}")
            partial_str = "Objectives that need more understanding:\n" + "\n".join(f"- {obj}\n  Reason: {reason}" for obj, reason in partial_objectives)
        if not missing_objectives and not partial_objectives:
            duck_logger.debug("All objectives have been met.")
            return None
        
        # Combine the messages with clear separation
        messages = []
        if missing_objectives:
            messages.append(missing_str)
        if partial_objectives:
            messages.append(partial_str)
        
        return  "\n\n".join(messages)

    async def get_missing_objectives(self, most_recent_user_message: str) -> str:
        self._message_history.append(GPTMessage(role='user', content=most_recent_user_message))

        chat_result = await self._call_gpt()
        return self._create_partial_and_complete_lists(chat_result)

    async def _call_gpt(self) -> list[dict]:
        if not all([self._guild_id, self._thread_id, self._user_id, self._engine]):
            duck_logger.error("Missing required parameters for AI client call.")
            return []

        response = await self._ai_client.get_completion(
            self._guild_id,
            self._parent_channel_id,
            self._thread_id,
            self._user_id,
            self._engine,
            self._message_history,
            tools=[]
        )

        try:
            response = json.loads(response[0], strict=False)
        except:
            pass

        return response
