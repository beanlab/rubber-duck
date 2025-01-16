# Rubber Duck Project

## Introduction 
Welcome to the Rubber-Duck Project! This guide will help you set up the project on your local machine and introduce you to the key technologies we use. 
**This will approximately take three hours.** Contact Dr. Bean if you encounter any major issues.

## Do this very first! 
Send the following information to Dr.Bean.
  - Your GitHub profile name
  - OPENAI username
  - your Discord Username
  - Your byu email so you can use AWS

## Prerequisites
The following technologies each have their own section that you can read specifics about regarding rubber duck. 
- **Please go in order** with this list to save time and to save yourself the headache. 
- If these technologies are unfamiliar to you, don't worry! That's why this guide is here. 
- You can read and learn more about these during your "Research time" each week.
  - Git and GitHub Projects
  - OPEN AI Account Creation and Organization Set-Up
  - Discord Bots
  - Customizing your config file
  - Docker
  - AWS CLI & ECR

## Git and GitHub Projects
- If you haven't already send your GitHub username to Dr. Bean so he can you add you to the Bean Lab organization in GitHub.
  - Check your https://github.com/ account to see if you have any pending invites after you have sent your information to Dr. Bean
  - After that look for an organization named "Bean Lab" https://github.com/beanlab.
  - After, go to the repo for rubber duck. This is where you will need to make a clone of your project.
    - It should be something like **git clone https://github.com/beanlab/rubber-duck.git** check the official documentation.
  - Next you are going to want to check the Rubber Duck Projects tab. Which can be found at the top of your window.
    - Inside here you can find the ongoing projects and issues for the Rubber Duck. 
    - We encourage you to become familiar with creating issues and branches from this tab. 
    - That way you will be better prepared when you meet with Dr. Bean
    - You will store any information about the feature/update into a new issue inside the project.

## OPEN AI Account
  - **If you haven't done this yet, register an account with OpenAI and send the username to Dr. Bean**
  - Check your email to see if you received an email from Dr. Bean inviting you to the BYU Computer Science Bean Organization.
  - Make sure your organization is set correctly. Go to the settings and look for API Keys.
    - Create a new secret key and record this information in a safe place. You will use this information for the rest of the semester. 
    - **Do not share this information with anyone! Don't accidentally expose it to GitHub. This poses a serious security risk.** Use a secrets file or an .env file to protect this information.

## Discord Bots
  - You are going to learn how to configure a Discord Bot using the intro assignment. This is part is key for learning how to configure your custom config file.
  - The assignment is to create your own discord bot or rubber duck. Follow the instructions posted on this Dr Bean's WICS Build A Bot Server (message him or ask another student for the link) and finish all the parts.
  - When you are finished with your bot, upload it on the channel "please-add-my-bot."
  - After you do that you are good to go.

## Customizing your config file
You should now be ready to do all the local machine set up for Rubber Duck. If you haven't yet please clone the repo for the project onto your local machine.
  - Check the repo for the config file and make a copy of it. Rename it to your name.
    - On the Bean Lab's discord server under Rubber-Duck add a bot channel and an admin channel.
      -  Name it to be your-name-chat-bot/your-name-bot-admin.
      - After it is created, right click on it to get the channel ID
    - In the config file, under the channels section go to config section and change the name section to match the name of your discord bot.
    - [Example Config Image](images/example-config.png)
      - Change that long id below the "feedback" to match the server id. This can be found by right-clicking the discord server icon. It should look like a seed.
    - After that, change the "Channel ID" field to match the channel id.
    - You will need to repeat these steps for the admin channel as well.
      - When the config file asks for a reviewer_role_id or admin_role_id you will need to put your personal discord id in those fields
    - For the name section use any label that makes sense for your channel. This is here for organizational purposes.
    - Your config file should look something like [this](images/complete-example-config.png) when you are done.

## Docker (Optional)
 - If you haven't taken CS204 or haven't run into Docker, this section is for you. Rubber Duck production line uses Docker to create production ready applications. Knowing how to use it and what is for will bless you as a software engineer.
 - This is going to be a short tutorial on how to get docker working.
 - **Follow the tutorial below to get started. This should take about one hour.**
   - For this video, watch the first 30 minutes of the video and follow along with the [video](https://youtu.be/fqMOX6JJhGo)
   - Follow this [Download Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
   - If you open Docker Desktop, and it is stuck on "Docker Desktop Starting" for more than 5 minutes, then you may need to install an earlier version of [Docker](https://docs.docker.com/desktop/release-notes/#4150)
   - If you are using the [Window 10 edition](images/docker_tutorial_img1.jpg)
   - [Final Instructions](images/docker_tutorial_img2.jpg) and [Docker Hello-World Output Screenshot Description](images/docker_tutorial_img3.jpg)


## AWS CLI & ECR (Optional)
- This section is optional but if you need to access BYU AWS servers please contact Dr. Bean to access.
- You need to send your byu email to him.
- You should be able to use this [link](https://byulogin.awsapps.com/start/#/?tab=accounts) to go there.

# Intro Assignment
The assignment it to create your own discord bot or rubber duck. Follow the instructions posted on this [instructions](https://discord.gg/YGRXPCCT) discord channel to test if everything is running correctly.

## Usage
The bot listens to the configured channel, currently set in the source code as `"duck-pond"`

When a user posts a message to the duck pond, the duck bot 
creates a public thread in response. 

[//]: # (To add a new listening channel, add a file named by the channel in the prompts folder.)
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
  - Your configuration should look something like this
  - [Configuration Image](images/example-configuration.png)

To run on server:
- cd to project folder
- `git pull`
- `poetry install`
- `nohup poetry run python discord_bot.py >> /tmp/duck.log &`

To kill on server:
- `ps -e | python`
- `kill <pid>`

