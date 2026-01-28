import os
from aiohttp import web
from dotenv import load_dotenv

from botbuilder.core import (
    ActivityHandler,
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import Activity
from openai import OpenAI

# ------------------ ENV ------------------
load_dotenv()

APP_ID = os.getenv("MICROSOFT_APP_ID")
APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ------------------ OPENAI ------------------
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ------------------ BOT ADAPTER ------------------
adapter_settings = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
adapter = BotFrameworkAdapter(adapter_settings)

# ------------------ BOT ------------------
class TeamsBot(ActivityHandler):
    async def on_turn(self, turn_context: TurnContext):
        print("ACTIVITY:", turn_context.activity.type)
        await super().on_turn(turn_context)

    async def on_message_activity(self, turn_context: TurnContext):
        text = TurnContext.remove_recipient_mention(turn_context.activity) or ""
        text = text.strip()

        if not text:
            await turn_context.send_activity("Say something 🙂")
            return

        response = openai_client.responses.create(
            model="gpt-4o-mini",
            input=text,
        )

        reply = response.output_text or "I had nothing to say 🤖"

        await turn_context.send_activity(reply)

bot = TeamsBot()

# ------------------ HTTP HANDLER ------------------
async def messages(req: web.Request) -> web.Response:
    if req.method == "OPTIONS":
        return web.Response(status=200)

    if req.method != "POST":
        return web.Response(status=405)

    if req.content_type != "application/json":
        return web.Response(status=415)

    try:
        body = await req.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON")

    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    async def call_bot(context: TurnContext):
        await bot.on_turn(context)

    await adapter.process_activity(activity, auth_header, call_bot)
    return web.Response(text="ok")

# ------------------ APP ------------------
app = web.Application()
app.router.add_route("*", "/api/messages", messages)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=3978)
