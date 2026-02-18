from typing import Callable

from .registration import Registration, RegistrationInfo
from ..utils.config_types import DuckContext

def describe_registration_progress(info: RegistrationInfo) -> str:
    completed = []
    pending = []

    # Net ID
    if not info.net_id:
        pending.append("Net ID has not been provided.")
    elif not info.net_id_checked:
        pending.append(f"Net ID '{info.net_id}' is pending validation.")
    else:
        completed.append(f"Net ID '{info.net_id}' is verified.")
    # Email
    if info.email_verified:
        completed.append("Email address is verified.")
    else:
        pending.append("Email address has not been verified.")
    # Nickname
    if info.nickname:
        if info.nickname_reason:
            completed.append(
                f"Nickname '{info.nickname}' is set ({info.nickname_reason})."
            )
        else:
            completed.append(f"Nickname '{info.nickname}' is set.")
    else:
        if info.nickname_reason:
            pending.append(f"Nickname has not been set ({info.nickname_reason}).")
        else:
            pending.append("Nickname has not been chosen.")
    # Roles
    if info.roles_assigned:
        completed.append(
            "Roles assigned: " + info.roles_assigned
        )
    else:
        pending.append("No roles have been assigned yet.")
    # Summary
    lines = []

    if completed:
        lines.append("Completed steps:")
        lines.extend(f"- {item}" for item in completed)

    if pending:
        lines.append("\nRemaining steps:")
        lines.extend(f"- {item}" for item in pending)
    else:
        lines.append("\nRegistration is complete.")

    return "\n".join(lines)

class RegistrationWorkflow:
    def __init__(self,
                 name: str,
                 registration: Registration,
                 registration_bot: Callable | None,
                 send_message
                 ):
        self.name = name
        self._registration = registration
        self._registration_bot = registration_bot
        self._send_message = send_message

    async def __call__(self, context: DuckContext):
        info = await self._registration.run(context)
        if info and self._registration_bot is not None:
            user_query = describe_registration_progress(info)
            await self._registration_bot(context, f"Please finish the registration process for this user: {user_query}")



