import logging
import logging.config
from pathlib import Path

import yaml

default_folder = Path.home().joinpath('.qt3-utils', 'logs')


# TODO: Updated config file and create a dynamic log formatter depending on the extra title and subtitle values.

def get_configured_logger(name: str) -> logging.Logger:
    with open('logger_config.yaml', 'r') as f:
        config = yaml.safe_load(f.read())
        config['handlers']['file_handler']['filename'] = \
            f"{default_folder.joinpath(config['handlers']['file_handler']['filename'])}"
        logging.config.dictConfig(config)

    logger = logging.getLogger(name)

    return logger


class LoggableMixin:
    def __init__(self, logger=None, title: str = None, subtitle: str = None):
        if logger is None:
            logger = get_configured_logger(self.__class__.__name__)

        # if title is None:
        #     title = ''
        # if subtitle is None:
        #     subtitle = ''

        self._logger = logger
        self._logger_title = title
        self._logger_subtitle = subtitle

    def log(self, message, level=logging.INFO):
        """
        Log messages related to the object.

        Parameters:
            message (str): The message to log.
            level (int, optional): The logging level (default is logging.INFO).
        """
        self._logger.log(
            level,
            message,
            extra={
                'title': self._logger_title,
                'subtitle': self._logger_subtitle
            },
            exc_info=True)
