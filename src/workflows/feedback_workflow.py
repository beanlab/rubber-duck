import asyncio
from pathlib import Path
import json

import markdowndata
from quest import step, queue

from ..gen_ai.gen_ai import Agent, AIClient
from ..utils.config_types import DuckContext, FeedbackSettings
from ..utils.fetch_github_file import fetch_github_file
from ..utils.logger import duck_logger
from ..utils.protocols import Message

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

    async def __call__(self, context: DuckContext):
        thread_id = context.thread_id

        project_name, sections = await self.get_project_and_sections(thread_id, context)
        report_contents = await self.get_report_contents(thread_id, context)

        all_sections_for_project = self.get_sections_for_project(project_name)
        project_rubric = await self.get_project_rubric(project_name, all_sections_for_project)

        for section in sections:
            await self._send_message(thread_id, f"## {section}")
            rubric_for_section = self.get_rubric_for_section(project_rubric, section)
            report_section = await self.get_report_section(report_contents, section)

            feedback = await self.get_feedback(context, report_section, rubric_for_section)
            await self._send_message(thread_id, feedback)

        await self._send_message(thread_id, "That is all. :thumbsup:")


    def get_sections_for_project(self, project_name):
        for assignment in self._settings['gradable_assignments']:
            if assignment['name'] == project_name:
                return assignment['sections']
        raise Exception("Project not found")


    def is_valid_project_name(self, project_name):
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

    async def get_project_and_sections(self, thread_id, context):
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

        if not self.is_valid_project_name(project):
            raise Exception(f"Invalid project name {project}")
        if not all(self.is_valid_section_name(project, section_name) for section_name in sections):
            raise Exception(f"Invalid section name(s): project: {project}, sections: {sections}")

        return project, sections

    async def get_report_contents(self, thread_id, context):
        try:
            await self._send_message(thread_id, "Please upload your md report: ")
            response = await self._wait_for_message(context.timeout)
            file_contents = "\n".join([await self.read_url(attachment['url']) for attachment in response["files"]])
            return file_contents
        except Exception as e:
            duck_logger.info(f"Something failed: {e}")
            await self._send_message(thread_id, "Something didn't work quite right.")

    # TODO unduplicate
    async def _wait_for_message(self, timeout=300) -> Message | None:
        async with queue('messages', None) as messages:
            try:
                message: Message = await asyncio.wait_for(messages.get(), timeout)
                return message
            except asyncio.TimeoutError:  # Close the thread if the conversation has closed
                return None

    async def get_feedback(self, context, report_section, rubric_for_section):
        input = {"report_contents": report_section,
                 "rubric": rubric_for_section}
        result = await self._ai_client.run_agent(context, self._grader_agent, str(input))
        return result

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

    def get_rubric_for_section(self, project_rubric: str, section):
        data = markdowndata.loads(project_rubric)
        rubric_contents = self._find_key(data, section)

        if rubric_contents is None:
            raise "Exception: Unable to find section in report " + section
        return rubric_contents

    async def get_project_rubric(self, project_name, all_sections):
        # rely on the settings to get rubric contents for the project
        for gradable in self._settings["gradable_assignments"] + self._settings["general_requirements"]:
            if gradable["name"] == project_name:
                if 'instruction_link' in gradable:
                    instructions = fetch_github_file(gradable['instruction_link'])
                    return self.instructions_to_rubric(instructions, all_sections)
                elif 'instruction_path' in gradable:
                    return Path(gradable['instruction_path']).read_text(encoding="utf-8")
                else:
                    raise ValueError(f"You must provide 'instruction_link' or 'instruction_path' for {project_name} ")
        raise f"Exception: unable to find project {project_name}"


    def instructions_to_rubric(self, instructions, all_sections):
        # Parse the instructions to get just the rubric
        outlines = []
        for line in instructions.splitlines():
            is_target_header = line.startswith("## ") and any(
                key in line for key in all_sections
            )
            is_check_item = line.strip().startswith("- [ ]")

            if is_target_header and outlines:
                outlines.append("```")

            if is_target_header or is_check_item:
                outlines.append(line)

            if is_target_header:
                outlines.append("```")

        outlines.append("```")
        return "\n".join(outlines)
