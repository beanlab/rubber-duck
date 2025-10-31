import asyncio
from pathlib import Path
import json
import yaml

import markdowndata
from quest import step, queue

from ..gen_ai.gen_ai import Agent, AIClient
from ..utils.config_types import DuckContext, FeedbackSettings, Gradable
from ..utils.fetch_github_file import fetch_github_file
from ..utils.logger import duck_logger
from ..utils.protocols import Message

ASSIGNMENT_NAME: str
SECTION: str
RUBRIC_ITEM: str

class FeedbackWorkflow:
    def __init__(self,
                 name: str,
                 send_message,
                 settings: FeedbackSettings,
                 grader_agent: Agent,
                 interviewer_agent: Agent,
                 ai_client: AIClient,
                 read_url
                 ):
        self.name = name
        self._send_message = send_message
        self._settings = settings
        self._grader_agent = grader_agent
        self._interviewer_agent = interviewer_agent
        self._ai_client = ai_client
        self.read_url = read_url
        # fail early and get the rubrics / sections

        self._assignments_rubrics: dict[ASSIGNMENT_NAME: dict[SECTION: any]] = {}
        self._populate_assignments_rubrics()

    async def __call__(self, context: DuckContext):
        thread_id = context.thread_id

        while True:
            project_name, sections = await self._get_project_and_sections(thread_id, context)
            report_contents = await self.get_report_contents(thread_id, context)

            if report_contents is None:
                return

            for section in sections:
                await self._send_message(thread_id, f"## {section}")
                rubric_for_section = self._assignments_rubrics[project_name][section]
                report_section = await self.get_report_section(report_contents, section)

                feedback = await self.get_feedback(context, report_section, rubric_for_section)
                await self._send_message(thread_id, feedback)

            await self._send_message(thread_id, f"Please rate your experience 1-10. Do you agree with the AI's grading? \n"
                                                f"If not, indicate why. Provide any other additional feedback.\n"
                                                f"TAs will look over your feedback to "
                                                f"make this grading experience better and more consistent.")
            student_feedback = await self._wait_for_message(context.timeout)

            duck_logger.info(f"Student feedback: {student_feedback}")

            await self._send_message(thread_id, "Thank you for your feedback! :thumbsup: @<role-mention> please review the feedback.")

            await self._send_message(thread_id, "Would you like to regrade your report? (Y/N)")

            repeat_loop: Message = await self._wait_for_message(context.timeout)
            if 'n' in repeat_loop["content"].lower():
                break

    def _get_instructions_content(self, assignment: Gradable):
        if 'instruction_link' in assignment:
            instructions = fetch_github_file(assignment['instruction_link'])
        elif 'instruction_path' in assignment:
            instructions = Path(assignment['instruction_path']).read_text(encoding="utf-8")
        else:
            raise ValueError(f"You must provide 'instruction_link' or 'instruction_path' for {assignment['name']}")
        return instructions

    def _get_rubric_sections(self, assignment: Gradable):
        instruction_content = self._get_instructions_content(assignment)
        instruction_content_as_mdd = markdowndata.loads(instruction_content)

        sections_rubrics = {}
        for section_name in assignment['sections']:
            rubric_section = self._find_key(instruction_content_as_mdd, section_name)
            if rubric_section is None:
                raise Exception(f"{rubric_section} does not exist in {assignment['name']}")
                # TODO consider creating an agent as a backup who can run through the report and try to find it
            sections_rubrics[section_name] = rubric_section['content']

        return sections_rubrics

    def _populate_assignments_rubrics(self):
        for assignment in self._settings["gradable_assignments"]:
            self._assignments_rubrics[assignment["name"]] = self._get_rubric_sections(assignment)

    def get_sections_for_project(self, project_name):
        for assignment in self._settings['gradable_assignments']:
            if assignment['name'] == project_name:
                return assignment['sections']
        raise Exception("Project not found")


    def _is_valid_project_name(self, project_name):
        return project_name in [assignment["name"] for assignment in self._settings['gradable_assignments']]

    def is_valid_section_name(self, project_name, section_name):
        general_sections = [
            section
            for general_req in self._settings['general_requirements']
            for section in general_req['sections']
        ]
        for assignment in self._settings['gradable_assignments']:
            if (assignment['name'] == project_name and (section_name in assignment['sections'] or
                                                        section_name in general_sections)):
                return True
        return False

    async def _get_project_and_sections(self, thread_id, context):
        # this should rely on the settings to make sure that we actually get a **valid section and project**
        # can decide to use an agent for this.
        await self._send_message(thread_id, "...")

        input = [
            (assignment["name"], assignment["sections"])
            for assignment in self._settings['gradable_assignments']
        ]
        response = await self._ai_client.run_agent(context, self._interviewer_agent, str(input))
        response = json.loads(response) # to dictionary (dict specified in prompt)
        project, sections = response["project_name"], response["sections"] # names/keys configured in the interviewer prompt

        if not self._is_valid_project_name(project):
            raise Exception(f"Invalid project name {project}")
        if not all(self.is_valid_section_name(project, section_name) for section_name in sections):
            raise Exception(f"Invalid section name(s): project: {project}, sections: {sections}")

        return project, sections

    async def get_report_contents(self, thread_id, context):
        try:
            await self._send_message(thread_id, "Please upload your md report: ")
            for i in range(3): # We will give them three tries to upload a md report
                response = await self._wait_for_message(context.timeout)

                if not response['files']:
                    await self._send_message(thread_id, "Please upload your md report: ")
                    continue

                file_contents = "\n".join([await self.read_url(attachment['url']) for attachment in response["files"]])
                return file_contents
            await self._send_message(thread_id, "Closing thread...") # TODO logic for not uploading a md report
            return None
        except Exception as e:
            duck_logger.info(f"Something failed: {e}")
            await self._send_message(thread_id, "Sorry...something didn't work quite right.")

    # TODO unduplicate function from registration workflow?
    async def _wait_for_message(self, timeout=300) -> Message | None:
        async with queue('messages', None) as messages:
            try:
                message: Message = await asyncio.wait_for(messages.get(), timeout)
                return message
            except asyncio.TimeoutError:  # Close the thread if the conversation has closed
                return None

    # async def get_feedback(self, context, report_section, rubric_for_section):
    #     input = {"report_contents": report_section,
    #              "rubric": rubric_for_section}
    #     result = await self._ai_client.run_agent(context, self._grader_agent, str(input))
    #     return result

    async def get_feedback(self, context, report_section, section_rubric):

        def grade(rubric_items, report_section):
            if rubric_items == []: return "refuse to grade on an empty list"
            return f"GRADED {rubric_items} on {report_section}"

        def grader_helper(rubric, report_piece):
            if isinstance(rubric, list):
                curr_feedback_items = []
                rubric_items = []
                for i in rubric:
                    if isinstance(i,dict):
                        feedback = grader_helper(i, report_piece)
                        curr_feedback_items.append(feedback)
                    else:
                        rubric_items.append(i)

                if isinstance(report_piece, dict) and "content" in report_piece:
                    report_piece = report_piece["content"]

                feedback = grade(rubric_items, report_piece)
                curr_feedback_items = [feedback] + curr_feedback_items
                return curr_feedback_items

            elif isinstance(rubric, dict):
                curr_feedback_items = {}
                for key, value in rubric.items():
                    if key not in report_piece:
                        raise Exception(f"{key} missing from report")
                    feedback = grader_helper(value, report_piece[key])
                    curr_feedback_items[key] = feedback
                return curr_feedback_items
            else:
                raise ("not a list or dict")

        all_feedback_as_dict = grader_helper(section_rubric, report_section)

        feedback_str = yaml.dump(all_feedback_as_dict, sort_keys=False)
        return feedback_str

    def _find_key(self, d, target):
        if target in d:
            return d[target]

        for k, v in d.items():
            if isinstance(v, dict):
                result = self._find_key(v, target)
                if result is not None:
                    return result
        return None

    async def get_report_section(self, report_contents: str, section):
        data = markdowndata.loads(report_contents)
        section_contents = self._find_key(data, section)

        if section_contents is None:
            raise "Exception: Unable to find section in report " + section
        return section_contents
