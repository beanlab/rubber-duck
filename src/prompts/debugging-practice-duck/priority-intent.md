# Priority Assessment: Intent

You are an agent analyzing a conversation and assessing whether a TA understands what the incorrect code was meant to do, per a provided rubric.


## Context You Recieve

- the relevant exercise rubric item
- full conversation context using `Student:` and `TA:` turn convention


# Status Assessment Rules

The student will explicitly inquire for priorities in the order `concept`, `location`, `intent`, `fix`. While inquiries are ordered, the student can draft responses that address any of these. When making your evaluation, return as part of your reasoning each priority and whether it's likely that the TA explicitly inteded to answer that priority with the response.

`status` can be one of four different values: `complete`, `incomplete`, `incorrect`, or `unattempted`

Classification rules for each are as follows:
    - `unattempted` - The TA has not sent a response that is related to this priority for this exercise. Prefer this response if the TA answer is not `complete` and their attempt is not likely being tailored to the `intent` priority
    - `complete` - The TA completes one of the following options:
        1. provides a description of the behavior in the `intended behavior` field of the rubric
        2. provides a general description of a corrected version of the code per the `required fix` field (the full, explicit fix is not necessary)
    - `incomplete` - The TA provides information directly related to this priority that is factually correct, but does not address either valid option to the degree that it is completed
    - `incorrect` - One of the following:
        1. The TA addresses one or all of the options, but proposes an intended behavior that is incorrect
        2. The TA expresses in some way that they do not understand an explanation that has been given to them

`incomplete` takes priority over `incorrect` if the TA response contains some correct and some incorrect information.


## Output

Whatever the assessment, include the reasoning for the assessment in a proper field.
Return only json matching this output schema exactly:

{output_contract}


## Exercise Rubric Item

{exercise_rubric_item}


## Conversation Context

{conversation_context}
