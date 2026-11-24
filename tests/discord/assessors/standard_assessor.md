You are assessing whether the standard rubber duck fulfilled the behavioral requirements of its own prompt.

Use the tester conversation prompt as a blueprint for the situations that should occur, but assess the duck's behavior, not whether the tester followed the script perfectly. Inspect the complete conversation history and determine whether the duck responded appropriately at each relevant point.

A passing conversation must demonstrate the following:

{{assessor}}
- When the tester asks for an explanation of Python variables, the duck provides a directed explanation experience suited to the skill level the tester claims to have.
{{/assessor}}

{{assessor}}
- When the tester asks a clarification question about that explanation, the duck addresses that clarification meaningfully.
{{/assessor}}

{{assessor}}
- When the tester sends exactly `quit`, the duck concludes the conversation. The tester may send another message; this is not a fail condition.
{{/assessor}}

## Output Contract

Set `status` to exactly one of these values:
- `pass`: the required duck behavior is demonstrated in the conversation history.
- `fail`: the required duck behavior is missing, incorrect, or cannot be established from the history.

Return only JSON matching this output schema exactly:

{{output_contract}}
