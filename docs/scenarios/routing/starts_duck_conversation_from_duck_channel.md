# Starts Duck Conversation From Duck Channel

## Purpose

Create conversation threads.

---

# Context

The bot is running and a Discord channel is configured to start a named
global duck or inline duck definition.

---

# Action

A non-bot user posts a routable message in the configured duck channel.

---

# Outcome

The bot starts a new duck conversation in a private thread. The user is
mentioned in the new thread, and the parent channel receives a join-link
message mentioning the user.

If the original message contains `duck`, the application adds a 🦆
reaction to the original message.

---

# Related Scenarios

- [Standard Duck supports student learning](../conversations/standard_duck_supports_student_learning.md)
- [Stats Duck provides statistical outputs](../conversations/stats_duck_provides_statistical_outputs.md)
- [Completes email-verified registration](../registration/completes_email_verified_registration.md)
- [Grades markdown report upload](../assignment_feedback/grades_markdown_report_upload.md)
