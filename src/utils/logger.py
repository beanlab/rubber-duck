import logging
from logging.handlers import TimedRotatingFileHandler
from quest.utils import quest_logger

# Set the Format
formatter = logging.Formatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set up the Handler. This sends the logs to the console.
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Timed Rotating File Handler
file_handler = TimedRotatingFileHandler(
    filename='logs/duck.log',
    when='midnight',         # Rotate daily at midnight
    interval=1,
    backupCount=2,           # Keep 2 days of logs
    encoding='utf-8'
)
file_handler.setFormatter(formatter)

# Set up the loggers
duck_logger = logging.getLogger("duck")
duck_logger.setLevel(logging.WARNING)
duck_logger.addHandler(console_handler)
duck_logger.addHandler(file_handler)

# Configure the imported quest logger to use the same handlers
quest_logger.addHandler(console_handler)
quest_logger.addHandler(file_handler)