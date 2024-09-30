FROM python:3.11.9

LABEL authors="Wiley Welch, Bryce Martin, Gordon Bean"

WORKDIR /rubber-duck

COPY . /rubber-duck

RUN pip install poetry

#fixed this again
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

CMD ["python", "/rubber-duck/discord_bot.py"]
