# Completes Email-Verified Registration

## Purpose

Register verified users.

---

# Context

A configured duck has `duck_type` set to `registration`, and a user has
started a new registration conversation thread.

---

# Action

The user provides a valid Net ID, completes the email verification
challenge, selects a valid nickname, and the application has permission
to apply the configured Discord nickname and role changes.

---

# Interaction

| Action | Outcome |
| --- | --- |
| The registration workflow starts. | The application prompts for the user's Net ID. |
| The user provides a valid Net ID. | The application validates the Net ID format and sends an email challenge. |
| The user completes the email verification challenge. | The application accepts the verified email challenge, including configured retry and resend support. |
| The application prompts for nickname selection and the user selects a valid nickname. | The application validates the nickname. |
| The application has permission to apply Discord account changes. | The application completes the configured nickname and role-assignment flow for the registered user. |

---

# Outcome

Verified registration completes only after Net ID validation, email
verification, nickname validation, and configured Discord account
changes succeed.

---

# Related Scenarios

- [Rejects invalid registration attempts](rejects_invalid_registration_attempts.md)
- [Reports registration permission failures](reports_registration_permission_failures.md)
