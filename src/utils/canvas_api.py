import os
import time
from canvasapi import Canvas
from ..utils.logger import duck_logger

class CanvasApi:
    def __init__(self, server_id: str, canvas_settings: dict):
        self._server_id = server_id
        self._canvas = Canvas(os.environ.get("CANVAS_BYU_URL"), os.environ.get("CANVAS_TOKEN"))
        self._last_update = 0
        self._enrollment_cache = {}
        
        courses_in_server = canvas_settings.get('courses_in_server', {})
        if not courses_in_server:
            raise ValueError(f"No courses configured in settings")
            
        course_id = next(iter(courses_in_server.values()))
        self._course = self._canvas.get_course(course_id)
        self._cache_timeout = canvas_settings.get("cache_timeout", 300)  # Default 5 minutes
        
        # Initial load of data
        self._update_cache()

    def get_user_enrollment(self, net_id: str) -> tuple[str, str] | None:
        """Returns (enrollment_type, section_name) for a given net_id"""
        if time.time() - self._last_update > self._cache_timeout:
            self._update_cache()
            
        return self._enrollment_cache.get(net_id)

    def _update_cache(self):
        """Update the enrollment cache from Canvas"""
        try:
            sections = self._course.get_sections()
            new_cache = {}
            
            for section in sections:
                for enrollment in section.get_enrollments(include=["user"]):
                    if hasattr(enrollment, 'user'):
                        login_id = enrollment.user.get('login_id')
                        if login_id:
                            new_cache[login_id] = (
                                getattr(enrollment, 'type', 'StudentEnrollment'),
                                section.name
                            )
            
            self._enrollment_cache = new_cache
            self._last_update = time.time()
            duck_logger.debug(f"Updated enrollment cache for server {self._server_id}")
            
        except Exception as e:
            duck_logger.error(f"Error updating enrollment cache: {e}")