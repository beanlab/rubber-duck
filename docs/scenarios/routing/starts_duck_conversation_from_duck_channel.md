# Starts Duck Conversation From Duck Channel

## Purpose

Create workflow threads.

---

# Context

The bot is running and a Discord channel is configured to start a named
global duck or inline duck definition.

---

# Action

A non-bot user posts a routable message in the configured duck channel.

---

# Outcome

The application starts a new duck workflow in a private thread. The
thread name is derived from the first 20 characters of the triggering
message. The user is mentioned in the new thread, and the parent channel
receives a join-link message mentioning the user.

If the original message contains `duck`, the application adds a 🦆
reaction to the original message.

---

# Related Scenarios

- [Runs agent-led conversation](../conversations/runs_agent_led_conversation.md)
- [Runs user-led conversation](../conversations/runs_user_led_conversation.md)
- [Completes email-verified registration](../registration/completes_email_verified_registration.md)
- [Grades markdown report upload](../assignment_feedback/grades_markdown_report_upload.md)
