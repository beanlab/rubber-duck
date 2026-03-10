# Teams Bot — Full Codebase Context

## Project Overview
- Python Microsoft Teams bot using Bot Framework SDK v4 (4.15.0)
- aiohttp server running on localhost:3000
- Cloudflare tunnel exposes localhost:3000 as https://demo.tryrevi.com/api/messages
- Azure Bot Service: `Rubber_Duck` in resource group `RubberDuckGroup`
- Azure AD App: SingleTenant, msaAppId `62e73df3-9e1c-4e5e-9951-e1141a9d586b`, tenantId `273a73f7-921d-4d22-9dd0-decd342a5b4a`
- OpenAI integration: uses AsyncOpenAI client, maintains per-conversation history (last 20 messages)

---

## app.py

```python
import traceback

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import BotFrameworkAdapterSettings, BotFrameworkAdapter, TurnContext
from botbuilder.schema import Activity

from config import DefaultConfig
from bot import TeamsBot

CONFIG = DefaultConfig()

SETTINGS = BotFrameworkAdapterSettings(
    app_id=CONFIG.APP_ID,
    app_password=CONFIG.APP_PASSWORD,
    channel_auth_tenant=CONFIG.APP_TENANT_ID,
)
ADAPTER = BotFrameworkAdapter(SETTINGS)


async def on_error(context: TurnContext, error: Exception):
    print(f"\n[on_turn_error] unhandled error: {error}", flush=True)
    traceback.print_exc()
    await context.send_activity("The bot encountered an error. Please try again.")


ADAPTER.on_turn_error = on_error

BOT = TeamsBot()


async def messages(req: Request) -> Response:
    if "application/json" not in req.headers.get("Content-Type", ""):
        return Response(status=415, text="Unsupported media type")

    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    invoke_response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)

    if invoke_response:
        return json_response(data=invoke_response.body, status=invoke_response.status)

    return Response(status=201)


async def health(req: Request) -> Response:
    return json_response({"status": "ok"})


APP = web.Application()
APP.router.add_post("/api/messages", messages)
APP.router.add_get("/health", health)

if __name__ == "__main__":
    print(f"Bot server starting on http://0.0.0.0:{CONFIG.PORT}")
    print(f"Messaging endpoint (local):  http://localhost:{CONFIG.PORT}/api/messages")
    print(f"Messaging endpoint (public): https://demo.tryrevi.com/api/messages")
    web.run_app(APP, host="0.0.0.0", port=CONFIG.PORT)
```

---

## bot.py

```python
import re

from openai import AsyncOpenAI
from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.schema import ChannelAccount

from config import DefaultConfig

CONFIG = DefaultConfig()

_openai_client = AsyncOpenAI(api_key=CONFIG.OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "You are a helpful assistant inside Microsoft Teams. "
    "Be concise and professional. Format responses using Markdown when appropriate."
)

_conversation_history: dict[str, list[dict]] = {}


class TeamsBot(ActivityHandler):

    async def on_message_activity(self, turn_context: TurnContext):
        raw = turn_context.activity.text or ""
        # Teams wraps @mentions in <at>Name</at> HTML tags — strip them reliably
        text = re.sub(r"<at>[^<]*</at>", "", raw).strip()

        if not text:
            return

        await self._handle_message(turn_context, text)

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    MessageFactory.text(
                        "Hello! I'm your AI assistant powered by OpenAI. "
                        "Ask me anything!"
                    )
                )

    async def _handle_message(self, turn_context: TurnContext, text: str):
        conversation_id = turn_context.activity.conversation.id

        if conversation_id not in _conversation_history:
            _conversation_history[conversation_id] = []

        _conversation_history[conversation_id].append(
            {"role": "user", "content": text}
        )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + \
                   _conversation_history[conversation_id][-20:]

        try:
            result = await _openai_client.chat.completions.create(
                model=CONFIG.OPENAI_MODEL,
                messages=messages,
            )
            response = result.choices[0].message.content

            _conversation_history[conversation_id].append(
                {"role": "assistant", "content": response}
            )

        except Exception as e:
            print(f"[OpenAI error] {e}", flush=True)
            response = "Sorry, I couldn't get a response from OpenAI right now. Please try again."

        await turn_context.send_activity(MessageFactory.text(response))
```

