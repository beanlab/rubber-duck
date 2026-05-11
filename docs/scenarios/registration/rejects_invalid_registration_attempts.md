# Rejects Invalid Registration Attempts

## Purpose

Guard registration flow.

---

# Context

A registration conversation is active in a Discord thread.

---

# Action

The user times out, repeatedly submits invalid verification tokens, or
otherwise fails registration validation.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Configured timeout reached | Closes the conversation with timeout messaging. |
| Repeated invalid verification tokens | Terminates the registration attempt. |
| Other registration validation failure | Does not complete the nickname and role-assignment flow. |

---

# Outcome

Invalid registration attempts end without applying registered-user
nickname or role changes.

---

# Related Scenarios

- [Completes email-verified registration](completes_email_verified_registration.md)
- [Reports registration permission failures](reports_registration_permission_failures.md)
- [Closes conversation after completion](../conversations/closes_conversation_after_completion.md)
