from asyncio import Queue
from dataclasses import dataclass
from typing import NotRequired, Optional, Union

from openai.types.responses import ResponseFunctionToolCallParam
from openai.types.responses.response_input_item import FunctionCallOutput
from typing_extensions import TypedDict

from pydantic import BaseModel

CHANNEL_ID = int
DUCK_WEIGHT = float
DUCK_NAME = str


class FileData(TypedDict):
    filename: str
    bytes: bytes



class AgentMessage(BaseModel):
    agent_name: str
    content: Optional[str] = None
    file: Optional[FileData] = None

class GPTMessage(BaseModel):
    role: str
    content: str

HistoryType = Union[GPTMessage, FunctionCallOutput, ResponseFunctionToolCallParam]

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
    description: str
    handoffs: NotRequired[list[str]]
    prompt: NotRequired[str]
    prompt_files: NotRequired[list[str]]



class MultiAgentSettings(TypedDict):
    agents: list[SingleAgentSettings]
    starting_agent: str | None  # If not set, will use first agent listed in `gen_ai`


class AgentAsToolSettings(MultiAgentSettings):
    tool_name: str
    description: str


class AgentConversationSettings(MultiAgentSettings):
    introduction: str
    timeout: int
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
