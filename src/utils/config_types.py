from dataclasses import dataclass
from typing import NotRequired, Union, Any, Literal

from openai.types.responses import ResponseFunctionToolCallParam
from openai.types.responses.response_input_item import FunctionCallOutput
from typing_extensions import TypedDict

CHANNEL_ID = int
DUCK_WEIGHT = float
DUCK_NAME = str


class FileData(TypedDict):
    filename: str
    bytes: bytes


class AgentMessage(TypedDict):
    content: NotRequired[str]
    file: NotRequired[FileData]
    agent_name: str


class GPTMessage(TypedDict):
    role: str
    content: str

class ReasoningItem(TypedDict):
    type: Literal["reasoning"]
    id: NotRequired[str]
    summary: NotRequired[list]


HistoryType = Union[GPTMessage, FunctionCallOutput, ResponseFunctionToolCallParam, ReasoningItem]


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
    email_domain: str
    "This is the domain used for email verification. For example, 'byu.edu'."
    roles: RolesSettings
    sender_email: str


class SingleAgentSettings(TypedDict):
    name: str
    engine: str
    tools: list[str]
    prompt: NotRequired[str]
    prompt_files: NotRequired[list[str]]
    tool_required: NotRequired[str]
    output_format: NotRequired[dict]
    reasoning: NotRequired[str]


class AgentAsToolSettings(TypedDict):
    tool_name: str
    doc_string: str
    agent: SingleAgentSettings


class MultiAgentSettings(TypedDict):
    agent: SingleAgentSettings
    agents_as_tools: list[AgentAsToolSettings]


class AgentConversationSettings(MultiAgentSettings):
    introduction: str
    file_size_limit: int
    file_type_ext: list[str]


@dataclass
class DuckContext:
    guild_id: int
    parent_channel_id: int
    author_id: int
    author_mention: str
    content: str
    message_id: int
    thread_id: int
    timeout: int


class DuckConfig(TypedDict):
    name: str
    "The channel name is not used in the code. It provides a description of the duck."
    duck_type: str  # Supported options found in main.py::build_ducks
    settings: dict


class WeightedDuck(TypedDict):
    weight: int
    duck: DUCK_NAME | DuckConfig


class ChannelConfig(TypedDict):
    channel_id: int
    channel_name: str
    "The channel name is not used in the code. It is used to indicate the name of Discord channel."
    ducks: list[DUCK_NAME | DuckConfig | WeightedDuck]
    "Either the name of the duck"
    timeout: int


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
    log_level: str
    "This is the log level for the admin channel. It can be 'DEBUG', 'INFO', 'WARNING', 'ERROR', or 'CRITICAL'."


class ReporterConfig(TypedDict):
    gpt_pricing: dict[str, list]


class Config(TypedDict):
    sql: SQLConfig
    ducks: list[DuckConfig]
    agents_as_tools: list[AgentAsToolSettings]
    servers: dict[str, ServerConfig]
    admin_settings: AdminSettings
    dataset_folder_locations: list[str]
    ai_completion_retry_protocol: RetryProtocol
    feedback_notifier_settings: FeedbackNotifierSettings
    reporter_settings: ReporterConfig
    sender_email: str
