from __future__ import annotations

import os
from openai import OpenAI

from education.scratch.Duck_Agent.agent import Agent
from education.scratch.Duck_Agent.coordinator import AgentCoordinator
from education.scratch.Duck_Agent.tools import ToolRegistry




def main():
    def add(a: int, b: int) -> int:
        """Adds two integers."""
        print("Adding two integers...")
        return a + b

    def concise_sentence(sentence: str) -> str:
        """Rewrites a sentence to be more concise."""
        print("Rewriting sentence to be more concise...")
        return ' '.join(sentence.split())

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    registry = ToolRegistry()

    registry.register(add)
    registry.register(concise_sentence)

    router_agent = Agent(
        client=client,
        tool_registry=registry,
        name="RouterAgent",
        model="gpt-4.1",
        prompt="IMMEDIATELY greet the user and talk to them using the talk_to_user tool. You are a routing agent for math and english questions. Continue talking back and forth with the user until the user mentions a question regarding math or english subjects, then hand off. You answer any question that does not have to do with math or english. If a question is about math, you route it to the math agent. If a question is about english, you route it to the english agent.",
        handoff_description="When the user asks about math or english, hand off to the correct agent.",
        handoffs=["MathAgent", "EnglishAgent"]
    )

    math_agent = Agent(
        client=client,
        tool_registry=registry,
        name="MathAgent",
        model="gpt-4.1",
        prompt="You are a math agent. IMMEDIATELY greet the user and talk to them using the talk_to_user tool. You can perform addition operations. When you have fully answered the user's math question, you can either continue helping with more math questions or hand off back to the routing agent if the user wants to discuss other topics.",
        tools=[registry.tools['add']],
        handoff_description="If the user asks a question that does not relate to math, hand off to the routing agent.",
        handoffs=["RouterAgent"]
    )

    english_agent = Agent(
        client=client,
        tool_registry=registry,
        name="EnglishAgent",
        model="gpt-4.1",
        prompt="You are an english agent. IMMEDIATELY greet the user and talk to them using the talk_to_user tool. You help rewrite sentences to be more concise. When you have fully answered the user's english question, you can either continue helping with more english questions or hand off back to the routing agent if the user wants to discuss other topics.",
        tools=[registry.tools['concise_sentence']],
        handoff_description="If the user asks a question that does not relate to english, hand off to the routing agent.",
        handoffs=["RouterAgent"]
    )

    coordinator = AgentCoordinator()

    coordinator.register_agent(router_agent)
    coordinator.register_agent(math_agent)
    coordinator.register_agent(english_agent)

    coordinator.setup_handoffs(registry)

    coordinator.start_conversation(router_agent)


if __name__ == "__main__":
    main()
