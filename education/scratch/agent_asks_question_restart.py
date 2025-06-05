import ast
import asyncio

from agents import Agent, Runner, function_tool, handoff, RunContextWrapper, ModelSettings


async def main():
    @function_tool
    async def talk_to_user(query: str) -> str:
        print(f"Agent: {query}")
        inpt = await asyncio.to_thread(input, "You: ")
        if inpt.lower() == "exit":
            inpt = "The user has exited the conversation."
        return inpt

    def make_on_handoff(target_agent: Agent):
        async def _on_handoff(ctx: RunContextWrapper[None]):
            print(f"\n--- Handoff to {target_agent.name} ---\n")

        return _on_handoff

    cat_agent = Agent(
        name="Cat Agent",
        handoff_description="If the user asks a question that does not relate to cats, hand off to the dispatch agent.",
        instructions="You are a cat expert. IMMEDIATELY greet the user and ask them a question about cats using the talk_to_user tool. Continue talking back and forth with the user until they mention dogs. Always use the talk_to_user tool for every response - never respond without using this tool first.",
        tools=[talk_to_user],
        model_settings=ModelSettings(tool_choice="required"),
        handoffs=[],
    )

    dog_agent = Agent(
        name="Dog Agent",
        handoff_description="If the user asks a question that does not relate to dogs, hand off to the dispatch agent.",
        instructions="You are a dog expert. IMMEDIATELY greet the user and ask them a question about dogs using the talk_to_user tool. Continue talking back and forth with the user until they mention cats. Always use the talk_to_user tool for every response - never respond without using this tool first.",
        tools=[talk_to_user],
        model_settings=ModelSettings(tool_choice="required"),
        handoffs=[],
    )

    dispatch_agent = Agent(
        name="Dispatch Agent",
        handoff_description="When the user asks about a dog or a cat, hand off to the correct agent.",
        instructions="You are a dispatch agent. Continue talking back and forth with the user until the user mentions dogs or cats, then hand off. Always use the talk_to_user tool to communicate with the user - never respond without using this tool first.",
        tools=[talk_to_user],
        model_settings=ModelSettings(tool_choice="required"),
        handoffs=[],
    )

    dog_handoff = handoff(agent=dog_agent, on_handoff=make_on_handoff(dog_agent))
    cat_handoff = handoff(agent=cat_agent, on_handoff=make_on_handoff(cat_agent))
    dispatch_handoff = handoff(agent=dispatch_agent, on_handoff=make_on_handoff(dispatch_agent))

    dispatch_agent.handoffs = [dog_handoff, cat_handoff]
    cat_agent.handoffs = [dispatch_handoff]
    dog_agent.handoffs = [dispatch_handoff]

    def find_last_agent_conversation(logs):
        for entry in reversed(logs):
            if entry.get("type") == "function_call_output":
                output_str = entry.get("output", "")
                try:
                    output_dict = ast.literal_eval(output_str)
                    if "assistant" in output_dict:
                        last_agent_name = output_dict["assistant"].lower().replace(" ", "_")
                        return last_agent_name
                except Exception:
                    continue
        return "unknown_agent"

    def find_last_agent_from_transfers(logs, start_agent, agents):
        last_agent = start_agent
        for entry in logs:
            if entry.get("type") == "function_call":
                function_name = entry.get("name", "")
                if function_name.startswith("transfer_to_"):
                    agent_name = function_name.replace("transfer_to_", "")
                    agent = next((a for a in agents if a.name == agent_name), None)
                    if agent:
                        last_agent = agent
                    else:
                        continue
        return last_agent






    agents = {
        "cat_agent": cat_agent,
        "dog_agent": dog_agent,
        "dispatch_agent": dispatch_agent,
    }

    message_history = [
        {"role": "system", "content": "Introduce yourself and what you can do to the user using the talk_to_user tool"},
        {"role": "user", "content": "Hi"},
    ]

    # Have a regular conversation starting with the dispatch agent
    result = await Runner.run(dispatch_agent, message_history, max_turns=100)

    print("\n--- Conversation Finished ---\n")

    # Get the message history from the conversation
    message_history_2 = result.to_input_list()

    print(f"Message History:\n{message_history_2}\n")
    # Find the last agent that handled the conversation
    last_agent = find_last_agent_conversation(message_history_2)

    last_agent2 = find_last_agent_from_transfers(message_history_2, dispatch_agent, agents.values())
    print(last_agent2)

    # Run again with the last agent, and trim the last 3 messages to avoid using the ending of the conversation
    await Runner.run(agents[last_agent], message_history_2[:-3], max_turns=100)


if __name__ == "__main__":
    asyncio.run(main())
