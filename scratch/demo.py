import openai.types.beta
from openai import OpenAI
import json
import os


def create_file_id(filename: str, dir: str) -> openai.File:
    return client.files.create(
        file=open(f'{dir}/{filename}', "rb"),  # Must be 'rb' for API to work
        purpose='assistants'
    )



def serialize_file(assistant_name: str, file: openai.File) -> None:
    with open(f'{assistant_name}-file-objects/{file.filename}.json', 'w') as f:
        f.write(file.model_dump_json(indent=4))
        # json.dump(file.__dict__, f)


def serialize_files(assistant_name: str, assistant_files: list[openai.File]) -> None:
    dir_contents = os.listdir()
    # Creates a directory to hold file objects if not already there
    if f'{assistant_name}-file-objects' not in dir_contents:
        os.mkdir(f'{assistant_name}-file-objects')

    for file in assistant_files:
        # Serialize openai.File with JSON for easy storage and retrieval
        serialize_file(assistant_name, file)


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
    # Serialize the assistant for easy retrieval later
    with open(f'assistants/{assistant_name}.json', 'w') as f:
        f.write(assistant.model_dump_json(indent=4))


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
    if f'{assistant_name}.json' not in dir_contents:
        return create_assistant(client, assistant_name)
    # Implied else statement

    # Get the assistant information
    with open(f'{dir}/{assistant_name}.json', 'r') as f:
        assistant_info = json.load(f)

    return client.beta.assistants.retrieve(assistant_info['id'])


def reset_files(client: OpenAI) -> None:
    files = client.files.list()
    for file in files:
        client.files.delete(file.id)


def add_assistant_file(client: OpenAI, filename: str, assistant: openai.types.beta.Assistant) -> None:
    dir = '.'
    file = create_file_id(filename, dir)
    assistant_file = client.beta.assistants.files.create(
        assistant_id=assistant.id,
        file_id=file.id
    )

    serialize_file(assistant.name, file)

if __name__ == "__main__":
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    my_assistant = get_assistant(client, 'Demo')

    lcr = 0
    print('ChatGPT: How can I help you today?')
    message_thread = client.beta.threads.create()
    while True:
        lcr += 1
        user_input = input("User: ")

        message = client.beta.threads.messages.create(
            thread_id=message_thread.id,
            role='user',
            content=user_input
        )

        run = client.beta.threads.runs.create(
            thread_id=message_thread.id,
            assistant_id=my_assistant.id
        )

        while run.status != 'completed':
            # TODO: There's probably a better way to wait for an update, maybe test out await / async
            run = client.beta.threads.runs.retrieve(
                run_id=run.id,
                thread_id=message_thread.id
            )

        message_thread = client.beta.threads.retrieve(message_thread.id)
        messages = client.beta.threads.messages.list(message_thread.id)
        formatted_response = "\n".join(messages.data[0].content[0].text.value.split("."))
        print(f'ChatGPT: {formatted_response}')

        if lcr == 1:
            add_assistant_file(client, 'bitbot.mdx', my_assistant)
