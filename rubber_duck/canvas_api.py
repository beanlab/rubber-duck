import os

import canvasapi.course
import requests
import time
from canvasapi import Canvas
from canvasapi.course import Course
from dotenv import load_dotenv

# load_dotenv()
# token = os.getenv("CANVAS_TOKEN")
# COURSE_ID = os.getenv("COURSE_ID")
# BASE_URL = "https://byu.instructure.com/api/v1"
# CANVAS_TOKEN = os.getenv("CANVAS_TOKEN")

#changes methods to private
#add feature from Dr.Bean
#given a course configuration create a canvas dict
#config needs general url,api token,

def _get_course(api_token: str, api_url: str, canvas_course_id: int) -> Course:
    """
    Returns a Canvas Course object for the given API URL, API token, and course ID.

    :param api_url: str: The URL for the Canvas API.
    :param api_token: str: The authentication token for the Canvas API.
    :param canvas_course_id: int: The ID of the Canvas course.
    :return: Course: A Canvas Course object.
    """
    canvas = Canvas(api_url, api_token)
    course: Course = canvas.get_course(canvas_course_id)
    return course

class CanvasApi:
    def __init__(self, config):
        print("Config in CanvasApi:", config)  # Debugging line
        self._courses = {
            guild_id: _get_course(config['token'], config['url'], course_id)
            for guild_id, course_id in config['courses'].items()
        }
        self._cache_timeout = config['cache_timeout']
        self._url = config['url']
        self._token = config['token']
        self.canvas_users = {}
        self.last_called = {}

    def get_canvas_users(self, guild_id):
        if self._is_data_stale(guild_id):
            self._retrieve_users(guild_id)
        return self.canvas_users[guild_id]

    def _retrieve_users(self, guild_id):
        self.canvas_users[guild_id] = {
            user.login_id: (user.name, user.email, user.enrollments)
            for user in self._courses[guild_id].get_enrollments()
        }

        self.last_called[guild_id] = time.time()

    def _is_data_stale(self, guild_id):
        return guild_id not in self.last_called or (self.last_called[guild_id] - time.time() > self._cache_timeout)
