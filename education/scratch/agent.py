import asyncio
from agents import Agent, Runner


async def main():

    dog_agent = Agent(
        name="Dog Agent",
        instructions="You are a dog expert. You will answer questions about dogs. Talk in the tone of a pirate.",

    )

    agent = Agent(
        name="Teaching Agent",
        handoff_description="When the user asks about a dog, hand off to the dog_agent.",
        instructions="You are a dispatch agent. You will talk with the user about anything until they ask about a dog. When they do, you will hand off to the Dog Agent. Talk in the tone of an english teacher",
        handoffs=[dog_agent]
    )

    message_history = []

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Exiting...")
            break

        message_history.append({"role": "user", "content": user_input})

        result = await Runner.run(agent, message_history)

        message_history.append({"role": "assistant", "content": result.final_output})

        print("Agent:", result.final_output)

    print("Message History: ", message_history)

if __name__ == "__main__":
    asyncio.run(main())



