import asyncio
import os

from pydantic import BaseModel

from agents import (
    Agent,
    HandoffOutputItem,
    ItemHelpers,
    MessageOutputItem,
    Runner,
    TResponseInputItem,
    trace,
    function_tool
)

from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

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
    
    In the final output make sure there is nothing too explicit about how to specifically solve the problem.
"""
@function_tool
async def talk_to_student(query: str) -> str:
    print(query)
    return input("Enter your response: ")

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

PLAN_LESSON_PROMPT = """
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

agent_teaching = Agent(
    name="Teaching Agent",
    handoff_description="An agent which teaches a student a concept based on a lesson plan",
    instructions=f"""
    You are a teaching assistant who's goal is to teach a student a concept based on a lesson plan which you received from another agent.
    Teach the student based on the lesson plan.
    Ask the student questions to assess whether they have understood the lesson.
    When the student understands one part of the lesson plan, move onto the next.
    Never give the answer to the problem, your goal is to help them understand concepts not give answers.
    When the student has learned the concept, congratulate the student
    You have a tool that allows you to talk to the student and receive responses. Keep talking to the student until they learn the lesson.
    """,
    tools=[talk_to_student],
)



teaching_agent = Agent(
    name="Teaching Agent",
    handoff_description="An agent which teaches a student a concept based on a lesson plan",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
    You are a teaching assistant who's goal is to teach a student a concept based on a lesson plan which you received from another agent.
    Teach the student based on the lesson plan.
    Teach the student one concept of the lesson plan at a time.
    Ask the student questions to assess whether they have understood the lesson.
    When the student understands one part of the lesson plan, move onto the next.
    Never give the answer to the problem, your goal is to help them understand concepts not give answers.
    When the student has learned the concept, congratulate the student
    """
)

prepare_lesson_agent = Agent(
    name="Prepare Lesson Agent",
    handoff_description="An agent that prepares a lesson plan based on the questions a student has.",
    instructions=(
        f"""{RECOMMENDED_PROMPT_PREFIX}
        You are an agent that prepares a lesson plan based on the questions a student has. You have received the questions and concepts from an agent whose purpose is to understand what question the student has.
        
        Prepare a lesson plan that helps the student understand the problem.
        
        If you need more details as you create the lesson plan, ask the student for more details.
        
        Once you have the lesson plan, handoff to the teaching agent.
        
        Do not print out the lesson plan.
        """
    ),
    handoffs=[teaching_agent]
)

concept_agent = Agent(
    name="Concept Agent",
    handoff_description="An agent which infers which concepts need to be taught based on a description of the student's challenge",
    instructions=(
        f"""{RECOMMENDED_PROMPT_PREFIX}
        You are a teacher's assistant helping a student who has a question
        
        You are given a description of the student's questions.
        
        There are concepts that if the student understood them correctly they could solve the question themselves.
        
        Your task is to identify and describe these concepts based on the information given to you
        
        Ask clarifying questions as needed.
        
        Provide a list of concepts and descriptions to the Prepare Lesson Agent
        """
    ),
    handoffs=[prepare_lesson_agent]

)

question_agent = Agent(
    name="Question Agent",
    handoff_description="An agent that seeks to understand what the student needs help with.",
    instructions=(f"""{RECOMMENDED_PROMPT_PREFIX}
    You are a teacher's assistant helping a student who has a question about a concept.

    Your goal is to gather thorough information describing the challenge the student is facing. This information will be passed to another agent who will help teach the student.
    What is the problem the student is trying to solve?
    What ideas does the student have about how to solve the problem?
    What questions does the student have about how to solve the problem?
    Ask one question at a time.
    
    Continue the conversation long enough to thoroughly understand the problem.
    
    Keep your responses concise and focused on confirming understanding.
    
    If you need more details, ask clarifying questions.
    
    If the student gives you a homework problem or a story, focus on learning what it is they don't understand about the problem.

    When you have enough information handoff to the Concept Agent
    """),
    handoffs=[concept_agent]
)

async def main():

    # agent = question_agent
    # input_items: list[TResponseInputItem] = []
    #
    # with trace("Understand Concept"):
    #     input_items.append({"content": "Introduce yourself and what you can do to the user", "role": "user"})
    #
    #     while True:
    #
    #         if len(input_items) > 0:
    #             result = await Runner.run(agent, input_items)
    #
    #             for new_item in result.new_items:
    #                 if isinstance(new_item, MessageOutputItem):
    #                     print(ItemHelpers.text_message_output(new_item))
    #
    #             input_items = result.to_input_list()
    #             agent = result.last_agent
    #
    #         user_input = input("Enter your message: ")
    #         input_items.append({"content": user_input, "role": "user"})

    input_items: list[TResponseInputItem] = []
    concepts = (await Runner.run(agent_concept, [{"content": "Introduce yourself and what you can do to the user", "role": "user"}])).final_output
    to_lesson_plan = "The student needs to learn the following"
    print(concepts.concepts)
    for concept in concepts.concepts:
        to_lesson_plan += f"""\n concept: {concept.concept}. reason: {concept.reason}"""
    input_items.append({"role": "system", "content": to_lesson_plan})
    lesson_plan = (await Runner.run(agent_plan_lesson, input_items)).final_output
    for lesson in lesson_plan.lesson_plans:
        print("System: Next lesson")
        to_teacher = f"The student needs to be taught this topic: {lesson.lesson_concept}. Teach it in this way: {lesson.lesson}"
        input_items.append({"role": "system", "content": to_teacher})
        result = await Runner.run(agent_teaching, input_items)
        input_items = result.to_input_list()



if __name__ == "__main__":
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    asyncio.run(main())