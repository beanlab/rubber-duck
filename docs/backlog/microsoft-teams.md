# Overview

- Migrate Discord functionality to Microsoft Teams with a parallel deployment
- Discord and Teams servers are both set up simultaneously in the config and in main.py
- Goal is feature parity with Discord where possible, while keeping student conversations private to admins

## Setting up the Bot

- Microsoft 365 account with global admin access
- Need Azure
    - This is how to set your own bot
    - Make sure to give it all permissions so it can listen to channels and not just its own DMs
    - Use VSCode's Teams Toolkit extension to make the manifest.json, etc.
- Need Teams (global admin access allows for custom teams apps like our bot)
- Need Microsoft env variables:
    - *fill out later*
- For running locally:
    - Need personal domain to reroute messages using Cloudflared
      - Teams > Bot Framework > Domain > Local Host

#### Helpful Links

- [Bot Setup Learning Module](https://learn.microsoft.com/en-us/training/modules/teams-toolkit-vsc-create-bot/)
- [Microsoft 365 Bot Documentation](https://learn.microsoft.com/en-us/microsoftteams/platform/m365-apps/overview?WT.mc_id=m365-84637-cxa&tabs=Android)
- [Cloudflared Instruction Video](https://www.youtube.com/watch?v=etluT8UC-nw)

## Remaining Decisions

- **DMs or Private Channels?**
    - The private channel limit was 30, but it's been upgraded to 1,000
    - Is storing 1,000 previous chats enough storage? If not, we might need to do DMs or get tricky with how we use
      channels
    - How will conversations be reviewed by TAs if we use DMs?
- Each class has its own Team
    - Rationale: each Team supports up to 1,000 private channels, and it keeps admin responsibilities separated
- For classes with multiple ducks like stats and eventually cs110, use separate posts within a channel

## Proposed Flow

1. Admins create a post in the general channel with instructions on how to use each duck (each post is similar to the
   separate channels in discord)
2. User responds to a post (just like a user can send a message in the discord channels)
    - This response is the trigger to open a new conversation in Teams

#### If we use private channels:

3. Bot creates a private channel for the user, and adds all the admins to it, exactly the same as a private thread in
   discord, but we are limited to 1,000 of these
4. Archives the channel when closed
5. TA review is done through providing a link to the archived channel

#### If we use DMs:

3. Bot replies to the user, telling them to go to their DMs
    - This is instead of creating a thread within the channel since Teams doesn't allow private threads
    - Setting up a private channel would work, but Teams limits us to 30 of those and it would get really noisy
4. Bot sends a DM to user indicating that it is a distinct conversation from any previous they could have had
    - "========== NEW CONVERSATION ===========" etc.
5. User interacts with the bot in their DMs, and we store all the messages externally
    - Alternatively, we could store their messages in another separate storage channel specifically for that, creating a
      public thread for the admins to view via a link to a specific message
6. On a conversation close, we include "to begin again, respond to the post in the general channel again" etc.
7. TA review is done by sending a text file of the conversation from our storage

## Conversation Lifecycle

- New conversation opens when a user responds to a post in a Team channel
- Conversation closes when the user starts a second conversation or when the existing close logic fires
