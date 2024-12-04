import os

import requests
import time
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("CANVAS_TOKEN")
COURSE_ID = os.getenv("COURSE_ID")
BASE_URL = "https://byu.instructure.com/api/v1"
CANVAS_TOKEN = os.getenv("CANVAS_TOKEN")

class CanvasApi:
    def __init__(self):
        self.canvas_users = {}
        self.last_called = None


    def get_canvas_users(self):
        return self.canvas_users

    def connect_canvas_api(self):
        url = f"{BASE_URL}/courses/{COURSE_ID}/users?include[]=email&include[]=login_id&include[]=enrollments&per_page=100"
        headers = {
            "Authorization": f"Bearer {CANVAS_TOKEN}"
        }

        try:
            while url:
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    users = response.json()
                    for user in users:
                        roles = [enrollment['type'] for enrollment in user.get('enrollments', [])]
                        self.canvas_users[user['login_id']] = user['name'], user['email'], roles
                    if 'next' in response.links:
                        url = response.links['next']['url']
                    else:
                        url = None  # No more pages
                else:
                    print(f"Error: {response.status_code}, {response.text}")
                    break
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")

        self.last_called = time.time()

    def get_last_called(self):
        if self.last_called:
            return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.last_called))
        else:
            return "API has not been called yet."

    def was_called_within_last_hour(self):
        if self.last_called:
            return (time.time() - self.last_called) <= 3600
        return False
