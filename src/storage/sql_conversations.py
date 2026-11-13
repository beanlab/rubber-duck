from sqlalchemy import BigInteger, Column, Integer, UniqueConstraint, select
from sqlalchemy.orm import Session, declarative_base

from ..conversation.conversations import ConversationThread


ConversationBase = declarative_base()


class ConversationThreadModel(ConversationBase):
    __tablename__ = "discord_conversation_threads"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "user_id",
            "entry_channel_id",
            name="uq_discord_conversation_owner",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger)
    user_id = Column(BigInteger)
    entry_channel_id = Column(BigInteger)
    thread_id = Column(BigInteger, unique=True)


def _conversation_thread(model):
    return ConversationThread(
        guild_id=model.guild_id,
        user_id=model.user_id,
        entry_channel_id=model.entry_channel_id,
        thread_id=model.thread_id,
    )


class SQLConversationStore:
    def __init__(self, session: Session):
        ConversationBase.metadata.create_all(session.connection())
        self._session = session

    def get(
            self,
            guild_id: int,
            user_id: int,
            entry_channel_id: int,
    ) -> ConversationThread | None:
        model = self._session.scalar(
            select(ConversationThreadModel).where(
                ConversationThreadModel.guild_id == guild_id,
                ConversationThreadModel.user_id == user_id,
                ConversationThreadModel.entry_channel_id == entry_channel_id,
            )
        )
        return _conversation_thread(model) if model is not None else None

    def get_by_thread(self, thread_id: int) -> ConversationThread | None:
        model = self._session.scalar(
            select(ConversationThreadModel).where(ConversationThreadModel.thread_id == thread_id)
        )
        return _conversation_thread(model) if model is not None else None

    def add(self, conversation: ConversationThread) -> None:
        try:
            self._session.add(ConversationThreadModel(
                guild_id=conversation.guild_id,
                user_id=conversation.user_id,
                entry_channel_id=conversation.entry_channel_id,
                thread_id=conversation.thread_id,
            ))
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
