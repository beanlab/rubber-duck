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

    agent = question_agent
    input_items: list[TResponseInputItem] = []

    with trace("Understand Concept"):
        input_items.append({"content": "Introduce yourself and what you can do to the user", "role": "user"})

        while True:

            if len(input_items) > 0:
                result = await Runner.run(agent, input_items)

                for new_item in result.new_items:
                    if isinstance(new_item, MessageOutputItem):
                        print(ItemHelpers.text_message_output(new_item))

                input_items = result.to_input_list()
                agent = result.last_agent

            user_input = input("Enter your message: ")
            input_items.append({"content": user_input, "role": "user"})




if __name__ == "__main__":
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    asyncio.run(main())