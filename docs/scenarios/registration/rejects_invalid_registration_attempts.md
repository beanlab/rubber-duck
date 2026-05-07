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

# Outcome

Timeout closes the conversation with timeout messaging. Repeated invalid
verification tokens terminate the registration attempt. The failed
registration does not complete the nickname and role-assignment flow.

---

# Related Scenarios

- [Completes email-verified registration](completes_email_verified_registration.md)
- [Reports registration permission failures](reports_registration_permission_failures.md)
- [Closes conversation after completion](../conversations/closes_conversation_after_completion.md)
