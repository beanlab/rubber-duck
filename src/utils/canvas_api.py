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
    try:
        course: Course = canvas.get_course(canvas_course_id)
    except Exception as e:
        duck_logger.error(f"Error fetching course {canvas_course_id}: {e}")
        raise
    return course

class CanvasApi:
    def __init__(self,
                 server_id: str,
                 canvas_settings: dict
                 ):
        self._server_id = server_id
        self._canvas_settings = canvas_settings
        self._courses = {}
        self.cache_timeout = canvas_settings["cache_timeout"] # 7 days
        self.canvas_users = {}  # guild_id -> users
        self.last_called = {}  # guild_id -> timestamp
        self._canvas_token = os.environ.get("CANVAS_TOKEN")
        self._api_url = os.environ.get("BYU_CANVAS_URL")

    def __call__(self):
        server_id = self._server_id  # Use the stored server_id
        
        # Check if course is not in the cache
        if server_id not in self._courses:
            duck_logger.debug(f"Canvas API for guild '{server_id}' not found - fetching course from API")

            # Get course from Canvas using settings
            canvas_course_ids = list(self._canvas_settings.get('courses_in_server', {}).values())

            for course_id in canvas_course_ids:
                self._courses[course_id] = get_course(self._canvas_token, self._api_url, course_id)

                # Initialize the user cache for the server
                self._populate_users(course_id)

                duck_logger.debug(f"Canvas API for guild '{server_id}' initialized with course ID {course_id}")

        else:
            duck_logger.debug(f"Canvas API for guild '{server_id}' already exists - using cached course")
        

    def get_canvas_users(self, guild_id):
        if self._is_data_stale(guild_id):
            self._populate_users(guild_id)
        return self.canvas_users[guild_id]

    def _populate_users(self, course_id: str):
        """
        Retrieves user data for the given course ID and updates the local cache.
        """
        if course_id not in self._courses:
            raise ValueError("Course not found in courses Cache.")

        course = self._courses[course_id]
        
        try:
            # Get enrollments from the course
            enrollments = list(course.get_enrollments(include=["user", "email", "enrollments"]))
            
            # Process enrollments based on the structure we observed in the debug log
            user_dict = {}
            for enrollment in enrollments:
                # Based on the debug log, we know enrollment.user is a dictionary
                if hasattr(enrollment, 'user') and isinstance(enrollment.user, dict):
                    user = enrollment.user
                    login_id = user.get('login_id')
                    if login_id:
                        user_dict[login_id] = (
                            user.get('name', 'Unknown'),
                            user.get('email', f"{login_id}@byu.edu"),
                            enrollment.type if hasattr(enrollment, 'type') else 'Unknown'
                        )
            
            # Store the user dictionary
            self.canvas_users[self._server_id] = user_dict
            duck_logger.debug(f"Retrieved {len(user_dict)} users for course")
            
        except Exception as e:
            duck_logger.error(f"Error retrieving users for course {course_id}: {str(e)}")
            # Initialize with empty dict to prevent further errors
            self.canvas_users[self._server_id] = {}

        self.last_called[self._server_id] = time.time()

    def _is_data_stale(self, server_id):
        return server_id not in self.last_called or (time.time() - self.last_called[server_id] > self.cache_timeout)