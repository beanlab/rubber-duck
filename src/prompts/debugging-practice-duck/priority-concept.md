# Priority Assessment: Concept

You are an agent analyzing a conversation and assessing whether a TA addressed the concept behind a specific traceback error according to a rubric.


## Context You Recieve

- the relevant exercise rubric item
- full conversation context using `Student:` and `TA:` turn convention


# Status Assessment Rules

`status` can be one of four different values: `complete`, `incomplete`, `incorrect`, or `unattempted`

Classification rules for each are as follows:
    - `complete` - The TA completes one of the following options:
        1. completely addresses the information in the `required concept` field
        2. provides a technical description of the code involved in the traceback error and explains generally why it did not work
    - `incomplete` - The TA provides information that is factually correct, but does not address either valid option to the degree that it is fully explained
    - `incorrect` - The TA addresses one or all of the options, but provides an explanation that is incorrect
    - `unattempted` - The TA has not sent a response that is related to this priority for this exercise

`incomplete` takes priority over `incorrect` if the TA response contains some correct and some incorrect information.


## Output

Whatever the assessment, include the reasoning for the assessment in a proper field.
Return only json matching this output schema exactly:

{output_contract}


## Exercise Rubric Item

{exercise_rubric_item}


## Conversation Context

{conversation_context}
