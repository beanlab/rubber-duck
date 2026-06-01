The following document outlines a rewrite/refactor of the debugging duck workflow

# Architectural Changes
The evaluation step is now a parallelized 5 agent run of the priority agents. All but the priority-unrelated agent return json with the following schema:

json
```
"reasoning": <reasoning for evaluation>,
"status": <output status>
```

priority-unrelated should return the following json shape:

json
```
"reasoning": <reasoning for evaluation>,
"unrelated": <output unrelated assessment (True or False)>
```

Complete type and schema enforcement for any agent in this workflow using pydantic. Pydantic parsing should also be used to repalce the bracketed output, rubric, and context fields before they are passed to the agent.

The parallel runs should be collected and packaged in the following manner:

async def collect()
	[asyncio.create task(get response) for item in lst]
	await asyncio.gather[tasks]

It should then package the results without the reasoning in the following format:

json
```
"concept": <relevant string value>
"location": <relvant string value>
"intent": <relvant string value>
"fix": <relvant string value>
"unrelated": <True or False>
```


# Function Structure Enforcement

The driving functions should have this structure. Deviation is not permitted. If implementation with this structure is impossible, you must confront the user about it, rather than make any assumption as to a correct implementation.

def next_goal(goal)
    grace = 1
    while (status := decide) != done:
        if status["unrelated"]:
            route unrelated completion
        if status == incomplete and grace:
            grace -= 1
            route incomplete completion
        elif (status == incorrect) or (status == incomplete and not grace):
            route incorrect completion
        else:
            throw edge case error
    return status

decide packages the assessor agents' runs. done is a case where concept, location, intent, and fix are all "complete" or concept and fix are both "complete".


def 
    # some code for routing the exercise and prompting for the first priority that returns some status for the loop to run
    for goal in status:
        if status[goal] != complete:
            status = next_goal(goal)

You must load the myteam question asking skill and ask implementation questions.