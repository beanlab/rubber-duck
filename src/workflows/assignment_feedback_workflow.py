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
        self._single_rubric_item_grader_agent_settings = single_rubric_item_grader
        self._project_scanner_agent_settings = project_scanner_agent
        self._ai_client = ai_client
        self.read_url = read_url

        self._assignments: dict[ASSIGNMENT_NAME: Gradable] = {
            assignment['name']: assignment
            for assignment in (self._settings)["gradable_assignments"]
        }

    async def __call__(self, context: DuckContext):
        try:
            # Send initial instructions
            await self._send_message(context.thread_id, self._settings['initial_instructions'])

            # Tell the user the supported assignments
            supported_assignment_names = list(self._assignments.keys()) # should the supported assignments be set on self when initializing?
            await self._send_message(context.thread_id,
                                     f"The supported assignments for grading are {supported_assignment_names}")

            # Query the report contents from the user
            # TODO ask read url is being used here. Do we need to pass that in? Do we care? We just care that the report contents are returned
            # pass in full context or just the thread id and timeout?
            # should read url be passed in?
            report_contents = await self._query_user_for_report(context)

            # Determine which project name is associated with the report
            # TODO ask: what should be passed here? Do we need to pass in agent settings? or is it okay it just relies on it within the function
            project_name = await self._extract_project_name_from_report(context, report_contents,
                                                                        supported_assignment_names)

            # Read the rubric contents associated with the project
            # TODO Error handling? in a function:  duck_logger.warn(f"Error loading the rubric file: {e}")
            # Best practices for opening files and paths?
            rubric_contents = Path(self._assignments[project_name].get("rubric_path")).read_text()

            # If present, send a project specific message to the user
            if project_message := self._assignments[project_name].get('message'):
                await self._send_message(context.thread_id, project_message)

            # TODO: check rubric and report formatting If not valid formatting? throw exception.... here or elsewhere??
            # early exit
            # if not valid_formatting(report_contents, rubric_contents):
            #     raise ConversationComplete("Error with formatting ")

            # grade the report
            # TODO ask: passing in functions here appropriate? Or just rely on them within the class? Is there a rule of thumb?
            graded_results = self.grade_assignment(report_contents,
                                                   rubric_contents,
                                                   self._grade_single_item,
                                                   self._format_graded_response)

            await self._send_message(context.thread_id, graded_results)

            # TODO ask: collect feedback from the user at the end? Did it work for the user?


        except ConversationComplete as e:
            await self._send_message(context.thread_id, str(e))
            return

    @step
    async def grade_assignment(self, context, report_contents, rubric_contents, grade_single_item, format_response) -> str:

        # break up the report into small pieces to grade with the associated rubric item
        flattened_report_and_rubric_items = flatten_report_and_rubric_items(report_contents, rubric_contents)

        tasks = [
            grade_single_item(context, piece_name, report_section, rubric_item)
            for piece_name, rubric_item, report_section in
            flattened_report_and_rubric_items
        ]

        flattened_graded_items: list[tuple[list[SECTION_NAME], RubricItemResponse]] = await asyncio.gather(*tasks)

        formatted_flattened_graded_items = [
            (name, format_response(result))
            for (name, result) in flattened_graded_items
        ]

        unflattened_formatted_graded_items = unflatten_dictionary(formatted_flattened_graded_items)

        md_formatted_graded_items = dict_to_md(unflattened_formatted_graded_items)

        return md_formatted_graded_items

    # TODO ask: should this stay on the class? My guess is yes
    def _format_graded_response(self, response: RubricItemResponse):
        emoji = ':white_check_mark:' if response['satisfactory'] else ':x:'
        justification = response['justification']
        return f'{emoji} **{response["rubric_item"]}** - {justification}'

    @step
    async def _get_project_name_using_agent(self, context, report_contents, valid_project_names):
        input = {
            'report_contents': report_contents,
            'valid_projects_names': valid_project_names
        }

        response = await self._ai_client.run_agent(context, self._project_scanner_agent_settings, str(input))
        response = json.loads(response)  # returns structured output as specified in the config
        project = response["project_name"]

        if project not in valid_project_names:
            raise ConversationComplete(
                f"The project report uploaded is not supported for grading.")

        return project

    # TODO ask: double steps? Does it matter? for extract and then use agent
    @step
    async def _extract_project_name_from_report(self, context, report_contents: str,
                                                valid_project_names: list[str]) -> str:
        if project_name := find_project_name_in_report_headers(report_contents, valid_project_names): # TODO better naming?
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
                file_contents = "\n".join([await self.read_url(attachment['url']) for attachment in md_attachments])
                return file_contents

            message = "No markdown files were uploaded. Please upload your markdown report: "

        raise ConversationComplete("No markdown files were uploaded")

    @step
    @task
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
        raw_response = await self._ai_client.run_agent(context, self._single_rubric_item_grader_agent_settings,
                                                       str(input))  # is the okay? Or should these be being passed in?
        result: RubricItemResponse = json.loads(raw_response)
        return piece_name, result

