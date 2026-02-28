from dataclasses import dataclass
from typing import NotRequired, Literal, Union

from openai.types.responses import ResponseInputItemParam
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


HistoryType = ResponseInputItemParam


class FeedbackNotifierSettings(TypedDict):
    feedback_check_hour: int
    feedback_check_minute: int


class FeedbackConfig(TypedDict):
    ta_review_channel_id: int
    reviewer_role_id: int | None
    allow_self_feedback: bool | None
    feedback_timeout: int | None


class RolePattern(TypedDict):
    pattern: str
    description: str


class RolesSettings(TypedDict):
    patterns: dict[str, RolePattern]


class RegistrationSettings(TypedDict):
    cache_timeout: int
    authenticated_user_role_name: str
    email_domain: str
    # This is the domain used for email verification. For example, 'byu.edu'.
    roles: RolesSettings
    sender_email: str
    max_retries: NotRequired[int]
    registration_bot: NotRequired[str]
    ta_channel_id: int


class SingleAgentSettings(TypedDict):
    name: str
    engine: str
    tools: list[str]
    prompt: NotRequired[str]
    prompt_files: NotRequired[list[str]]
    tool_required: NotRequired[str]
    output_format: NotRequired[dict]
    reasoning: NotRequired[str]


class Gradable(TypedDict):
    rubric_path: list[str]
    message: NotRequired[str]


class AssignmentFeedbackSettings(TypedDict):
    initial_instructions: str
    gradable_assignments: dict[str, Gradable]
    single_rubric_item_grader: SingleAgentSettings
    project_scanner_agent: SingleAgentSettings


class RubricItemResponse(TypedDict):
    rubric_item: str
    justification: str
    satisfactory: bool


class AgentAsToolSettings(TypedDict):
    doc_string: str
    agent: SingleAgentSettings


class MultiAgentSettings(TypedDict):
    agent: SingleAgentSettings
    agents_as_tools: dict[str, AgentAsToolSettings]


class AgentConversationSettings(TypedDict):
    agent: SingleAgentSettings
    introduction: NotRequired[str]
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
    duck_type: str  # validated in build_ducks
    settings: dict  # could specify further


class ChannelConfig(TypedDict):
    channel_id: int
    duck: DUCK_NAME | DuckConfig
    timeout: int
    channel_name: NotRequired[str]


class ServerConfig(TypedDict):
    server_id: int
    channels: dict[str, ChannelConfig]


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
    # This is the log level for the admin channel. It can be 'DEBUG', 'INFO', 'WARNING', 'ERROR', or 'CRITICAL'.


class ReporterConfig(TypedDict):
    gpt_pricing: dict[str, list[float]]


class ResourceConfig(TypedDict):
    source: str
    target: str


class ContainerSettings(TypedDict, total=False):
    timeout: int
    working_dir: str
    network_mode: str
    memory: str
    memory_swap: str
    cpus: int
    pids_limit: int
    read_only_root: bool


class ContainerConfig(TypedDict):
    image: str
    resources: list[ResourceConfig]
    settings: ContainerSettings


class ContainerTool(TypedDict):
    type: Literal["container_exec"]
    container: str
    description: NotRequired[str]


ToolConfig = ContainerTool


class Config(TypedDict):
    sql: SQLConfig
    containers: dict[str, ContainerConfig]
    tools: dict[str, ToolConfig]
    ducks: dict[DUCK_NAME, DuckConfig]
    agents_as_tools: dict[str, AgentAsToolSettings]
    servers: dict[str, ServerConfig]
    admin_settings: AdminSettings
    ai_completion_retry_protocol: RetryProtocol
    feedback_notifier_settings: NotRequired[FeedbackNotifierSettings]
    reporter_settings: ReporterConfig
    sender_email: str
