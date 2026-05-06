This design doc is intended for the files related to the code-duck workflow. We will be changing the duck to have the following functionality:

The bot is the student and the user is the TA.

The conversation revolves around a complete program (learner level) pulled from a yaml rubric similar to the one currently being used. That said, all the issues with the code should be stack traceback errors related to the concept being reviewed.

Per turn, the whole conversation in a single string is passed to a conversation review agent that assesses the conversation and evaluates what question the student should ask next. Another agent packages this question and relevant code to the user (it should not make additions of its own)

You will need to edit variables.yaml to contain proper code, documented errors, and exact strings of the traceback errors. To do this, run the script with the various errors and capture the output associated with each individual error to document them in the yaml rubric. This will get passed along with the agent prompt to the conversation-review agent. The agent that packages the question and code will be the code-duck user facing agent. You may modify those prompts to fit project structure.

If anything is incomplete about this plan, ask me for additional details.