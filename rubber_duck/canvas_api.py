import os

import requests
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("CANVAS_TOKEN")
COURSE_ID = os.getenv("COURSE_ID")
BASE_URL = "https://byu.instructure.com/api/v1"

class canvas_api:
    def __init__(self):
        self.canvas_users = {}

    def get_canvas_users(self):
        return self.canvas_users

    def _get_canvas_users(self, API_TOKEN=None):
        url = f"{BASE_URL}/courses/{COURSE_ID}/users?include[]=email&include[]=login_id&include[]=enrollments&per_page=100"
        headers = {
            "Authorization": f"Bearer {API_TOKEN}"
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

