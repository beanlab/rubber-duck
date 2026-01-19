import os
from aiohttp import web
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
    ActivityHandler,
)
from botbuilder.schema import Activity
from openai import OpenAI

# --- OpenAI client ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Bot Framework setup ---
APP_ID = os.getenv("MICROSOFT_APP_ID", "")
APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD", "")

adapter_settings = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
adapter = BotFrameworkAdapter(adapter_settings)


class TeamsAIBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        user_text = turn_context.activity.text or ""

        # Remove @Bot mention
        user_text = TurnContext.remove_recipient_mention(turn_context.activity)
        user_text = user_text.strip()

        if not user_text:
            await turn_context.send_activity("Say something 🙂")
            return

        # --- Call OpenAI ---
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant in Microsoft Teams."},
                {"role": "user", "content": user_text},
            ],
        )

        reply = completion.choices[0].message.content

        await turn_context.send_activity(reply)


bot = TeamsAIBot()


async def messages(req: web.Request) -> web.Response:
    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    async def call_bot(context: TurnContext):
        await bot.on_turn(context)

    await adapter.process_activity(activity, auth_header, call_bot)
    return web.Response(text="ok")


app = web.Application()
app.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=3978)