---

## config.py

```python
import os
from dotenv import load_dotenv

load_dotenv()


class DefaultConfig:
    PORT: int = int(os.environ.get("PORT", 3000))
    APP_ID: str = os.environ.get("MicrosoftAppId", "")
    APP_PASSWORD: str = os.environ.get("MicrosoftAppPassword", "")
    APP_TENANT_ID: str = os.environ.get("MicrosoftAppTenantId", "")
    APP_TYPE: str = os.environ.get("MicrosoftAppType", "SingleTenant")
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
```

---

## requirements.txt

```
botbuilder-core==4.15.0
botframework-connector==4.15.0
aiohttp==3.9.3
python-dotenv==1.0.1
openai>=1.0.0
```

---

## deploy.sh

```bash
#!/bin/bash
set -e

# -------------------------------------------------------
# Teams Bot - Setup & Run Script
# -------------------------------------------------------
# What this script does:
#   1. Validates your .env file exists and is filled in
#   2. Creates a Python virtual environment (if not present)
#   3. Installs Python dependencies
#   4. Updates the Azure Bot Service messaging endpoint to
#      https://demo.tryrevi.com/api/messages
#   5. Enables the Microsoft Teams channel on the bot
#   6. Starts the bot server on localhost:3000
#
# Prerequisites:
#   - Python 3.10+
#   - Azure CLI installed and logged in  (az login)
#   - Cloudflare tunnel already running  (localhost:3000 → demo.tryrevi.com)
#   - .env file configured               (cp .env.example .env)
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh <bot-name>
#
# To find your bot name:
#   az resource list --resource-group RubberDuckGroup --output table
# -------------------------------------------------------

RESOURCE_GROUP="RubberDuckGroup"
ENDPOINT="https://demo.tryrevi.com/api/messages"
BOT_NAME="${1:-}"

# ---- Validate bot name ----
if [ -z "$BOT_NAME" ]; then
    echo ""
    echo "ERROR: Bot name is required."
    echo ""
    echo "Usage:  ./deploy.sh <bot-name>"
    echo ""
    echo "To find your bot name, run:"
    echo "  az resource list --resource-group $RESOURCE_GROUP --output table"
    echo ""
    exit 1
fi

# ---- Validate .env ----
if [ ! -f ".env" ]; then
    echo ""
    echo "ERROR: .env file not found."
    echo "Run:  cp .env.example .env"
    echo "Then fill in MicrosoftAppId, MicrosoftAppPassword, and MicrosoftAppTenantId."
    echo ""
    exit 1
fi

# Check that the placeholder values have been replaced
if grep -q "YOUR_APP_ID_HERE\|YOUR_APP_SECRET_HERE\|YOUR_TENANT_ID_HERE" .env; then
    echo ""
    echo "ERROR: .env still contains placeholder values."
    echo "Open .env and replace YOUR_APP_ID_HERE, YOUR_APP_SECRET_HERE,"
    echo "and YOUR_TENANT_ID_HERE with your real Azure AD credentials."
    echo ""
    exit 1
fi

# ---- Check Python ----
echo "==> Checking Python version..."
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not installed or not on PATH."
    exit 1
fi
python3 --version

# ---- Virtual environment ----
echo "==> Setting up virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "    Created .venv"
else
    echo "    .venv already exists"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# ---- Install dependencies ----
echo "==> Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "    Done"

# ---- Update Azure Bot endpoint ----
echo "==> Checking Azure CLI login..."
if ! az account show > /dev/null 2>&1; then
    echo "ERROR: Not logged in to Azure CLI."
    echo "Run:  az login"
    exit 1
fi

echo "==> Updating Azure Bot '$BOT_NAME' endpoint in '$RESOURCE_GROUP'..."
az bot update \
    --resource-group "$RESOURCE_GROUP" \
    --name "$BOT_NAME" \
    --endpoint "$ENDPOINT"
echo "    Endpoint set to: $ENDPOINT"

echo "==> Enabling Microsoft Teams channel..."
SUBSCRIPTION=$(az account show --query id -o tsv)
az rest \
    --method PUT \
    --url "https://management.azure.com/subscriptions/${SUBSCRIPTION}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.BotService/botServices/${BOT_NAME}/channels/MsTeamsChannel?api-version=2022-09-15" \
    --body '{"location":"global","properties":{"channelName":"MsTeamsChannel","properties":{"isEnabled":true}}}' \
    > /dev/null
echo "    Teams channel enabled"

# ---- Start the bot ----
echo ""
echo "========================================================"
echo "  Bot server starting on http://localhost:3000"
echo "  Public endpoint: $ENDPOINT"
echo "========================================================"
echo ""
python3 app.py
```

