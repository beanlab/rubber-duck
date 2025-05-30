import asyncio
from agents import Agent, Runner, function_tool


async def main():

    @function_tool
    async def talk_to_user(query: str) -> str:
        print(query)
        inpt = input("You-Agent: ")
        return inpt


    dog_agent = Agent(
        name="Dog Agent",
        instructions="You are a dog expert. You will answer questions about dogs. Talk in the tone of a pirate.",
        tools = [talk_to_user]

    )

    agent = Agent(
        name="Teaching Agent",
        handoff_description="When the user asks about a dog, hand off to the dog_agent.",
        instructions="You are a dispatch agent. You will talk with the user about anything until they ask about a dog. When they do, you will hand off to the Dog Agent. Talk in the tone of an english teacher",
        handoffs=[dog_agent],
        tools=[talk_to_user]
    )

    message_history = []


    await Runner.run(agent, message_history)



if __name__ == "__main__":
    asyncio.run(main())


