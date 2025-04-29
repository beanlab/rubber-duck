from typing import TypedDict


class FeedbackConfig(TypedDict):
    ta_review_channel_id: int
    reviewer_role_id: int | None
    allow_self_feedback: bool | None
    feedback_timeout: int | None


class DuckSettings(TypedDict):
    prompt_file: str
    engine: str
    weight: int
    timeout: int


class DuckConfig(TypedDict):
    name: str
    workflow_type: str
    duck_settings_config: DuckSettings


class ChannelsConfig:
    channel_id: int
    channel_name: str
    feedback_config: FeedbackConfig
    duck_config: DuckConfig


class ServerConfig(TypedDict):
    server_name: str
    channels_config: list[ChannelsConfig]


class MultiServerConfig(TypedDict):
    servers: list[ServerConfig]


class DefaultConfig(TypedDict):
    engine: str | None
    timeout: int | None 