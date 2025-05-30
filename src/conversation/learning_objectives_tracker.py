from quest import wrap_steps
from pathlib import Path
import yaml
import json

from src.utils.config_types import LearningObjectiveSettings

from ..utils.gen_ai import GPTMessage
from ..utils.logger import duck_logger

class LearningObjective:
    def __init__(self, name: str, principles: list[str]):
        self.general_principle_name = name
        self.list_of_sub_principles = principles

class LearningObjectivesTracker:
    def __init__(self, ai_client):
        self._ai_client = ai_client
        wrap_steps(self._ai_client, ['get_completion'])

        self._guild_id = None
        self._thread_id = None
        self._user_id = None
        self._engine = None

    async def __call__(self, thread_id, initial_message, settings: LearningObjectiveSettings):
        self._learning_objectives = self._get_learning_objectives_from_file(settings['learning_objective_file_path'])

        self._current_objectives_complete = [False] * len(self._learning_objectives)
        self._current_objectives_partial = [False] * len(self._learning_objectives)
        self._thread_id = thread_id
        self._guild_id = initial_message['guild_id']
        self._parent_channel_id = initial_message['channel_id']
        self._user_id = initial_message['author_id']
        self._engine = initial_message.get('engine', 'gpt-4')  # Default to gpt-4 if not specified

        self._prompt = self._get_prompt(settings['prompt_file_path'])

        self._message_history = [
            GPTMessage(role='system', content=self._prompt),
            GPTMessage(role="system", content=str(self._learning_objectives))
        ]

        # we now need to analyze the code to see if we can extract any info

    def _get_learning_objectives_from_file(self, file_path: str):
        duck_logger.debug("Attempting to read learning objectives from file: %s", file_path)
        with open(file_path, 'r') as topics_file:
            topics_list = yaml.load(topics_file, Loader=yaml.SafeLoader)

        learning_objectives = []

        def helper(item):
            if isinstance(item, dict):
                # If the item has topic_name and topic_principles, create a Topic object
                if 'topic_name' in item and 'topic_principles' in item:
                    learning_objectives.append(Topic(item['topic_name'], item['topic_principles']))
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

        duck_logger.debug(f"Extracted learning objectives: {learning_objectives}")
        return learning_objectives

    def _get_prompt(self, prompt_file_path):
        return Path(prompt_file_path).read_text(encoding="utf-8")

    def _update_current_objectives_complete(self, chat_result):
        self._current_objectives_complete = [
            objective_already_complete or chat_response_objective.get('met', False)
            for objective_already_complete, chat_response_objective
            in zip(self._current_objectives_complete, chat_result)
        ]

    def _update_learning_objectives_partial(self, chat_result):
        self._current_objectives_partial = [
            objective_partial or chat_response_partial.get('mentioned', False)
            for objective_partial, chat_response_partial
            in zip(self._current_objectives_partial, chat_result)
        ]

    def all_objectives_complete(self):
        return all(self._current_objectives_complete)

    def _create_partial_and_complete_lists(self, chat_results: list[dict]):
        missing_objectives = [
            lo
            for lo, partial, bot_result in zip(self._learning_objectives, self._current_objectives_partial, chat_results)
            if not partial
        ]

        partial_objectives = [
            (lo, bot_result['reason'])
            for lo, is_complete, bot_result in zip(self._learning_objectives, self._current_objectives_complete, chat_results)
            if not is_complete
        ]

        missing_str = f"The following objectives are not mentioned: {((' - ' + obj) for obj in missing_objectives)}"
        partial_str = f"The following objectives are not fully understood: {((' - ' + objective + ' because ' + reason) for objective, reason in partial_objectives)}"

        return missing_str + '\n\n' + partial_str

    async def get_missing_objectives(self, most_recent_user_message: str) -> bool:
        self._message_history.append(GPTMessage(role='user', content=most_recent_user_message))

        chat_result = await self._call_gpt()

        self._update_current_objectives_complete(chat_result)
        self._update_learning_objectives_partial(chat_result)

        missing_objectives = [
            (lo + " because " + bot_result['reason'])
            for lo, bot_result in zip(self._learning_objectives, chat_result)
            if not bot_result['met']
        ]

        return "The following objectives are not met: \n" + "\n".join(missing_objectives)

    async def _call_gpt(self) -> list[dict]:
        if not all([self._guild_id, self._thread_id, self._user_id, self._engine]):
            duck_logger.debug("Missing required parameters for AI client call.")
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
