import base64
import re

import requests
from botbuilder.core import BotFrameworkAdapter, MessageFactory, TurnContext
from botbuilder.schema import Activity, ActivityTypes, Attachment as BotAttachment, ConversationReference

from ..utils.config_types import FileData, PlatformId
from ..utils.logger import duck_logger
from ..utils.protocols import Context, Message


def _strip_mentions(text: str) -> str:
    """Remove Teams @mention tags: <at>Name</at>"""
    return re.sub(r'<at>[^<]*</at>', '', text).strip()


def _as_message(activity: Activity) -> Message:
    channel_data = activity.channel_data or {}
    team_id = ''
    if isinstance(channel_data, dict):
        team_info = channel_data.get('team')
        if isinstance(team_info, dict):
            team_id = team_info.get('id', '')

    return Message(
        guild_id=team_id,
        channel_name='',
        channel_id=activity.conversation.id,
        author_id=activity.from_property.id,
        author_name=activity.from_property.name,
        author_mention=activity.from_property.name,
        message_id=activity.id,
        content=_strip_mentions(activity.text or ''),
        files=[],
    )


class _NoOpContext:
    async def __aenter__(self) -> '_NoOpContext':
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class TeamsBot:
    def __init__(self, adapter: BotFrameworkAdapter, app_id: str) -> None:
        self._adapter = adapter
        self._app_id = app_id
        self._rubber_duck = None
        self._admin_channel: PlatformId | None = None
        self._conversation_references: dict[str, ConversationReference] = {}

    def set_duck_app(self, rubber_duck, admin_channel_id: PlatformId) -> None:
        self._rubber_duck = rubber_duck
        self._admin_channel = admin_channel_id

    def _register_conversation(
        self, conversation_id: str, reference: ConversationReference
    ) -> None:
        self._conversation_references[conversation_id] = reference

    async def on_turn(self, turn_context: TurnContext) -> None:
        try:
            activity = turn_context.activity
            duck_logger.info(
                'on_turn entered: activity_type=%s conversation_id=%s',
                activity.type,
                activity.conversation.id if activity.conversation else None,
            )

            if self._rubber_duck is None:
                return

            # Store conversation reference so proactive messages can be sent later.
            reference = TurnContext.get_conversation_reference(activity)
            self._register_conversation(str(activity.conversation.id), reference)

            if activity.type != ActivityTypes.message:
                duck_logger.info('on_turn filtered: activity_type=%s is not a message', activity.type)
                return
            duck_logger.info('on_turn passed activity type check: activity_type=%s', activity.type)

            # Ignore messages that are empty after mention stripping (e.g. bare @mentions).
            cleaned = _strip_mentions(activity.text or '')
            duck_logger.info('on_turn after mention stripping: cleaned content=%r', cleaned)
            if not cleaned:
                duck_logger.info('on_turn filtered: empty content after mention stripping')
                return

            # Ignore messages that start with // (same convention as Discord adapter).
            if (activity.text or '').lstrip().startswith('//'):
                duck_logger.info('on_turn filtered: message starts with //')
                return

            duck_logger.info('on_turn routing message to rubber duck')
            await self._rubber_duck.route_message(_as_message(activity))
        except Exception:
            duck_logger.exception('on_turn unhandled exception')

    async def send_message(
        self,
        channel_id: PlatformId,
        message: str = None,
        file: FileData = None,
    ) -> str:
        conversation_id = str(channel_id)
        reference = self._conversation_references.get(conversation_id)
        if reference is None:
            raise ValueError(f'No conversation reference for channel {channel_id}')

        result_id: str | None = None

        async def _callback(tc: TurnContext) -> None:
            nonlocal result_id
            if message:
                response = await tc.send_activity(MessageFactory.text(message))
                result_id = response.id
            elif file is not None:
                # Teams does not support inline binary attachments in all contexts;
                # base64-encoded content works for small files in personal/group chats.
                # For large files or channel tabs, use the Teams Files API instead.
                attachment = BotAttachment(
                    name=file['filename'],
                    content_type='application/octet-stream',
                    content=base64.b64encode(file['bytes']).decode(),
                )
                response = await tc.send_activity(MessageFactory.attachment(attachment))
                result_id = response.id
            else:
                raise ValueError('Must send message or file')

        await self._adapter.continue_conversation(reference, _callback, self._app_id)
        return result_id

    async def edit_message(
        self,
        channel_id: PlatformId,
        message_id: PlatformId,
        new_content: str,
    ) -> None:
        conversation_id = str(channel_id)
        reference = self._conversation_references.get(conversation_id)
        if reference is None:
            duck_logger.error(f'No conversation reference for channel {channel_id}')
            return

        async def _callback(tc: TurnContext) -> None:
            updated = Activity(id=str(message_id), type='message', text=new_content)
            await tc.update_activity(updated)

        try:
            await self._adapter.continue_conversation(reference, _callback, self._app_id)
        except Exception as e:
            duck_logger.error(
                f'Could not edit message {message_id} in channel {channel_id}: {e}'
            )

    async def add_reaction(
        self,
        channel_id: PlatformId,
        message_id: PlatformId,
        reaction: str,
    ) -> None:
        pass  # no-op: Bot Framework has no emoji reaction API for Teams

    def typing(self, channel_id: PlatformId) -> Context:
        # Teams typing indicators require an Activity send per turn, not a persistent
        # context manager.  A no-op satisfies the protocol without side effects.
        return _NoOpContext()

    async def create_thread(
        self, parent_channel_id: PlatformId, title: str
    ) -> PlatformId:
        # Teams conversations are implicit reply chains; there is no separate thread
        # channel with a distinct ID.  We return the parent conversation ID so that
        # all subsequent sends and workflow routing use the same channel identifier.
        # rubber_duck_app.route_message checks has_workflow before duck channels, so
        # follow-up messages are routed to the active workflow rather than starting
        # a new one.
        return parent_channel_id

    async def read_url(self, url: str) -> str:
        # Teams attachment URLs require a Bearer token issued by the Bot Framework
        # token service.  We attempt an unauthenticated GET first (works for public
        # URLs), then retry with a token on 401.  Authenticated retries require that
        # the adapter's credentials object exposes get_access_token(); if not available
        # in the installed SDK version, the 401 error is re-raised with a clear message.
        try:
            response = requests.get(url)
            if response.status_code != 401:
                response.raise_for_status()
                return response.text

            # Authenticated retry for Teams CDN attachment URLs.
            credentials = getattr(self._adapter, '_credentials', None)
            if credentials is None:
                raise PermissionError(
                    f'URL {url} returned 401 and adapter credentials are not accessible'
                )
            token = await credentials.get_access_token()
            response = requests.get(url, headers={'Authorization': f'Bearer {token}'})
            response.raise_for_status()
            return response.text
        except Exception:
            duck_logger.exception(f'Error reading URL {url}')
            raise
