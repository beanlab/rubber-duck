# Reports Registration Permission Failures

## Purpose

Notify registration operators.

---

# Context

A registration workflow has validated the user and is attempting to
apply the configured nickname or role changes in Discord.

---

# Action

Discord permission issues prevent nickname or role assignment.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Discord prevents nickname assignment. | The application notifies the configured TA channel about the permission issue and terminates the registration flow. |
| Discord prevents role assignment. | The application notifies the configured TA channel about the permission issue and terminates the registration flow. |

---

# Outcome

The application notifies the configured TA channel about the permission
issue and terminates the registration flow.

---

# Related Scenarios

- [Completes email-verified registration](completes_email_verified_registration.md)
- [Rejects invalid registration attempts](rejects_invalid_registration_attempts.md)
