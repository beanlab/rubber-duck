import threading
from flask import Flask, request
import requests
import os

class OAuthServer:
    def __init__(self, bot_instance):
        self.app = Flask(__name__)
        self.bot_instance = bot_instance
        self.app.add_url_rule('/callback', 'callback', self.callback)

    def callback(self):
        """This route will handle the OAuth callback from Canvas."""
        code = request.args.get("code")
        state = request.args.get("state")

        if not code or not state:
            return "Missing code or state", 400

        # Exchange code for token
        token_response = requests.post("https://byu.instructure.com/login/oauth2/token", data={
            "grant_type": "authorization_code",
            "client_id": os.getenv("CLIENT_ID"),
            "client_secret": os.getenv("CLIENT_SECRET"),
            "redirect_uri": os.getenv("REDIRECT_URI"),
            "code": code
        })

        if token_response.status_code != 200:
            return f"Token exchange failed: {token_response.text}", 500

        access_token = token_response.json().get("access_token")

        # Send the token to the bot instance (via an internal method)
        self.bot_instance.receive_token(state, access_token)

        return "✅ Canvas login successful! You can return to Discord."

    def run(self):
        """Start the Flask server in a separate thread."""
        def run_flask():
            self.app.run(debug=True, port=5000, use_reloader=False)  # Disable reloader in production
        thread = threading.Thread(target=run_flask)
        thread.start()

    def stop(self):
        """Shut down the Flask server."""
        print("Shutting down Flask server...")
        func = request.environ.get('werkzeug.server.shutdown')
        if func:
            func()
