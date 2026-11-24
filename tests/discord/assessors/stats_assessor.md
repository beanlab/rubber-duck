You are assessing whether a statistics rubber duck fulfilled the behavioral requirements of its own prompt.

Use the tester conversation prompt as a blueprint for the requests and conditions that should occur, but assess the duck's behavior, not whether the tester followed the script perfectly. Inspect the complete conversation history and determine whether the duck provided the requested information and analysis.

A passing conversation must demonstrate the following:

{{assessor}}
- When the tester asks what datasets are available, the duck provides dataset information rather than a generic refusal or unrelated response.
{{/assessor}}

{{assessor}}
- When the tester selects an available dataset and asks for its first 10 lines, the duck provides information from that selected dataset and addresses the requested row display.
{{/assessor}}

{{assessor}}
- When the tester asks for a chi-square test of association between variables from the selected dataset, the duck performs or invokes the appropriate data/statistics behavior and provides the resulting information. It is not sufficient to merely explain what a chi-square test is or ignore the requested analysis.
{{/assessor}}

{{assessor}}
- When the tester sends exactly `quit`, the duck concludes the conversation.
{{/assessor}}

{{assessor}}
- After the conversation has been concluded, the duck does not continue the analysis workflow or reopen the conversation in response to a brief thank-you.
{{/assessor}}

## Output Contract

Set `status` to exactly one of these values:
- `pass`: the required duck behavior is demonstrated in the conversation history.
- `fail`: the required duck behavior is missing, incorrect, or cannot be established from the history.

Return only JSON matching this output schema exactly:

{{output_contract}}
