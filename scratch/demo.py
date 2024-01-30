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
        print('Assistant not found!\nCreating new assistant...')
        return create_assistant(client, assistant_name)
    # Implied else statement

    print('Assistant found!\nLoading assistant...')

    # Get the assistant information
    with open(f'{dir}/{assistant_name}.json', 'r') as f:
        assistant_info = json.load(f)

    return client.beta.assistants.retrieve(assistant_info['id'])


def delete_assistant(client: openai.OpenAI, assistant: openai.types.beta.Assistant) -> None:
    response = client.beta.assistants.delete(assistant.id)
    print(response)


def reset_files(client: OpenAI) -> None:
    files = client.files.list()
    for file in files:
        client.files.delete(file.id)


def add_assistant_file(client: OpenAI, assistant: openai.types.beta.Assistant, filename: str) -> None:
    dir = '.'
    file = create_file_id(filename, dir)
    # This returns an assistant file object, which is different from a File object
    client.beta.assistants.files.create(
        assistant_id=assistant.id,
        file_id=file.id
    )

    serialize_file(assistant.name, file)


def remove_assistant_file(client: openai.OpenAI,
                          assistant_id: str,
                          file_id: str) -> None:
    client.beta.assistants.files.delete(
        assistant_id=assistant_id,
        file_id=file_id
    )


def remove_serialized_file(assistant_name: str, filename: str) -> None:
    os.remove(f'{assistant_name}-file-objects/{filename}.json')
    print('File successfully deleted.\n')


def get_assistant_file_id(assistant_name: str, filename: str) -> str:
    # TODO: Implement a try catch for file not found and use API for listing assistant files
    with open(f'{assistant_name}-file-objects/{filename}.json') as f:
        return json.load(f)['id']


def get_modify_assistant_options() -> str:
    return """
Which would you like to modify?
    1. Instructions 
    2. Name (of assistant)
    3. Tools (retrieval, function, code generation)
    4. Model ('gpt4', 'gpt3.5-1106')
    5. Files (new filename(s))
    """


def get_modify_options() -> str:
    return """
How would you like to modify this assistant?
    1. Add an assistant file
    2. Remove an assistant file
    3. Modify assistant instructions, name, tools, model, file ids
    4. Delete this assistant
    """


def modify_assistant(client: openai.OpenAI, assistant: openai.types.beta.Assistant) -> None:
    print(get_modify_options())
    modify_number = int(input('Enter a number: ').strip())
    match modify_number:
        case 1:  # Add assistant file
            filename = input('Enter filename (include extension): ').strip()
            add_assistant_file(client, assistant, filename)
        case 2:  # Remove an assistant file
            filename = input('Enter filename (include extension): ').strip()
            remove_assistant_file(client, assistant.id, get_assistant_file_id(assistant.name, filename))
            remove_serialized_file(assistant.name, filename)
        case 3:  # Modify an assistant
            print(get_modify_assistant_options())
            # TODO: Implement dynamic functions to change assistant
        case 4:  # Delete this assistant
            confirmation = input(f'Are you sure you want to permanently delete {assistant.name}? [y] / [n]\n')
            if 'y' in confirmation.strip().lower():
                delete_assistant(client, assistant)
        case _:
            print('Invalid input. Please enter a number between 1-4')

    # TODO: Make this an input loop for making as many changes as the user wants


def get_gpt_completion(client: openai.OpenAI, message_thread_id: str) -> str:
    # message_thread = client.beta.threads.retrieve(message_thread_id)
    messages = client.beta.threads.messages.list(message_thread_id)
    formatted_response = "\n".join(messages.data[0].content[0].text.value.split("."))
    return f'ChatGPT: {formatted_response}'



def chat_bot(client: openai.OpenAI,
             my_assistant_id: str,
             message_thread_id: str) -> None:
    user_input = input("User: ")

    # Creating a new message that links up with the
    client.beta.threads.messages.create(
        thread_id=message_thread_id,
        role='user',
        content=user_input
    )

    run = client.beta.threads.runs.create(
        thread_id=message_thread_id,
        assistant_id=my_assistant_id
    )

    while run.status != 'completed':
        run = client.beta.threads.runs.retrieve(
            run_id=run.id,
            thread_id=message_thread_id
        )

    print(get_gpt_completion(client, message_thread_id))


# BEFORE YOU RUN:
# Make sure you have a directory named "{assistant_name}-files" with the appropriate documents
# These wil be the documents uploaded with the assistant
if __name__ == "__main__":
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    assistant_name = input("Which assistant do you want to use? ").strip()

    my_assistant = get_assistant(client, assistant_name)
    print("Assistant loaded!\n")

    modify_answer = input('Do you want to modify this assistant? [y]o / [n]o\n').lower()

    if 'y' in modify_answer:
        modify_assistant(client, my_assistant)
        print('Model has been modified.\n')

    lcr = 0
    print('ChatGPT: How can I help you today?')
    message_thread = client.beta.threads.create()
    while True:
        chat_bot(client, my_assistant.id, message_thread.id)
