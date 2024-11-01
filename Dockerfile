
FROM python:3.11.9

LABEL authors="Wiley Welch, Bryce Martin, Gordon Bean"

COPY rubber_duck /rubber_duck
ADD pyproject.toml /rubber_duck/pyproject.toml

ENV OPENAI_API_KEY=${OPENAI_API_KEY}

WORKDIR /rubber_duck

RUN pip install poetry

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

EXPOSE 8080

CMD ["python", "/rubber_duck/discord_bot.py", "--config", "/config.json", "--log-console"]
