from openai import OpenAI

client = OpenAI()

client.beta.threads.runs.c
assist = client.beta.assistants.retrieve()

assist.