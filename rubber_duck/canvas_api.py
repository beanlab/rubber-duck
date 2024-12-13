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
        self._courses = {course_id: details for course_id, details in config["courses"].items()}
        self._cache_timeout = config['cache_timeout']
        self._url = None
        self._token = None
        self.canvas_users = {}
        self.last_called = {}

    def first_time(self, guild_id):
        """
        Initializes Canvas data for the given guild ID, preparing it for user retrieval.
        """
        guild_id = str(guild_id)
        if guild_id not in self._courses:
            raise ValueError(f"Guild ID {guild_id} not found in configuration.")

        token_name, url, course_id = self._courses[guild_id].values()

        self._token = os.getenv(token_name)
        if not self._token:
            raise ValueError(f"API token for {token_name} is not set in environment variables.")

        course = _get_course(self._token, url, course_id)
        users = course.get_users()
        self._courses[guild_id] = course

        enrollments = course.get_enrollments()

        for user in users:
            login_id = user.login_id
            user_email = user.email

            user_enrollment = None
            for enrollment in enrollments:
                if enrollment.user_id == user.id:
                    user_enrollment = enrollment.enrollment_state
                    break

            if not user_enrollment:
                user_enrollment = 'unknown'

            self.canvas_users[login_id] = {
                'email': user_email,
                'enrollment': user_enrollment,
                'login_id': login_id
            }
        self._courses[guild_id] = self.canvas_users

    def get_canvas_users(self, guild_id):
        if self._is_data_stale(guild_id):
            self._retrieve_users(guild_id)
        return self.canvas_users[guild_id]

    def _retrieve_users(self, guild_id):
        """
        Retrieves user data for the given guild ID and updates the local cache.
        """
        if guild_id not in self._courses:
            raise ValueError(f"Guild ID {guild_id} not found in courses.")

        course = self._courses[guild_id]

        self.canvas_users[guild_id] = {
            user.user.login_id: (user.user.name, user.user.email, user.enrollments)
            for user in course.get_enrollments(include=["user", "email", "enrollments"])
        }

        self.last_called[guild_id] = time.time()

    def _is_data_stale(self, guild_id):
        return guild_id not in self.last_called or (self.last_called[guild_id] - time.time() > self._cache_timeout)
