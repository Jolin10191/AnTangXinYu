"""会话层：把消息分成一段一段，供侧边栏列表和上下文隔离使用。

约定：
- 每段对话只带自己的消息给模型，换会话就换上下文；
- 陪伴记忆仍然按人算（跨会话），否则开一段新对话等于让患者重新自我介绍；
- 主动关怀落在单独的 kind='care' 会话里，不和患者自己开的对话混在一起。
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from antang_api.models import Conversation

CONVERSATION_TITLE_CHARS = 24
CARE_CONVERSATION_TITLE = "关怀消息"
NEW_CONVERSATION_TITLE = "新对话"


def conversation_title(content: str) -> str:
    """用第一条用户消息当标题，不额外花一次模型调用。"""

    text = " ".join(content.split())
    if not text:
        return NEW_CONVERSATION_TITLE
    return text[:CONVERSATION_TITLE_CHARS]


async def latest_chat_conversation(
    session: AsyncSession, user_id: UUID
) -> Conversation | None:
    return await session.scalar(
        select(Conversation)
        .where(Conversation.user_id == user_id, Conversation.kind == "chat")
        .order_by(Conversation.created_at.desc(), Conversation.id.desc())
        .limit(1)
    )


async def create_chat_conversation(
    session: AsyncSession, user_id: UUID, *, title: str = NEW_CONVERSATION_TITLE
) -> Conversation:
    conversation = Conversation(user_id=user_id, kind="chat", title=title)
    session.add(conversation)
    await session.flush()
    return conversation


async def ensure_chat_conversation(
    session: AsyncSession, user_id: UUID
) -> Conversation:
    """没有会话时建一段，供老客户端（不传 conversation_id）继续用。"""

    conversation = await latest_chat_conversation(session, user_id)
    if conversation is not None:
        return conversation
    return await create_chat_conversation(session, user_id)


async def owned_conversation(
    session: AsyncSession, *, user_id: UUID, conversation_id: UUID
) -> Conversation | None:
    return await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )


async def care_conversation(session: AsyncSession, user_id: UUID) -> Conversation:
    """主动关怀单独一段，没有就建。"""

    conversation = await session.scalar(
        select(Conversation)
        .where(Conversation.user_id == user_id, Conversation.kind == "care")
        .order_by(Conversation.created_at.desc(), Conversation.id.desc())
        .limit(1)
    )
    if conversation is not None:
        return conversation
    conversation = Conversation(
        user_id=user_id, kind="care", title=CARE_CONVERSATION_TITLE
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def list_conversations(
    session: AsyncSession, user_id: UUID, *, limit: int = 50
) -> list[Conversation]:
    """只列患者自己开的对话，按最近消息排序；没有消息的会话排在最后。

    主动关怀那段（kind='care'）不进这个列表：它和患者主动发起的对话混在一起读起来很怪。
    """

    return list(
        await session.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.kind == "chat")
            .order_by(
                Conversation.last_message_at.desc().nulls_last(),
                Conversation.created_at.desc(),
            )
            .limit(limit)
        )
    )


async def touch_conversation(
    session: AsyncSession,
    conversation: Conversation,
    *,
    at: datetime | None = None,
) -> None:
    conversation.last_message_at = at or datetime.now(UTC)
