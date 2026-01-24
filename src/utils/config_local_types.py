from typing import TypedDict

DUCK_NAME = str
CHANNEL_ID = int
SERVER_ID = int


class IncludeContainers(TypedDict, total=False):
    name: str


class IncludeDucks(TypedDict, total=False):
    name: str


class IncludeTools(TypedDict, total=False):
    name: str


class IncludeAgentsAsTools(TypedDict, total=False):
    tool_name: str


IncludeServers = int


class IncludeConfig(TypedDict, total=False):
    include_all: bool
    include_these: list[str]
    containers: list[IncludeContainers]
    ducks: list[IncludeDucks]
    tools: list[IncludeTools]
    agents_as_tools: list[IncludeAgentsAsTools]
    servers: list[IncludeServers]


class OverrideSQL(TypedDict, total=False):
    database: str
    username: str
    password: str
    host: str
    port: str


class OverrideContainer(TypedDict, total=False):
    name: str
    image: str
    mounts: list[dict]
    settings: dict


class OverrideDuck(TypedDict, total=False):
    name: DUCK_NAME
    duck_type: str
    settings: dict


class OverrideTool(TypedDict, total=False):
    name: str
    type: str
    container: str
    description: str


class OverrideAgentAsTool(TypedDict, total=False):
    tool_name: str
    doc_string: str
    agent: dict


class OverrideChannel(TypedDict, total=False):
    channel_id: CHANNEL_ID
    channel_name: str
    timeout: int
    ducks: list[DUCK_NAME]


class OverrideServer(TypedDict, total=False):
    server_name: str
    channels: list[OverrideChannel]


class OverrideAdminSettings(TypedDict, total=False):
    admin_channel_id: int
    admin_role_id: int
    log_level: str


class OverrideConfig(TypedDict, total=False):
    sql: OverrideSQL
    containers: list[OverrideContainer]
    ducks: list[OverrideDuck]
    tools: list[OverrideTool]
    agents_as_tools: list[OverrideAgentAsTool]
    servers: dict[SERVER_ID, OverrideServer]
    admin_settings: OverrideAdminSettings


class LocalConfig(TypedDict, total=False):
    include: IncludeConfig
    override: OverrideConfig
