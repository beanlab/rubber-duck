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

3. **Set Up Run Configuration Variables**
    - Open the run configuration menu, and change it to run the `src.main` module instead of the `main.py` script
    - Make sure the working directory is `.../rubber-duck/`
    - **Discord Token**:
        - Open Discord in your web browser.
        - Open developer tools (Control + Shift + I, or F12) and open the Network tab within it
        - Open a different text channel than the one you already had open (to force it to fetch the messages)
        - In the dev tools, look for the messages?limit=50 request. You can filter Fetch/XHR or search for it, if that
          helps. Once you've found it, click on the request
        - Under the 'Headers' section, scroll to 'Request headers', then 'Authorization'. The value of that header is
          the token
    - **OpenAI API Key**:
        - From the [organization page](https://platform.openai.com/docs/overview), go to `settings`>`API Keys`>
          `+ Create new secret key`
        - Ensure your name is included in the key name
    - Add these to your run configuration with the following format:
    ```
    DISCORD_TOKEN=your_discord_token
    OPENAI_API_KEY=your_openai_key
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
    - In rubber-duck, create a `local-testing-configs` directory in the project root (ensure it's excluded in the
      .gitignore!)
    - Inside it, create:
        - A `local_<name>_config.yaml` file (follow the structure of `local-config-example.yaml`)
        - A `local_<name>_database.db` file
    - In your config file, modify the following sections from your copy:
       ```yaml
        sql:
          db_type: sqlite
          database: local_<name>_database.db 
       ```
       ```yaml
        servers:
            BeanLab:
              server_id: 1058490579799003187
              channels:
                Ducks/<name>-chat-bot:
                  channel_id: 0000000000000000 # paste channel ID here
                  timeout: 300
                  duck:
                              - standard-rubber-duck
                    #          - stats-duck
                    #          - emoji-duck
                    #          - guessing-game-duck
        ```
        ```yaml
        admin_settings:
          admin_channel_id: 0000000000000000000 # paste admin channel ID here
          admin_role_id: 0000000000000000000 # past discord profile ID here
        ```
    - To obtain the proper IDs, turn on developer mode in Discord (`Settings`>`Advanced`>`Developer Mode`)
    - This will allow you to right-click on any channel and your profile to copy the associated IDs.

2. **Run the Bot Locally**
    - In your run configuration, add `--config ./local-testing-configs/local_<name>_config.yaml` in script parameters,
      and you should be good to go!

2. **Test the Bot**
    - In your `<name>-chat-bot channel`, send a message to test the bot's response!

## Next Steps

- Read the [Development Guide](development.md) for more detailed information
- Check out the [Architecture Overview](architecture.md) to understand the project structure
- Review the [Deployment Guide](deployment.md) for production deployment instructions

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
    - Verify your config.json file format
    - Check environment variables
    - Ensure all required fields are present

## Need Help?

- Check our [FAQ](faq.md)
- Open an issue on GitHub
- Ask in the Bean Lab Discord server
