import asyncio
import os

import openai
import json

from openai import OpenAI


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

client = OpenAI()


def prompt_input():
    response = input('User: ')
    if not response:
        return None
    role = 'system' if response.startswith('!') else 'user'
    return dict(role=role, content=response.lstrip('!'))


def main(starter_history_file: str | None):

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

        completion = client.chat.completions.create(
            model=ENGINE,
            messages=history
        )
        print('Assistant:', completion.choices[0]['message'].content)
        history.append(completion.choices[0]['message'])


if __name__ == '__main__':
    main(None)