---

## update_endpoint.sh

```bash
#!/bin/bash
set -e

# -------------------------------------------------------
# Updates the messaging endpoint of your existing
# Azure Bot Service to point at the Cloudflare tunnel.
#
# Usage:
#   chmod +x update_endpoint.sh
#   ./update_endpoint.sh <bot-name>
# -------------------------------------------------------

RESOURCE_GROUP="RubberDuckGroup"
ENDPOINT="https://demo.tryrevi.com/api/messages"

# --- Set your bot name here ---
BOT_NAME="${1:-}"

if [ -z "$BOT_NAME" ]; then
    echo "Usage: ./update_endpoint.sh <bot-name>"
    echo ""
    echo "To find your bot name, run:"
    echo "  az resource list --resource-group $RESOURCE_GROUP --output table"
    exit 1
fi

echo "==> Checking Azure CLI login..."
az account show > /dev/null 2>&1 || { echo "Not logged in. Run: az login"; exit 1; }

echo "==> Updating bot '$BOT_NAME' in resource group '$RESOURCE_GROUP'..."
az bot update \
    --resource-group "$RESOURCE_GROUP" \
    --name "$BOT_NAME" \
    --endpoint "$ENDPOINT"

echo ""
echo "Done! Messaging endpoint is now:"
echo "  $ENDPOINT"
```

---

## manifest/manifest.json

```json
{
  "$schema": "https://developer.microsoft.com/en-us/json-schemas/teams/v1.16/MicrosoftTeams.schema.json",
  "manifestVersion": "1.16",
  "version": "1.0.0",
  "id": "62e73df3-9e1c-4e5e-9951-e1141a9d586b",
  "packageName": "com.yourcompany.teamsbot",
  "developer": {
    "name": "Your Company",
    "websiteUrl": "https://yourwebsite.com",
    "privacyUrl": "https://yourwebsite.com/privacy",
    "termsOfUseUrl": "https://yourwebsite.com/terms"
  },
  "name": {
    "short": "TeamsBot",
    "full": "My Teams Bot"
  },
  "description": {
    "short": "A Teams bot that responds to messages",
    "full": "A Microsoft Teams bot built with Bot Framework SDK v4 that responds to user messages."
  },
  "icons": {
    "color": "color.png",
    "outline": "outline.png"
  },
  "accentColor": "#0078D4",
  "bots": [
    {
      "botId": "62e73df3-9e1c-4e5e-9951-e1141a9d586b",
      "scopes": ["personal", "team", "groupchat"],
      "supportsFiles": false,
      "isNotificationOnly": false,
      "commandLists": [
        {
          "scopes": ["personal", "team", "groupchat"],
          "commands": [
            {
              "title": "help",
              "description": "Show available commands"
            },
            {
              "title": "hello",
              "description": "Say hello to the bot"
            },
            {
              "title": "info",
              "description": "Show bot information"
            }
          ]
        }
      ]
    }
  ],
  "permissions": ["identity", "messageTeamMembers"],
  "validDomains": ["demo.tryrevi.com", "token.botframework.com"]
}
```

---

## .env (template — do not commit real values)

```
MicrosoftAppId=<your-azure-ad-app-id>
MicrosoftAppPassword=<your-client-secret>
MicrosoftAppTenantId=<your-tenant-id>
MicrosoftAppType=SingleTenant
PORT=3000
OPENAI_API_KEY=<your-openai-api-key>
OPENAI_MODEL=gpt-4o-mini
```
