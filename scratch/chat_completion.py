from openai import AsyncOpenAI, OpenAI
import openai
import os


async def get_completion(client: AsyncOpenAI) -> openai.ChatCompletion:
    test =  await client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]
    )

    return test[2]

async def main():
    client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    completion = await get_completion(client)

    print(completion.choices[0].message.content)


if __name__ == "__main__":
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    test = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]
    )

    test = test.dict()

    usage = test['usage']
    print(usage, usage['completion_tokens'], usage['prompt_tokens'], usage['total_tokens'])
    choices = test['choices']
    print(choices, choices[0]['message']['content'])

