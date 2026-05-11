# Reports Registration Permission Failures

## Purpose

Notify registration operators.

---

# Context

A registration conversation has validated the user and is attempting to
apply the configured nickname or role changes in Discord.

---

# Action

Discord permission issues prevent nickname or role assignment.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Nickname assignment blocked | Notifies the configured TA channel about the permission issue and ends registration. |
| Role assignment blocked | Notifies the configured TA channel about the permission issue and ends registration. |

---

# Outcome

The application notifies the configured TA channel about the permission
issue and ends registration.

---

# Related Scenarios

- [Completes email-verified registration](completes_email_verified_registration.md)
- [Rejects invalid registration attempts](rejects_invalid_registration_attempts.md)
