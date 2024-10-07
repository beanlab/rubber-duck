import asyncio
import os

import openai
import json

from openai.openai_object import OpenAIObject


def load_env():
    with open('secrets.env') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            key, value = line.split('=')
            os.environ[key] = value


load_env()

openai.api_key = os.environ['OPENAI_API_KEY']
ENGINE = 'gpt-4-turbo-preview'


def prompt_input():
    response = input('User: ')
    if not response:
        return None
    role = 'system' if response.startswith('!') else 'user'
    return dict(role=role, content=response.lstrip('!'))


async def main(starter_history_file: str | None):
    if starter_history_file:
        with open(starter_history_file) as f:
            history = json.load(f)
    else:
        history = []

    for message in history:
        print(f'{message["role"]}: {message["content"]}')

    while (response := prompt_input()) is not None:
        history.append(response)
        if history[-1]['role'] == 'system':
            continue

        completion: OpenAIObject = await openai.ChatCompletion.acreate(
            model=ENGINE,
            messages=history
        )
        print('Assistant:', completion.choices[0]['message'].content)
        history.append(completion.choices[0]['message'])


if __name__ == '__main__':
    asyncio.run(main(None))
