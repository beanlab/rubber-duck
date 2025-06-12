from dataclasses import dataclass
from typing import TypedDict

from ..utils.protocols import SendMessage

CHANNEL_ID = int
DUCK_WEIGHT = float


class AgentMessage(TypedDict):
    content: str
    file: bytes | None


class GPTMessage(TypedDict):
    role: str
    content: str

class FeedbackNotifierSettings(TypedDict):
    feedback_check_hour: int
    feedback_check_minute: int


class FeedbackConfig(TypedDict):
    ta_review_channel_id: int
    reviewer_role_id: int | None
    allow_self_feedback: bool | None
    feedback_timeout: int | None


class RolePattern(TypedDict):
    name: str
    pattern: str
    description: str


class RolesSettings(TypedDict):
    patterns: list[RolePattern]


class RegistrationSettings(TypedDict):
    cache_timeout: int
    authenticated_user_role_name: str
    roles: RolesSettings
    sender_email: str


class SingleAgentSettings(TypedDict):
    prompt_file: str
    engine: str
    name: str
    handoff_prompt: str
    tools: list[str]
    handoffs: list[str]


class MultiAgentSettings(TypedDict):
    starting_agent: str
    individual_agent_settings: list[SingleAgentSettings]


class AgentConversationSettings(TypedDict):
    introduction: str
    agent_type: str
    agent_settings: SingleAgentSettings | MultiAgentSettings
    timeout: int


@dataclass
class DuckContext:
    guild_id: int
    channel_id: int
    author_id: int
    author_mention: str
    content: str
    message_id: int
    thread_id: int
    send_message: SendMessage


class DuckConfig(TypedDict):
    name: str
    "The channel name is not used in the code. It provides a description of the duck."
    workflow_type: str
    weight: int
    settings: dict


class ChannelConfig(TypedDict):
    channel_id: int
    channel_name: str
    "The channel name is not used in the code. It is used to indicate the name of Discord channel."
    ducks: list[DuckConfig]


class ServerConfig(TypedDict):
    server_name: str
    "The channel name is not used in the code. It is used to indicate the name of the server."
    channels: list[ChannelConfig]


class SQLConfig(TypedDict):
    db_type: str
    username: str
    password: str
    host: str
    port: str
    database: str


class RetryProtocol(TypedDict):
    max_retries: int
    delay: int
    backoff: int


class AdminSettings(TypedDict):
    admin_channel_id: int
    admin_role_id: int


class ReporterConfig(TypedDict):
    gpt_pricing: dict[str, list]


class Config(TypedDict):
    sql: SQLConfig
    servers: dict[str, ServerConfig]
    admin_settings: AdminSettings
    dataset_folder_locations: list[str]
    ai_completion_retry_protocol: RetryProtocol
    default_duck_settings: dict[str, dict]
    feedback_notifier_settings: FeedbackNotifierSettings
    reporter_settings: ReporterConfig
