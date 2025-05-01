# Rubber Duck Discord Bot

## Usage
The bot listens to the configured channel, currently set in the source code as `"duck-pond"`

When a user posts a message to the duck pond, the duck bot 
creates a public thread in response. 

To add a new listening channel, add a file named by the channel in the prompts folder.
The file should contain the prompt to use for each thread in that channel.

## TODO
- [ ] Gracefully handle deleted threads
- [ ] Clean up expired threads
- [ ] Serialize state on exit, load on startup

## Setup
- Create an OPENAI account
  - https://openai.com/
  - Get the API key and provide it as the environment variable `OPENAI_API_KEY` to the bot
- Create a new discord application
  - https://discord.com/developers/applications
  - Get the token under the bot tab and provide it as the environment variable `DISCORD_TOKEN` to the bot
  - Under "Bot"
    - Select "Message content intent"
  - Under "OAuth2"
    - Select "bot" scope
    - Permissions:
      - Send messages
      - Create public threads
      - Send messages in threads
      - Manage threads
      - Add reactions
    - Copy the generated link, paste in the URL bar of your browser, 
      and use it to add the bot to your server
  - Install `poetry`
    - https://python-poetry.org/docs/#installation
    - `curl -sSL https://install.python-poetry.org | python3 -`
  - Clone this repo
    - requires python 3.11
    - run `poetry install`

To run on server:
- cd to project folder
- `git pull`
- `poetry install`
- `nohup poetry run python discord_bot.py >> /tmp/duck.log &`

To kill on server:
- `ps -e | python`
- `kill <pid>`

