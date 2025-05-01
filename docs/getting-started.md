# Getting Started with Rubber Duck

This guide will help you set up your development environment and get started with the Rubber Duck project.

## Prerequisites

Before you begin, you'll need:

1. **GitHub Account**

   - Ensure you have access to the Bean Lab organization
   - Verify your GitHub account for pending invitations

2. **OpenAI Account**

   - Register an account with OpenAI
   - Get your API key from the OpenAI dashboard

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

3. **Set Up Environment Variables**
   Create a `.env` file in the project root with:
   ```
   DISCORD_TOKEN=your_discord_token
   OPENAI_API_KEY=your_openai_key
   ```

## Discord Bot Setup
**Join the WICS Skillathon Build A Bot Server**
   - Go to the [Tutorial Server](https://discord.gg/nu4MV2mzMw)
   - Follow the Skillathon Setup starting with **1-setup-python**
   - **This is required before moving on!**

## Local Development

1. **Run the Bot Locally**

   ```bash
   poetry run python src/main.py --config config.json --log-console
   ```

2. **Test the Bot**
   - Create a channel named "duck-pond" in your Discord server
   - Send a message to test the bot's response

## Next Steps

- Read the [Development Guide](development.md) for more detailed information
- Check out the [Architecture Overview](architecture.md) to understand the project structure
- Review the [Deployment Guide](deployment.md) for production deployment instructions

## Troubleshooting

If you encounter issues:

1. **Bot Not Responding**

   - Verify the bot token is correct
   - Check the channel permissions
   - Ensure the bot has the required intents

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
