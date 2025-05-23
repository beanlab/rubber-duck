from quest import wrap_steps
from pathlib import Path
import yaml

from ..utils.gen_ai import GPTMessage


class LearningObjectivesTracker:
    def __init__(self, ai_client):
        self._ai_client = ai_client
        wrap_steps(self._ai_client, ['get_completion'])

        self.guild_id = None
        self.thread_id = None
        self.user_id = None
        self.engine = None

        self._learning_objectives = None
        self._current_objective_complete = None
        self._prompt = self._get_prompt()

    def __call__(self, learning_objectives: list[dict], guild_id: int, thread_id, user_id, engine):
        self._learning_objectives = learning_objectives
        self._current_objective_complete = [False] * len(learning_objectives)
        self.guild_id = guild_id
        self.thread_id = thread_id
        self.user_id = user_id
        self.engine = engine

    def parse_yaml_objectives(self, yaml_file_path: str) -> list[dict]:
        """
        Parse a YAML file containing learning objectives into a list of dictionaries.
        Each dictionary contains the question and its answer.
        
        Returns:
            List of dictionaries, each containing:
            {
                'question': str,  # The learning objective question
                'answer': str,    # The correct answer
                'section': str    # The section the question belongs to
            }
        """
        try:
            with open(yaml_file_path, 'r', encoding='utf-8') as file:
                yaml_content = yaml.safe_load(file)
                
            objectives_list = []
            
            # Handle the list structure of the YAML
            if isinstance(yaml_content, list):
                for section in yaml_content:
                    if isinstance(section, dict):
                        for section_name, questions in section.items():
                            if isinstance(questions, list):
                                for question in questions:
                                    if isinstance(question, dict):
                                        for q, a in question.items():
                                            if q.startswith('Question:'):
                                                question_text = q.replace('Question:', '').strip()
                                                answer_text = a.replace('Answer:', '').strip()
                                                objectives_list.append({
                                                    'question': question_text,
                                                    'answer': answer_text,
                                                    'section': section_name
                                                })
            
            return objectives_list
            
        except Exception as e:
            print(f"Error parsing YAML file: {e}")
            return []

    def _get_prompt(self):
        return Path("prompts/learning_objectives_prompt.txt").read_text(encoding="utf-8")

    async def check_objectives_complete(self, most_recent_user_message: str) -> bool:
        if not self._learning_objectives:
            return False
            
        chat_result = await self._call_gpt(most_recent_user_message)
        
        if not isinstance(chat_result, list):
            return False

        self._current_objective_complete = [
            objective_already_complete or chat_response_objective.get('met', False) 
            for objective_already_complete, chat_response_objective 
            in zip(self._current_objective_complete, chat_result)
        ]
        return all(self._current_objective_complete)

    async def _call_gpt(self, message: str) -> list[dict]:
        if not all([self.guild_id, self.thread_id, self.user_id, self.engine]):
            return []

        response = await self._ai_client.get_completion(
            self.guild_id,
            GPTMessage(role='user', content=self._prompt),
            self.thread_id,
            self.user_id,
            self.engine,
            GPTMessage(role='user', content=message),
            tools=None
        )

        return response
