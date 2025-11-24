import asyncio
import json
from pathlib import Path

from quest import step, task

from .parsing_utils import is_filled_in_report, flatten_report_and_rubric_items, unflatten_dictionary, dict_to_md, \
    find_project_name_in_report_headers
from ..gen_ai.gen_ai import Agent, AIClient
from ..utils.config_types import DuckContext, AssignmentFeedbackSettings, Gradable, RubricItemResponse
from ..utils.message_utils import wait_for_message
from ..utils.protocols import ConversationComplete

ASSIGNMENT_NAME = str
SECTION_NAME = str
RUBRIC_ITEM = str


class AssignmentFeedbackWorkflow:
    def __init__(self,
                 name: str,
                 send_message,
                 settings: AssignmentFeedbackSettings,
                 single_rubric_item_grader: Agent,
                 project_scanner_agent: Agent,
                 ai_client: AIClient,
                 read_url
                 ):
        self.name = name
        self._send_message = step(send_message)
        self._settings = settings
        self._single_rubric_item_grader_agent = single_rubric_item_grader
        self._project_scanner_agent = project_scanner_agent
        self._ai_client = ai_client
        self._read_url = read_url

        self._assignments: dict[ASSIGNMENT_NAME: Gradable] = {
            assignment['name']: assignment
            for assignment in (self._settings)["gradable_assignments"]
        }

    async def __call__(self, context: DuckContext):
        try:
            await self._send_message(context.thread_id, self._settings['initial_instructions'])

            await self._send_message(context.thread_id,
                                     f"The supported assignments for grading are {' '.join(self._assignments)}")

            report_contents = await self._query_user_for_report(context)

            project_name = await self._extract_project_name_from_report(context, report_contents)

            rubric_contents = await self._load_rubric(project_name)

            if assignment_message := self._assignments[project_name].get('message'):
                await self._send_message(context.thread_id, assignment_message)

            graded_results = await self._grade_assignment(context,
                                                          report_contents,
                                                          rubric_contents)

            await self._send_message(context.thread_id, graded_results)

            # TODO ask: collect feedback from the user at the end? Did it work for the user?
        except ConversationComplete as e:
            await self._send_message(context.thread_id, str(e))
            return

    async def _load_rubric(self, project_name):
        return Path(self._assignments[project_name].get("rubric_path")).read_text()

    @step
    async def _grade_assignment(self, context, report_contents, rubric_contents) -> str:
        try:
            flattened_report_and_rubric_items = flatten_report_and_rubric_items(report_contents, rubric_contents)
        except Exception as e:
            raise ConversationComplete(e)

        tasks = [
            self._grade_single_item(context, piece_name, report_section, rubric_item)
            for piece_name, rubric_item, report_section in
            flattened_report_and_rubric_items
        ]

        flattened_graded_items: list[tuple[list[SECTION_NAME], RubricItemResponse]] = await asyncio.gather(*tasks)

        formatted_flattened_graded_items = [
            (name, self._format_graded_response(result))
            for (name, result) in flattened_graded_items
        ]

        unflattened_formatted_graded_items = unflatten_dictionary(formatted_flattened_graded_items)

        md_formatted_graded_items = dict_to_md(unflattened_formatted_graded_items)

        return md_formatted_graded_items

    def _format_graded_response(self, response: RubricItemResponse):
        emoji = ':white_check_mark:' if response['satisfactory'] else ':x:'
        return f'{emoji} **{response["rubric_item"]}** - {response["justification"]}'

    @step
    async def _get_project_name_using_agent(self, context, report_contents, valid_project_names):
        input = {
            'report_contents': report_contents,
            'valid_projects_names': valid_project_names
        }

        response = await self._ai_client.run_agent(context, self._project_scanner_agent, str(input))
        response = json.loads(response)  # returns structured output as specified in the config
        project = response["project_name"]

        if project not in valid_project_names:
            raise ConversationComplete(
                f"{project} is not supported for grading.\n"  # TODO modify prompt for grabbing the project name 
                f"Supported projects are {' '.join(self._assignments)}")

        return project

    @step
    async def _extract_project_name_from_report(self, context, report_contents: str) -> str:
        valid_project_names = list(self._assignments.keys())
        if project_name := find_project_name_in_report_headers(report_contents, valid_project_names):
            return project_name
        else:
            return await self._get_project_name_using_agent(context, report_contents, valid_project_names)

    @step
    async def _query_user_for_report(self, context):
        message = "Please upload your markdown report."

        for _ in range(3):
            await self._send_message(context.thread_id, message)
            response = await wait_for_message(context.timeout)

            if response is None:
                raise ConversationComplete("This conversation has timed out.")

            attachments = response.get("files", [])
            md_attachments = [attachment for attachment in attachments if "md" in attachment["filename"]]

            if md_attachments:
                file_contents = "\n".join([await self._read_url(attachment['url']) for attachment in md_attachments])
                return file_contents

            message = "No markdown files were uploaded. Please upload your markdown report: "

        raise ConversationComplete("No markdown files were uploaded")

    @task
    @step
    async def _grade_single_item(self, context, piece_name, report_section, rubric_item) -> tuple[
        list[SECTION_NAME], RubricItemResponse]:

        if not is_filled_in_report(report_section):
            return piece_name, RubricItemResponse(
                rubric_item=rubric_item,
                justification="Report section is not filled in.",
                satisfactory=False
            )

        input = {"report_contents": report_section,
                 "rubric_item": rubric_item}
        raw_response = await self._ai_client.run_agent(context, self._single_rubric_item_grader_agent, str(input))
        result: RubricItemResponse = json.loads(raw_response)
        return piece_name, result
