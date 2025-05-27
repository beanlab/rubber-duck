from quest import wrap_steps
from pathlib import Path
import yaml
import json

from ..utils.gen_ai import GPTMessage
from ..utils.logger import duck_logger


class LearningObjectivesTracker:
    def __init__(self, ai_client):
        self._ai_client = ai_client
        wrap_steps(self._ai_client, ['get_completion'])

        self.guild_id = None
        self.thread_id = None
        self.user_id = None
        self.engine = None

    def __call__(self, guild_id: int, thread_id, parent_channel_id, user_id, engine, learning_objective_file_path, prompt_file_path):
        self._learning_objectives = self._get_learning_objectives_from_file(learning_objective_file_path)

        self._current_objectives_complete = [False] * len(self._learning_objectives)
        self._current_objectives_partial = [False] * len(self._learning_objectives)
        self.guild_id = guild_id
        self.thread_id = thread_id
        self.parent_channel_id = parent_channel_id
        self.user_id = user_id
        self.engine = engine

        self._prompt = self._get_prompt(prompt_file_path)
        self._message_history = [
            GPTMessage(role="assistant", content=str(self._learning_objectives)),
            GPTMessage(role='system', content=self._prompt)
        ]


    def _get_learning_objectives_from_file(self, file_path: str):
        # assumes any title/non Learning objective line will have a * in front of it

        # path = Path(file_path)
                # .read_text(encoding="utf-8"))
        # with open(Path("prompts/project_3_network_routing/learning_objects_pq2.yaml"), 'r') as rubric_file:
        #     objectives_dict = yaml.load(rubric_file, Loader=yaml.SafeLoader)
        duck_logger.debug("Attempting to read learning objectives from file: %s", file_path)
        with open(file_path, 'r') as rubric_file:
            objectives_dict = yaml.load(rubric_file, Loader=yaml.SafeLoader)

        learning_objectives = []

        def helper(dict):
            for key, value in dict.items():
                if key.startswith("Objective"):
                    learning_objectives.append(value)
                else:
                    for item in value:
                        helper(item)

        helper(objectives_dict[0])
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
        # return self._create_partial_and_complete_lists(chat_result)

    async def _call_gpt(self) -> list[dict]:
        if not all([self.guild_id, self.thread_id, self.user_id, self.engine]):
            return []

        response = await self._ai_client.get_completion(
            self.guild_id,
            self.parent_channel_id,
            self.thread_id,
            self.user_id,
            self.engine,
            self._message_history,
            tools=[]
        )

        try:
            response = json.loads(response[0], strict=False)
        except:
            pass

        return response
