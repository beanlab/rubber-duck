import os
import time

from canvasapi import Canvas
from canvasapi.course import Course

from ..utils.logger import duck_logger


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
    def __init__(self):
        self._courses = {}
        self.cache_timeout = 604800 # 7 days
        self.canvas_users = {}  # guild_id -> users
        self.last_called = {}  # guild_id -> timestamp
        self._canvas_token = os.environ.get("CANVAS_TOKEN")
        self._api_url = os.environ.get("BYU_CANVAS_API_URL")

    def __call__(self, server_id: int, canvas_settings: dict):
        # @TODO: figure out how to do it by channel id for servers like physics.
        server_id = str(server_id)  # Convert to string for consistency
        
        # Check if course is not in the cache
        if server_id not in self._courses:
            duck_logger.info(f"Canvas API for guild '{server_id}' not found - fetching course from API")

            # Get course from Canvas using settings
            canvas_course_ids:list = canvas_settings.get('courses_in_server').values()

            for course_id in canvas_course_ids:
                self._courses[course_id] = get_course(server_id, self._api_url, course_id)
            
            # Initialize the user cache for the server

        else:
            duck_logger.debug(f"Canvas API for guild '{server_id}' already exists - using cached course")
        

    def get_canvas_users(self, guild_id):
        if self._is_data_stale(guild_id):
            self._retrieve_users(guild_id)
        return self.canvas_users[guild_id]

    def _retrieve_users(self, server_id: str):
        """
        Retrieves user data for the given guild ID and updates the local cache.
        """
        server_id = server_id
        if server_id not in self._courses:
            raise ValueError(f"Guild ID {server_id} not found in courses.")

        course = self._courses[server_id]

        self.canvas_users[server_id] = {
            user.user.login_id: (user.user.name, user.user.email, user.enrollments)
            for user in course.get_enrollments(include=["user", "email", "enrollments"])
        }

        self.last_called[server_id] = time.time()

    def _is_data_stale(self, server_id):
        return server_id not in self.last_called or (self.last_called[server_id] - time.time() > self._cache_timeout)