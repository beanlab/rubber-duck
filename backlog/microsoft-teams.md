# Microsoft Teams Bot Parity

Created on: 2026-04-20
Created by: Tyler

## Details

Migrate Discord functionality to Microsoft Teams with a parallel deployment.

- What problem does the feature address?
  - Teams adoption requires a bot experience that matches Discord while keeping student conversations private.
- What is the intent of the feature?
  - Achieve feature parity where possible, with admins retaining access to student conversations.
- What details exist so far about this feature?
  - Discord and Teams servers are both set up simultaneously in the config and in main.py.
  - Bot setup requirements (pending exact permission list):
    - Microsoft 365 account with global admin access.
    - Azure (for bot registration and permissions).
    - Teams (global admin access allows custom Teams apps like our bot).
    - Microsoft env variables (TBD, list exact names + sources once known).
    - Local dev requires a personal domain to reroute messages using Cloudflared.
  - Class organization decision:
    - Each class has its own Team (up to 1,000 private channels, clearer admin separation).
    - Multiple ducks per class use separate posts within a channel.
  - Proposed flow:
    1. Admins create a post in the general channel with instructions for each duck.
    2. User responds to a post, which triggers opening a new conversation in Teams.
  - If we use private channels:
    3. Bot creates a private channel for the user and adds all admins (limited to 1,000).
    4. Archive the channel when closed.
    5. TA review uses a link to the archived channel.
  - If we use DMs:
    3. Bot replies in-channel and directs the user to DMs.
    4. Bot sends a DM indicating a distinct conversation ("========== NEW CONVERSATION ==========").
    5. User interacts in DMs and messages are stored externally.
    6. On close, instruct the user to respond to the general post to start again.
    7. TA review uses a text file of the conversation from storage.
  - Conversation lifecycle:
    - New conversation opens when a user responds to a post in a Team channel.
    - Conversation closes when the user starts a second conversation or when existing close logic fires.
  - Helpful links:
    - https://learn.microsoft.com/en-us/training/modules/teams-toolkit-vsc-create-bot/
    - https://learn.microsoft.com/en-us/microsoftteams/platform/m365-apps/overview?WT.mc_id=m365-84637-cxa&tabs=Android
    - https://www.youtube.com/watch?v=etluT8UC-nw

## Out-of-scope

TBD.

## Dependencies

None identified yet.
