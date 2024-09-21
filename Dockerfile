FROM python:3.11

COPY . /rubber-duck

RUN pip install openai==^1.11.1 discord==^2.1.0 urllib3==<2.0 quest-py==0.2.0b5

CMD ["python", "/rubber-duck/discord_bot.py"]