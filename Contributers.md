# Rubber Duck Project

## Introduction 
Welcome to the Rubber-Duck Project! This guide will help you set up the project on your local machine.

## Prerequisites
The following technologies each have their own section that you can read specifics about regarding rubber duck. **Please go in order** with this list to save time and to save yourself the headache. If these technologies are unfamiliar to you, don't worry! That's why this guide is here. You can read and learn more about these during your "Research time" each week.
- **Do very first! Send the following to Dr.Bean your GitHub profile name, OPENAI username, your Discord Username**
- Git
- OPEN AI Account Creation and Organization Set-Up
- Customizing your config file
- Docker
- AWS CLI & ECR

## Git
- If you haven't already send your GitHub username to Dr. Bean so he can you add you to the Bean Lab organization in Github.
  - Check your https://github.com/ account to see if you have any pending invites after you have sent your information to Dr. Bean
  - After that look for an organization named "Bean Lab" https://github.com/beanlab.
  - After, go to the repo for rubber duck. This is where you will need to make a clone of your project.
    - It should be something like **git clone https://github.com/beanlab/rubber-duck.git** check the offical documentation.
  - Next you are going to want to check the Rubber Duck Projects tab. Which can be found at the top of your window.
    - Inside here you can find the ongoing projects and issues for the Rubber Duck. We encourage you become familiar with creating issues and branches from this tab. That way you will be better prepared when you meet with Dr. Bean and when he requests a new feature or update.  

## OPEN AI Account
  - **If you haven't done this yet, register an account with OpenAI and send the username and email to Dr. Bean**
  - Check your email to see if you received an email from Dr. Bean inviting you to the BYU Computer Science Bean Organization.
  - Make sure your organization is set correctly. Go to the settings and look for API Keys.
    - Create a new secret key and record this information in a safe place. You will use this information for the rest of the semester. **Do not share this information with anyone! Don't accidently expose it to GitHub. This poses a serious security risk.** We will show you the proper way to protect this information later.



# Intro Assignment
The assignment it to create your own discord bot or rubber duck. Follow the instructions posted on this *instructions* discord channel to test if everything is running correctly. https://discord.gg/YGRXPCCT

## Usage
The bot listens to the configured channel, currently set in the source code as `"duck-pond"`

When a user posts a message to the duck pond, the duck bot 
creates a public thread in response. 

To add a new listening channel, add a file named by the channel in the prompts folder.
The file should contain the prompt to use for each thread in that channel.


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

