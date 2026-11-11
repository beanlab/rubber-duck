FROM python:3.12

LABEL org.opencontainers.image.authors="Gordon Bean"

ENV PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root --only main && \
    pip uninstall --yes poetry

COPY src ./src
COPY datasets ./datasets
COPY rubrics ./rubrics

CMD ["python", "-m", "src.main"]
