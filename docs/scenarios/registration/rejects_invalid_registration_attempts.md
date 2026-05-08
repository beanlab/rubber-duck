# Rejects Invalid Registration Attempts

## Purpose

Guard registration flow.

---

# Context

A configured registration workflow is running in a Discord conversation
thread.

---

# Action

The user times out, repeatedly submits invalid verification tokens, or
otherwise fails registration validation.

---

# Interaction

| Action | Outcome |
| --- | --- |
| The user remains inactive until the configured timeout is reached. | The application closes the conversation with timeout messaging. |
| The user repeatedly submits invalid verification tokens. | The application terminates the registration attempt. |
| The user otherwise fails registration validation. | The failed registration does not complete the nickname and role-assignment flow. |

---

# Outcome

Invalid registration attempts end without applying registered-user
nickname or role changes.

---

# Related Scenarios

- [Completes email-verified registration](completes_email_verified_registration.md)
- [Reports registration permission failures](reports_registration_permission_failures.md)
- [Closes conversation after completion](../conversations/closes_conversation_after_completion.md)
