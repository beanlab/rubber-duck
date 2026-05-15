# Ends Conversation Threads

## Purpose

Close finished conversations.

---

# Context

A duck conversation is active inside its private Discord thread.

---

# Action

The conversation ends normally, reaches a handled timeout condition, or
cannot continue because of an unexpected failure.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Conversation completes normally. | Sends `*This conversation has been closed.*` in the thread. |
| Conversation reaches a handled timeout condition. | Sends timeout or completion messaging and then sends `*This conversation has been closed.*`. |
| Unexpected failure prevents the conversation from continuing. | Sends an error-code message and then sends `*This conversation has been closed.*`. |

---

# Outcome

Ended duck conversations close visibly in the Discord thread. Completed
duck conversations that are eligible for review are available for later
feedback processing.
