import os
import time

from canvasapi import Canvas
from canvasapi.course import Course

from ..utils.logger import duck_logger


class CanvasApi:
    def __init__(self,
                 server_id: str,
                 canvas_settings: dict
                 ):
        self._server_id = server_id
        self._canvas_settings = canvas_settings
        self.cache_timeout = canvas_settings["cache_timeout"]
        self._courses = {}
        self.section_enrollments = {}
        self.last_called = {}
        self._canvas_token = os.environ.get("CANVAS_TOKEN")
        self._api_url = os.environ.get("BYU_CANVAS_URL")
        self.canvas = None

        server_id = self._server_id  # Use the stored server_id
        
        # Check if course is not in the cache
        if server_id not in self._courses:
            duck_logger.debug(f"Canvas API for guild '{server_id}' not found - fetching course from API")

            # Get course from Canvas using settings
            canvas_course_ids = list(self._canvas_settings.get('courses_in_server', {}).values())

            for course_id in canvas_course_ids:
                course = self._get_course(self._canvas_token, self._api_url, course_id)
                self._courses[course_id] = course

                # Initialize the section enrollments for the server
                self._populate_section_enrollments(course_id)
                duck_logger.debug(f"Canvas API for guild '{server_id}' initialized with course ID {course_id}")

        else:
            duck_logger.debug(f"Canvas API for guild '{server_id}' already exists - using cached course")

    def _get_course(self, api_token: str, api_url: str, canvas_course_id: int) -> Course:
        """
        Returns a Canvas Course object for the given API URL, API token, and course ID.

        :param api_url: str: The URL for the Canvas API.
        :param api_token: str: The authentication token for the Canvas API.
        :param canvas_course_id: int: The ID of the Canvas course.
        :return: Course: A Canvas Course object.
        """
        self.canvas = Canvas(api_url, api_token)
        try:
            course: Course = self.canvas.get_course(canvas_course_id)
        except Exception as e:
            duck_logger.error(f"Error fetching course {canvas_course_id}: {e}")
            raise
        return course

    def get_canvas_users(self, guild_id):
        """
        Returns a flattened dictionary of all users across all sections.
        Format: {net_id: (name, email, enrollment_type)}
        """
        if self._is_data_stale(guild_id):
            course_id = list(self._canvas_settings.get('courses_in_server', {}).values())[0]
            self._populate_section_enrollments(course_id)
        
        # Flatten section enrollments into the format expected by the registration workflow
        users_dict = {}
        for section_data in self.section_enrollments[self._server_id].values():
            for user_info in section_data['enrollments'].values():
                net_id = user_info['login_id']
                users_dict[net_id] = (
                    user_info['name'],
                    user_info['email'],
                    user_info['enrollment_type']
                )
        return users_dict

    def _populate_section_enrollments(self, course_id: int):
        """
        Retrieves section and enrollment data for the given course ID and updates the local cache.
        """
        if course_id not in self._courses:
            raise ValueError(f"Course ID {course_id} not found in cache.")

        course = self._courses[course_id]
        section_data = {}

        try:
            sections = course.get_sections()
            for section in sections:
                section_number = section.name
                section_data[section_number] = {
                    'id': section.id,
                    'sis_section_id': getattr(section, 'sis_section_id', None),
                    'enrollments': {}
                }
                
                # Get enrollments for this section
                enrollments = section.get_enrollments(include=["user", "email"])
                for enrollment in enrollments:
                    if hasattr(enrollment, 'user') and isinstance(enrollment.user, dict):
                        user = enrollment.user
                        login_id = user.get('login_id')
                        if login_id:
                            section_data[section_number]['enrollments'][login_id] = {
                                'name': user.get('name', 'Unknown'),
                                'email': user.get('email', f"{login_id}@byu.edu"),
                                'enrollment_type': getattr(enrollment, 'type', 'StudentEnrollment'),
                                'login_id': login_id
                            }

            self.section_enrollments[self._server_id] = section_data
            self.last_called[self._server_id] = time.time()
            duck_logger.debug(f"Retrieved section enrollments for course {course_id}")

        except Exception as e:
            duck_logger.error(f"Error retrieving section enrollments for course {course_id}: {str(e)}")
            self.section_enrollments[self._server_id] = {}
            self.last_called[self._server_id] = time.time()

    def get_course_sections(self, course_id: int = None):
        """
        Returns section information from the cached section enrollments.
        """
        if self._server_id not in self.section_enrollments:
            if course_id is None:
                course_id = list(self._canvas_settings.get('courses_in_server', {}).values())[0]
            self._populate_section_enrollments(course_id)

        sections = []
        for section_number, data in self.section_enrollments[self._server_id].items():
            sections.append({
                'id': data['id'],
                'name': section_number,
                'sis_section_id': data['sis_section_id']
            })
        return sections

    def get_section_enrollments(self, course_id: int) -> dict:
        """
        Returns a dictionary mapping section numbers to their enrolled students and their enrollment types.
        Format: {section_number: {student_name: enrollment_type}}
        """
        if course_id not in self._courses:
            raise ValueError(f"Course ID {course_id} not found in cache.")

        course = self._courses[course_id]
        section_enrollments = {}

        try:
            sections = course.get_sections()
            for section in sections:
                section_number = section.name
                section_enrollments[section_number] = {}
                
                # Get enrollments for this section
                enrollments = section.get_enrollments(include=["user"])
                for enrollment in enrollments:
                    if hasattr(enrollment, 'user') and isinstance(enrollment.user, dict):
                        user = enrollment.user
                        student_name = user.get('name', 'Unknown')
                        enrollment_type = getattr(enrollment, 'type', 'StudentEnrollment')
                        section_enrollments[section_number][student_name] = enrollment_type

            return section_enrollments

        except Exception as e:
            duck_logger.error(f"Error fetching section enrollments for course {course_id}: {e}")
            return {}

    def _is_data_stale(self, server_id: str) -> bool:
        """
        Checks if the cached data for a server is stale and needs to be refreshed.
        Returns True if:
        1. No data exists for the server
        2. Last update was more than cache_timeout seconds ago
        """
        if (
            server_id not in self.last_called or
            server_id not in self.section_enrollments 
        ):
            return True

        time_since_update = time.time() - self.last_called[server_id]
        return time_since_update > self.cache_timeout