from typing import TypedDict


class FeedbackConfig(TypedDict):
    ta_review_channel_id: int
    reviewer_role_id: int | None
    allow_self_feedback: bool | None
    feedback_timeout: int | None


class DuckWorkflowSettings(TypedDict):
    prompt_file: str
    engine: str
    timeout: int


class DuckConfig(TypedDict):
    name: str
    "The name will not affect the code and is only used to distinguish between different rubber ducks."
    workflow_type: str
    weight: int
    settings: dict


class ChannelConfig:
    channel_id: int
    channel_name: str
    "The channel name will not affect the code and is only used to know what the name of the Discord channel we are using is."
    feedback_config: FeedbackConfig
    duck_config: DuckConfig


class ServerConfig(TypedDict):
    server_name: str
    "The server name will not affect the code and is only used to distinguish between different servers."
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


class Config(TypedDict):
    sql: SQLConfig
    reporting: dict[str, str]
    servers: dict[str, ServerConfig]
    admin_settings: AdminSettings
    ai_completion_retry_protocol: RetryProtocol
    default_duck_settings: dict[str, dict]

