import os
import time
from canvasapi import Canvas
from canvasapi.course import Course


def get_course(api_token: str, api_url: str, canvas_course_id: int) -> Course:
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
    def __init__(self, canvas_config, guild_config):
        self._cache_timeout = canvas_config['cache_timeout']
        self._courses = {
            guild_id: _get_course(os.getenv(details['token_name']), details['url'], details['course_id'])
            for guild_id, details in guild_config.items()  # Use guild_config directly
        }
        self.canvas_users = {}  # guild_id -> users
        self.last_called = {}  # guild_id -> timestamp

    def get_canvas_users(self, guild_id):
        if self._is_data_stale(guild_id):
            self._retrieve_users(guild_id)
        return self.canvas_users[guild_id]

    def _retrieve_users(self, guild_id: int):
        """
        Retrieves user data for the given guild ID and updates the local cache.
        """
        guild_id = str(guild_id)
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