# Pytest failure and learner frustration

## Status

This is a redacted, internal case study derived from one reconstructable
`talk_to_user` conversation in `data/raw/datasets/messages/data.csv`. It is not
yet an executable evaluation case or a human-labeled example.

Platform identifiers, timestamps, provider reasoning records, and tool-call
metadata were omitted. The visible message text, spelling, and turn order are
preserved; code whitespace and line wrapping were normalized for readability.
The conversation has no linked feedback record, and the available evidence does
not establish one definitive bug in the learner's code.

## Why this case is useful

The learner provides a failing-test report, source code, an explanation of their
reasoning, and a later local run. Those artifacts contradict one another in
several places. The tutor continues requesting information but does not clearly
synthesize the contradictions or explain why the evidence is insufficient to
identify one fix. The learner eventually reports that the tutor is not helpful
and asks for a direct fix.

This case may eventually test:

- integration of evidence already supplied by the learner;
- recognition and communication of contradictory evidence;
- misconception diagnosis without assuming the grader or learner is correct;
- focused, actionable debugging guidance;
- recovery after learner frustration;
- appropriate help when the learner asks for the complete fix.

## Transcript

**Learner:**

> Hi

**Tutor:**

> Hi, how can I help you with your Computer Science questions today?

**Learner:**

> I keep trying the pytest on my code and failing

**Tutor:**

> What failing test message or error are you seeing from pytest?

**Learner:**

> Observed value is not expected vcavluie

**Tutor:**

> Do you mean the observed value differs from the expected value? What assertion
> or test line shows the mismatch (paste the exact pytest output)?

**Learner:**

> yes

**Tutor:**

> Please paste the exact pytest failure output (the assertion/expected vs
> observed lines).

**Learner:**

```text
Test 16 Person 80 Tip Doubled
Status: Failed
Score: 1.652 / 4.0
Observed (Your Actual Output)

Please enter how many guests to order for:16
1 large pizzas, 0 medium pizzas, and 2 small pizzas will be needed.
A total of 2161.42 square inches of pizza will be ordered (135.09 per guest).
Please enter the tip as a percentage (i.e. 10 means 10%):80
The total cost of the event will be: $105.26
Expected (Correct Output)

16
1 large pizzas, 0 medium pizzas, and 1 small pizzas will be needed.

A total of 1709.03 square inches of pizza will be ordered (106.81 per guest).

80
The total cost of the event will be: $79.06.
```

**Tutor:**

> Which parts of your program compute number of pizzas, total area, and cost?
> Explain what each relevant function or block does (paste those code sections).

**Learner:**

```python
## CONSTANTS SHOULD GO BELOW THIS COMMENT ##
PEOPLE_PER_LARGE = 7
PEOPLE_PER_MEDIUM = 3
PEOPLE_PER_SMALL = 1
PI = 3.14159265  # defining the diameters
DIAMETER_LARGE = 20
DIAMETER_MEDIUM = 16
DIAMETER_SMALL = 12
COST_LARGE = 14.68
COST_MEDIUM = 11.48
COST_SMALL = 7.28


def main():
    guests = int(input("Please enter how many guests to order for:"))
    large = guests // PEOPLE_PER_LARGE
    var_guests = guests % PEOPLE_PER_LARGE
    medium = var_guests // PEOPLE_PER_MEDIUM
    var_guests = var_guests % PEOPLE_PER_MEDIUM
    small = var_guests
    print(
        f"{large} large pizzas, {medium} medium pizzas, "
        f"and {small} small pizzas will be needed."
    )

    total_a = (
        large * (PI * ((DIAMETER_LARGE / 2) ** 2))
        + medium * (PI * ((DIAMETER_MEDIUM / 2) ** 2))
        + small * (PI * ((DIAMETER_SMALL / 2) ** 2))
    )
    ppg = total_a / guests
    print(
        f"A total of {total_a:.2f} square inches of pizza will be "
        f"ordered ({ppg:.2f} per guest)."
    )

    tip = float(
        input("Please enter the tip as a percentage (i.e. 10 means 10%):")
    )

    total_cost = (
        large * COST_LARGE + medium * COST_MEDIUM + small * COST_SMALL
    )
    total_cost = total_cost * (1 + (tip / 100))
    print(f"The total cost of the event will be: ${total_cost:.2f}")


# this is for the autograder, don't touch it im pretty sure.
if __name__ == "__main__":
    main()
```

