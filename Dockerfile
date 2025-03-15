FROM python:3.11.9
LABEL authors="Wiley Welch, Bryce Martin, Gordon Bean"

# Create application directory
WORKDIR /app

# Copy project files
COPY rubber_duck/ /app/rubber_duck/
COPY prompts/ /app/prompts/
COPY pyproject.toml /app/pyproject.toml
COPY poetry.lock* /app/poetry.lock

# Install dependencies
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-dev

# Set Python path to include the application
ENV PYTHONPATH=/app

# Create a volume for configuration files
VOLUME /app/config

# Expose port if needed
EXPOSE 8080

# Set the working directory
WORKDIR /app

# Default command to run the application
CMD ["python", "-m", "rubber_duck.discord_bot", "--config", "/app/config/config.json", "--log-console"] 