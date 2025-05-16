from typing import TypedDict

class CourseConfig(TypedDict):
    name: str
    "The name is not used in the code. It helps us identify what the settings are for a course."
    api_token: str
    "The API token is from the env file"
    role_ids: dict[str, str]
    "role ids and a section name and id"

class CanvasConfig(TypedDict):
    course_ids: dict[str,CourseConfig]
    sender_email: str
    # TODO: Ask Dr. Bean to make a rubberduck@byu.edu email for us to verify with AWS SES
    global_role_id: str
    # Student


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
    "The channel name is not used in the code. It provides a description of the duck."
    workflow_type: str
    weight: int
    settings: dict


class ChannelConfig(TypedDict):
    channel_id: int
    channel_name: str
    canvas_course_id: int | None
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


class Config(TypedDict):
    sql: SQLConfig
    reporting: dict[str, str]
    servers: dict[str, ServerConfig]
    admin_settings: AdminSettings
    ai_completion_retry_protocol: RetryProtocol
    default_duck_settings: dict[str, dict]