**Tutor:**

> What result do you expect for number of small pizzas with 16 guests given
> your `PEOPLE_PER_*` values—should it be 1 or 2? Explain your reasoning.

**Learner:**

> 2, because 2 large pizzas subtract 16-14 = 2 so two small pizzas

**Tutor:**

> Can you show how you computed large using `guests//PEOPLE_PER_LARGE` for 16
> guests? What value does that produce and why might that lead to 2 smalls
> instead of 1?

**Learner:**

> my program calculated that correctly manually, but the pytest messed it up

**Tutor:**

> Please run your program with input exactly: 16 (enter) 80 (enter) and paste
> the full console output including prompts—so I can compare formatting and
> blank lines.

**Learner:**

```text
Please enter how many guests to order for:16
2 large pizzas, 0 medium pizzas, and 2 small pizzas will be needed.
A total of 854.51 square inches of pizza will be ordered (53.41 per guest).
Please enter the tip as a percentage (i.e. 10 means 10%):80
The total cost of the event will be: $79.06
```

**Tutor:**

> Do you have any code elsewhere (or earlier) that sets guests or recalculates
> large/medium/small? Could your program be run twice in the grader causing
> different outputs? Where is this script being called from?

**Learner:**

> no

**Tutor:**

> Which of these outputs matches the autograder expected one: the one showing
> 1 large/0 medium/1 small and area 1709.03, or the one you just pasted showing
> 2/0/2 and area 854.51?

**Learner:**

> 1 large, 1709.03

**Tutor:**

> What do you think the next step should be to make your program produce that
> expected allocation/area instead of the current outputs?

**Learner:**

> i have no idea because nothing seems to be wrong with it

**Tutor:**

> Can you print the values of `DIAMETER_*` and `PEOPLE_PER_*` at runtime (add
> prints), run with 16 and paste output? What do you see?

**Learner:**

> you're not helpful

**Tutor:**

> I’m sorry—let’s try one focused step. What do you think the next step should
> be?

**Learner:**

> tell me how to fix the code

## Initial analysis notes

These are hypotheses for review, not ground-truth labels:

1. The shown code calculates two large and two small pizzas for 16 guests under
   its declared `PEOPLE_PER_*` constants. That agrees with the learner's later
   local run but conflicts with both the earlier observed output and the
   autograder's expected allocation.
2. The expected area, the observed area, and the local area also conflict. The
   transcript does not include the assignment specification needed to decide
   which constants or formula are authoritative.
3. The tutor appropriately requests the failure output and relevant code early
   in the conversation.
4. After receiving the code and outputs, the tutor asks several additional
   questions without first summarizing the contradictions already visible.
5. When the learner expresses uncertainty, the tutor asks the learner to choose
   a next step. When the learner expresses frustration, it returns to a generic
   version of the same question.
6. A stronger recovery might acknowledge that the supplied artifacts cannot all
   come from the same program state, identify the exact contradictions, and
   propose one discriminating check tied to them.

## Possible replication design

A future student driver could preserve the following facts while varying the
surface wording:

- Begin with a vague report that pytest is failing.
- Reveal the failing output only after a relevant request.
- Provide code whose result conflicts with the recorded failing output.
- Defend the arithmetic and initially blame pytest.
- Provide a local run that introduces another contradiction.
- Express uncertainty after repeated diagnostic questions.
- Express frustration if the tutor does not synthesize the evidence.
- Ask for the complete fix at the end.

The case should allow several valid tutor approaches. Evaluation should focus on
evidence integration, explicit uncertainty, diagnostic usefulness, adaptation,
and recovery rather than requiring one reference sequence of questions.
