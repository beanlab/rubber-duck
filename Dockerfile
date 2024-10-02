FROM python:3.11.4-slim

LABEL authors="Wiley Welch, Bryce Martin, Gordon Bean"

COPY rubber_duck /rubber_duck
ADD pyproject.toml /rubber_duck/pyproject.toml

WORKDIR /rubber_duck

RUN pip install poetry

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

CMD ["python", "/rubber_duck/discord_bot.py", "--config", "/config.json", "--state", "/state", "--secrets", "/.env"]
