from time import monotonic

from ..utils import load_logging
from ..utils.protocols import CreateThread, SendMessage


class SetupPrivateThread:
    def __init__(self, create_thread: CreateThread, send_message: SendMessage):
        self._create_thread = create_thread
        self._send_message = send_message

    async def __call__(self, parent_channel_id: int, author_mention: str, title: str) -> int:
        setup_started = monotonic()
        thread_id = await load_logging.timed(
            "thread_create",
            self._create_thread(parent_channel_id, title[:20]),
            result_field="thread",
            channel=parent_channel_id,
        )

        await load_logging.timed(
            "thread_welcome",
            self._send_message(thread_id, f'{author_mention}'),
            thread=thread_id,
        )

        await load_logging.timed(
            "thread_link",
            self._send_message(
                parent_channel_id,
                f"{author_mention} Click here to join the conversation: <#{thread_id}>",
            ),
            channel=parent_channel_id,
            thread=thread_id,
        )
        load_logging.thread_setup_complete(
            parent_channel_id,
            thread_id,
            setup_started,
        )

        return thread_id
