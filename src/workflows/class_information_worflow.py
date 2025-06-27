import asyncio
import io

import aiohttp
import docx
import PyPDF2

from quest import step, queue

from ..armory.rag import MultiClassRAGDatabase
from ..utils.config_types import ClassInformationSettings, DuckContext
from ..utils.protocols import Message


class ClassInformationWorkflow:
    def __init__(self,
                 name: str,
                 database: MultiClassRAGDatabase,
                 send_message,
                 settings: ClassInformationSettings
                 ):

        self._name = name
        self._send_message = step(send_message)
        self._settings = settings
        self._database = database
        self._file_size_limit = settings.get('file_size_limit', 10 * 1024 * 1024)
        self._file_type_ext = ['txt', 'md', 'pdf', 'docx']

    async def __call__(self, context: DuckContext):
        thread_id = context.thread_id
        await self._send_message(context.thread_id, "In this conversation, you will provide information about your class. You can send documents of type [.txt, .md, .pdf, .docx]")
        while(True):
            await self._send_message(thread_id, "Please select a category for the class information you want to provide. "
                                                 "You can choose from the following categories:")
            if not self._settings['class_categories']:
                await self._send_message(thread_id, "No categories are configured. Please contact an administrator.")
                return
            # Create a dictionary to map category numbers to category names and send a message with the options

            cat_dict = {}
            cat_string = ""
            for i, cat in enumerate(self._settings['class_categories']):
                cat_dict[str(i + 1)] = cat
                cat_string += f"{i + 1}. {cat}\n"
            cat_string += f"{len(self._settings['class_categories']) + 1}. Exit\n"
            await self._send_message(thread_id, cat_string)

            # Wait for the user to select a category or exit
            async with queue('messages', None) as messages:
                cat_num: Message = await asyncio.wait_for(messages.get(), timeout=300)

            if cat_num['content'] == str(len(self._settings['class_categories']) + 1):
                break

            category = cat_dict.get(cat_num['content'], None)

            # If the category is not valid, send an error message and ask again
            if category is None:
                await self._send_message(thread_id, "Invalid category selected. Please try again.")
                continue

            else:
                while True:
                    await self._send_message(thread_id,
                                             f"Please add relative documents and URLs to the **{category}** category.")
                    errors = await self._wait_for_message(category, thread_id)
                    if errors:
                        await self._send_message(thread_id, errors)
                    else:
                        break

        await self._send_message(thread_id, "Thank you for providing the information. The class information has been updated.")


    async def _wait_for_message(self, category: str, thread_id: int, timeout=300) -> str | None:
        async with queue('messages', None) as messages:
            try:
                errors = []
                message: Message = await asyncio.wait_for(messages.get(), timeout)
                if message['content']:
                    self._send_message(thread_id, "What should the Title be for the written content?")
                    message2: Message = await asyncio.wait_for(messages.get(), timeout)
                    if message2['content']:
                        self._database.add_document(str(self._settings['target_channel_id']), category, message2['content'], message['content'])

                if message['files']:
                    async with aiohttp.ClientSession() as session:
                        for attachment in message['files']:
                            if attachment['size'] > self._file_size_limit:
                                errors.append(
                                    f"File {attachment['filename']} is too large. "
                                    f"Please upload a file smaller than {self._file_size_limit / 1024 / 1024:.2f} MB."
                                )
                                continue

                            if attachment['filename'].split('.')[-1] not in self._file_type_ext:
                                errors.append(
                                    f"File {attachment['filename']} is not an allowed type. "
                                    f"Allowed types are: {', '.join(self._file_type_ext)}."
                                )
                                continue

                            try:
                                file_content = await self._read_url(attachment['url'],
                                                                    attachment['filename'].split('.')[-1], session)
                                self._database.add_document(str(self._settings['target_channel_id']), category, attachment['filename'], file_content)

                            except ValueError as e:
                                errors.append(f"Error reading file {attachment['filename']}: {e}")

                    if errors:
                        return "\n".join(errors)
                return None

            except asyncio.TimeoutError:
                return "Conversation timed out. Please try again."

    async def _read_url(self, url: str, suffix: str, session: aiohttp.ClientSession) -> str:

        suffix = suffix.lower()

        try:
            async with session.get(url) as response:
                    if response.status != 200:
                        raise ValueError(f"Failed to fetch file. Status code: {response.status}")
                    file_bytes = await response.read()

            if suffix in ["txt", "md"]:
                return file_bytes.decode("utf-8")

            elif suffix == "pdf":
                reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text.strip()

            elif suffix == "docx":
                document = docx.Document(io.BytesIO(file_bytes))
                return "\n".join([para.text for para in document.paragraphs])

            else:
                raise ValueError(f"Unsupported file type: {suffix}")

        except Exception as e:
            raise ValueError(f"Error reading file: {e}")