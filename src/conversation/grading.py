import asyncio
from pathlib import Path

from quest import wrap_steps, step, queue

from src.bot.discord_bot import read_text_from_discord_url
from src.conversation.conversation import BasicSetupConversation
from src.utils.gen_ai import RetryableGenAI, RecordMessage, RecordUsage
from src.utils.protocols import SendMessage, ReportError, Message


class GradingWorkflow:
    def __init__(self,
                 ai_client: RetryableGenAI,
                 record_message: RecordMessage,
                 record_usage: RecordUsage,
                 send_message: SendMessage,
                 report_error: ReportError,
                 setup_conversation: BasicSetupConversation,
                 ):
        self._ai_client = wrap_steps(ai_client, ['get_completion'])

        self._record_message = step(record_message)
        self._record_usage = step(record_usage)

        self._send_message = step(send_message)
        self._report_error = step(report_error)

        self._setup_conversation = step(setup_conversation)

    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):

        prompt_file = settings["prompt_file"]
        if prompt_file:
            prompt = Path(prompt_file).read_text(encoding="utf-8")
        else:
            prompt = initial_message['content']

        rubric = settings["rubric"]
        engine = settings["engine"]
        timeout = settings["timeout"]

        introduction = settings.get("introduction",
                                    "Hi, I will help you grade this assignment, please provide a report.md and a code.py file to be graded.")

        message_history = await self._setup_conversation(thread_id, prompt, initial_message)
        message_history.append({
            'role': 'system',
            'content': f"The following rubric: {rubric} will be used to grade the assignment."
        })
        await self._send_message(thread_id, introduction)

        while True:
            try:
                async with queue('messages', None) as messages:
                    message: Message = await asyncio.wait_for(messages.get(), timeout=90)
                    message_files = message['file']

                if message_files is None:
                    await self._send_message(thread_id,
                                             "No files were provided. Please attach the necessary files to be graded.")
                    continue

                if len(message_files) != 2:
                    await self._send_message(thread_id,
                                             "Please provide exactly two files: a report (.md/.pdf) and a code file (.py).")
                    continue

                report_file = next((f for f in message_files if f['filename'].endswith(('.md', '.pdf'))), None)
                code_file = next((f for f in message_files if f['filename'].endswith('.py')), None)

                if not report_file or not code_file:
                    await self._send_message(thread_id, "One or both files are missing or not of the correct type.")
                    continue

                await self._send_message(thread_id,
                                         "Thank you for providing the files. You will receive feedback shortly.")

                report_file_text = await read_text_from_discord_url(report_file['file_url'])
                code_file_text = await read_text_from_discord_url(code_file['file_url'])

                if report_file_text is None:
                    await self._send_message(thread_id, f"Report file `{report_file['filename']}` could not be read.")
                    continue
                if code_file_text is None:
                    await self._send_message(thread_id, f"Code file `{code_file['filename']}` could not be read.")
                    continue

                message_content = f"Report:\n{report_file_text}\n\nCode:\n{code_file_text}"

                # Here you can continue your workflow Rebecca


            except asyncio.TimeoutError:
                await self._send_message(thread_id, "No response received within 90 seconds.")













            except asyncio.TimeoutError:
                message_content = '-'
                await self._send_message(thread_id, "No feedback provided, skipping.")
