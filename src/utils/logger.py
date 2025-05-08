import logging

# Set the Format
formatter = logging.Formatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set up the Handler. This sends the logs to the console.
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)


# Set up the logger
duck_logger = logging.getLogger("duck")
duck_logger.setLevel(logging.WARNING)
duck_logger.addHandler(console_handler)