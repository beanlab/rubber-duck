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

# Outcome

The application prompts for the Net ID, validates the Net ID format,
sends and verifies an email challenge with retry and resend support,
prompts for nickname selection, validates the nickname, and completes
the role-assignment flow for the registered user.

---

# Related Scenarios

- [Rejects invalid registration attempts](rejects_invalid_registration_attempts.md)
- [Reports registration permission failures](reports_registration_permission_failures.md)
