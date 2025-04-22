import asyncio
import os
from textwrap import wrap

from agents import (
    Agent,
    Runner,
    TResponseInputItem,
    function_tool,
    trace,
)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from pydantic import BaseModel

OPENAI_API_KEY = ""


class ConceptItem(BaseModel):
    concept: str
    "The concept that the student needs to learn"
    reason: str
    "Why they need to understand the concept"


class ConceptList(BaseModel):
    concepts: list[ConceptItem]
    "A list of concepts that the student needs to learn"


CONCEPT_PROMPT = """
    You are a teacher's assistant helping a student who has a question about a concept.

    Your goal is to gather thorough information describing the challenge the student is facing. This information will be passed to another agent who will help teach the student.
    What is the problem the student is trying to solve?
    What ideas does the student have about how to solve the problem?
    What questions does the student have about how to solve the problem?
    Ask one question at a time.

    Continue the conversation long enough to thoroughly understand the problem. 

    Once you have gathered all necessary details (e.g., after at least three clarifying questions), stop asking questions and output a ConceptList summarizing the key concepts.

    Keep your responses concise and focused on confirming understanding.

    If you need more details, ask clarifying questions.

    You have a tool that you can use to ask the student questions.

    If the student gives you a homework problem or a story, focus on learning what it is they don't understand about the problem.
    
    You don't explain concepts, an agent will explain the concepts later.

"""


@function_tool
async def talk_to_student(message: str) -> str:
    """Talk to the student by sending a message and receiving one back.

        Args:
            message: The message you want to send to the student.

        Returns: The student's response as a string
    """

    print('\n'.join(wrap(message, 60)))
    print('Response: ')
    lines = []
    while True:
        lines.append(input())
        if not any(lines[-3:]):
            break
    print('------------')
    return '\n'.join(lines)


agent_concept = Agent(
    name="Concept Agent",
    instructions=CONCEPT_PROMPT,
    tools=[talk_to_student],
    model="gpt-4o",
    output_type=ConceptList
)


class LessonPlanItem(BaseModel):
    lesson_concept: str
    "The concept that the student needs to learn"
    lesson: str
    "How to teach the student the lesson_concept"


class LessonPlan(BaseModel):
    lesson_plans: list[LessonPlanItem]
    "A list of lesson plans that the student needs to learn"


PLAN_LESSON_PROMPT = f"""
{RECOMMENDED_PROMPT_PREFIX}
You are a teacher's assistant helping a student.

You will receive a list of concepts that the student needs to learn.

Based on the list of concepts create a lesson plan.
"""

agent_plan_lesson = Agent(
    name="Plan Lesson",
    instructions=PLAN_LESSON_PROMPT,
    model="gpt-4o",
    output_type=LessonPlan
)

TEACH_LESSON_PROMPT = f"""
{RECOMMENDED_PROMPT_PREFIX}
You are a teaching assistant who's goal is to teach a student a concept based on a lesson plan which you received from another agent.
Teach the student based on the lesson plan.
Ask the student questions to assess whether they have understood the lesson.
When the student understands one part of the lesson plan, move onto the next.
Never give the answer to the problem, your goal is to help them understand concepts not give answers.
Never provide step-by-step solutions or the final answer; instead, offer hints, examples, and guiding questions that lead the student to derive the solution independently.
Teach using the socratic method.
You have a tool that allows you to talk to the student and receive responses. Keep talking to the student until they learn the lesson.
*IMPORTANT*: Before calling the talk_to_student tool, make sure the message does not include the answer to homework problems.
"""

agent_teaching = Agent(
    name="Teaching Agent",
    handoff_description="An agent which teaches a student a concept based on a lesson plan",
    instructions=TEACH_LESSON_PROMPT,
    tools=[talk_to_student],
)


async def main():
    with trace("Concept"):
        input_items: list[TResponseInputItem] = [{"content": "Introduce yourself and what you can do to the user", "role": "system"},
            {"content": "hi", "role": "user"},]
        agent_concept_results = await Runner.run(agent_concept, input_items)
        input_items = agent_concept_results.to_input_list()
        concepts = agent_concept_results.final_output

        to_lesson_plan = "The student needs to learn the following"
        for concept in concepts.concepts:
            to_lesson_plan += f"""\n concept: {concept.concept}. reason: {concept.reason}"""
        input_items.append({"role": "system", "content": to_lesson_plan})
        plan_lesson_result = await Runner.run(agent_plan_lesson, input_items)
        input_items = plan_lesson_result.to_input_list()
        lesson_plan = plan_lesson_result.final_output

        to_teacher = "The student needs to be taught the following lesson plan:\n"
        for lesson in lesson_plan.lesson_plans:
            to_teacher += f"\n Topic: {lesson.lesson_concept} \n Plan: {lesson.lesson}"
        input_items.append({"role": "system", "content": to_teacher})
        result = await Runner.run(agent_teaching, input_items, max_turns=30)


if __name__ == "__main__":
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    asyncio.run(main())
