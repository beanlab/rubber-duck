FROM python:3.11.9

LABEL authors="Wiley Welch, Bryce Martin, Dr. Gordon Bean"

WORKDIR /rubber-duck

COPY . /rubber-duck

RUN pip install openai==1.11.1 discord==2.1.0 urllib3<2.0 quest-py==0.2.0b5 \
    && pip install poetry

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

CMD ["python", "/rubber-duck/discord_bot.py"]
