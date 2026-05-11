# Registration Verifies And Registers Users

## Purpose

Register verified users.

---

# Context

A user has started a registration conversation thread.

---

# Action

The user attempts to complete registration by providing a Net ID,
completing email verification, and selecting a nickname.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Conversation starts. | Prompts for the user's Net ID. |
| Valid Net ID. | Validates the Net ID format and sends an email challenge. |
| Email verification succeeds. | Accepts the verified email challenge, including configured retry and resend support. |
| Valid nickname selection. | Validates the nickname. |
| Discord account changes permitted. | Completes the configured nickname and role-assignment flow for the registered user. |
| Configured timeout reached. | Closes the conversation with timeout messaging. |
| Repeated invalid verification tokens. | Ends the registration attempt without applying registered-user nickname or role changes. |
| Other registration validation failure. | Does not complete the nickname and role-assignment flow. |
| Nickname assignment blocked. | Notifies the configured TA channel about the permission issue and ends registration. |
| Role assignment blocked. | Notifies the configured TA channel about the permission issue and ends registration. |

---

# Outcome

Verified registration completes only after Net ID validation, email
verification, nickname validation, and configured Discord account
changes succeed. Failed registration attempts end without applying
registered-user nickname or role changes.

---

# Related Scenarios

- [Ends conversation threads](../conversations/ends_conversation_threads.md)
