import openai.types.beta
from openai import OpenAI
import pickle
import json
import os


def create_file_id(filename: str, dir: str) -> openai.File:
    return client.files.create(
        file=open(f'{dir}/{filename}', "rb"), # Must be 'rb' for API to work
        purpose='assistants'
    )


def serialize_files(assistant_name: str, assistant_files: list[openai.File]) -> None:
    dir_contents = os.listdir()
    # Creates a directory to hold file objects if not already there
    if f'{assistant_name}-file-objects' not in dir_contents:
        os.mkdir(f'{assistant_name}-file-objects')

    for file in assistant_files:
        # Serialize openai.File with JSON for easy storage and retrieval
        with open(f'{assistant_name}-file-objects/{file.filename}.json', 'w') as f:
            json.dump(file.__dict__, f)



def get_file_ids(assistant_name: str) -> list:
    # Read the files and generate unique file ids for each document
    dir = f'{assistant_name}-files'
    files = os.listdir(dir)
    assistant_files = [create_file_id(file, dir) for file in files]

    # Serialize the documents as .json
    serialize_files(assistant_name, assistant_files)

    # We only need the file ids to pass into the assistant
    file_ids = [file.id for file in assistant_files]
    return file_ids


def get_assistant_instructions() -> str:
    with open('assistant-instructions.txt') as f:
        return f.read()


def serialize_assistant(assistant_name: str, assistant: openai.types.beta.Assistant) -> None:
    # Pickle the assistant for easy retrieval later
    # Also, serializing with JSON didn't work
    with open(f'assistants/{assistant_name}.pkl', 'wb') as f:
        pickle.dump(assistant, f)



def create_assistant(client: OpenAI, assistant_name: str) -> openai.types.beta.Assistant:
    instructions = get_assistant_instructions()
    assistant = client.beta.assistants.create(
        instructions=instructions,
        name=assistant_name,
        tools=[{"type": "retrieval"}],
        model="gpt-3.5-turbo-1106",
        file_ids=get_file_ids(assistant_name)
        # Generates file ids for all the files in the folder with the assistant's name
    )

    serialize_assistant(assistant_name, assistant)

    return assistant


def get_assistant(client: OpenAI, assistant_name: str) -> openai.types.beta.Assistant:
    dir_contents = os.listdir()
    dir = 'assistants'
    # Create the directory "assistants" if it isn't there
    if dir not in dir_contents:
        os.mkdir(dir)


    dir_contents = os.listdir(dir)
    # If there isn't a serialized version of this specific assistant, create a new one
    if f'{assistant_name}.pkl' not in dir_contents:
        return create_assistant(client, assistant_name)
    # Implied else statement

    # Unpickle the assistant
    with open(f'{dir}/{assistant_name}.pkl', 'rb') as f:
        return pickle.load(f)


def reset_files(client: OpenAI) -> None:
    files = client.files.list()
    for file in files:
        client.files.delete(file.id)


if __name__ == "__main__":
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    my_assistant = get_assistant(client, 'Demo')

    while True:
        user_input = input("ChatGPT: How can I help you today?\n")

