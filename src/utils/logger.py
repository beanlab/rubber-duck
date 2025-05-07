import logging
from typing import Optional
from colorlog import ColoredFormatter
import os

class DuckLogger:
    def __init__(
        self,
        name: str,
        *,
        log_file: Optional[str] = None,
        level: Optional[int] = None,
        use_colors: bool = True,
    ):
        self.logger = logging.getLogger(name)
        
        # Set level based on DEBUG environment variable or default to INFO
        if level is None:
            level = logging.DEBUG if os.environ.get('DEBUG') == '1' else logging.INFO
            
        self.logger.setLevel(level)

        if not self.logger.handlers:
            # Add color support if needed
            try:
                if use_colors:
                    formatter = ColoredFormatter(
                        '%(log_color)s%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        log_colors={
                            'DEBUG': 'cyan',
                            'INFO': 'green',
                            'WARNING': 'yellow',
                            'ERROR': 'red',
                            'CRITICAL': 'bold_red',
                        }
                    )
                else:
                    formatter = logging.Formatter(
                        '%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S'
                    )
            except ImportError:
                # Fallback if colorlog is not available
                formatter = logging.Formatter(
                    '%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

            if log_file:
                file_formatter = logging.Formatter(
                    '%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(file_formatter)
                self.logger.addHandler(file_handler)

    # Example log methods
    def debug(self, message: str):
        self.logger.debug(message)

    def info(self, message: str):
        self.logger.info(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str):
        self.logger.error(message)

    def critical(self, message: str):
        self.logger.critical(message)

    def exception(self, message: str):
        self.logger.exception(message)
