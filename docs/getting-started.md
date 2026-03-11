# Getting Started with Rubber Duck

This guide will help you set up your development environment and get started with the Rubber Duck project.

## Prerequisites

Before you begin, you'll need:

1. **GitHub Account**

    - Ensure you have access to the Bean Lab organization
    - Verify your GitHub account for pending invitations

2. **OpenAI Account**

    - Register an account with [OpenAI's API platform](https://auth.openai.com/log-in)
    - Ensure you have access to the "BYU Computer Science Bean" organization

3. **Discord Account**

    - Create a Discord account if you don't have one
    - Join the Bean Lab Discord server

4. **Python 3.11**

    - Install Python 3.11 from [python.org](https://www.python.org/downloads/)
    - Verify installation with `python --version`

5. **Poetry**
    - Install Poetry from [python-poetry.org](https://python-poetry.org/docs/#installation)
    - Verify installation with `poetry --version`

## Initial Setup

1. **Clone the Repository**

   ```bash
   git clone https://github.com/beanlab/rubber-duck.git
   cd rubber-duck
   ```

2. **Install Dependencies**

   ```bash
   poetry install
   ```

3. **Set Required Environment Variables**
    - **Discord Bot Token**:
        - Go to the Discord Developer Portal for your bot application
        - Copy the bot token from the Bot settings page
    - **OpenAI API Key**:
        - From the [OpenAI Platform](https://platform.openai.com/), go to `Settings` > `API keys`
        - Create a new secret key
    - Set both in your shell or IDE run configuration:
    ```bash
    export DISCORD_TOKEN=your_discord_bot_token
    export OPENAI_API_KEY=your_openai_key
    ```

## Discord Bot Setup

**Join the WICS Skillathon Build A Bot Server**

- Go to the [Tutorial Server](https://discord.gg/nu4MV2mzMw)
- Follow the Skillathon Setup starting with **1-setup-python**, but there are a few differences to keep in mind:
    - Create a bot (name it `<name>-chat-bot`, and upload a fun profile picture for it)
    - Give it all permissions except for Administrator
    - Send the copied url in step 2 to Dr. Bean, and he will add it to the Bean Lab
    - Create two Channels in the `Ducks` section of Bean Lab
        - `<name>-chat-bot`
        - `<name>-bot-admin`

- **This is required before moving on!**

## Local Development

1. **Setup Local Config File**
    - Create your local config from the project template:
      ```bash
      mkdir -p local-testing-configs
      cp local-config-example.yaml local-testing-configs/local_<name>_config.yaml
      ```
    - Keep the same top-level structure used by production config (`sql`, `containers`, `tools`, `ducks`, `servers`,
      `admin_settings`, etc.).
    - Use includes from `local-config-example.yaml` so your local file mirrors production structure:
      - `ducks`: include from `production-config.yaml@$.ducks`
      - `cache`: include from `production-config.yaml@$.cache`
      - `agents_as_tools`: include from `production-config.yaml@$.agents_as_tools`
      - `admin_settings`: include from `production-config.yaml@$.admin_settings`
    - Update local-only values in these sections:
      - `sql.database` (point to a local sqlite file)
      - `servers.*.server_id`
      - `servers.*.channels.*.channel_id`
      - `admin_settings.admin_channel_id`
      - `admin_settings.admin_role_id`
    - For channel duck assignment, use the production-style shape:
      - `duck: standard-rubber-duck` for a global duck reference
      - or inline duck config dict for channel-specific ducks
    - To get Discord IDs, enable Developer Mode (`Settings` > `Advanced` > `Developer Mode`) and copy IDs from Discord.

2. **Run the Bot Locally**
    - Run from the repo root:
      ```bash
      poetry run python -m src.main --config ./local-testing-configs/local_<name>_config.yaml --debug
      ```

3. **Test the Bot**
    - In your `<name>-chat-bot channel`, send a message to test the bot's response!

## Next Steps

- Review the [Deployment Guide](deployment.md) for production deployment instructions
- Inspect `production-config.yaml` to understand full production configuration
- Inspect `local-config-example.yaml` for include patterns and local overrides

## Troubleshooting

If you encounter issues:

1. **Bot Not Responding**

    - Verify the all tokens and channel ids are correct
    - Check the channel permissions
    - Ensure the bot has the required intents
    - Try changing the prompt

2. **Dependency Issues**

    - Try `poetry install --no-root`
    - Check Python version compatibility
    - Clear Poetry cache if needed

3. **Configuration Problems**
    - Verify your config YAML/JSON file format
    - Check environment variables
    - Ensure all required fields are present

## Need Help?

- Open an issue on GitHub
- Ask in the Bean Lab Discord server
