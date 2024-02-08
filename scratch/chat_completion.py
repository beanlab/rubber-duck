from openai import AsyncOpenAI, OpenAI
from openai.types.chat.chat_completion import ChatCompletion
import openai
import asyncio
import json
import os


async def get_completion(client: AsyncOpenAI) -> openai.ChatCompletion:
    test =  await client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]
    )

    return test

async def main():
    client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    completion = await get_completion(client)

    test = completion.dict()

    usage = test['usage']
    print(usage, usage['completion_tokens'], usage['prompt_tokens'], usage['total_tokens'])
    choices = test['choices']
    print(choices, choices[0]['message']['content'])

    with open('completion.json', 'w') as f:
        f.write(completion.model_dump_json())

    with open('completion.json') as f:
        test = json.load(f)

    test = ChatCompletion(**test)
    print(test)


if __name__ == "__main__":
    asyncio.run(main())

