# Conversation Scenarios

Conversation scenarios describe behavior inside private Discord threads
created for duck workflows.

The shared conversation context is:

- a routable Discord message has started a duck workflow thread
- subsequent thread messages may be forwarded to the active workflow
- workflow output is sent back to Discord in the thread
- completed or failed workflows close the conversation visibly

## Scenarios

- [Runs agent-led conversation](runs_agent_led_conversation.md)
- [Runs user-led conversation](runs_user_led_conversation.md)
- [Closes conversation after completion](closes_conversation_after_completion.md)
- [Reports workflow failure to thread](reports_workflow_failure_to_thread.md)
