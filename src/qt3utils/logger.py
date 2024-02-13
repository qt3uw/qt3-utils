import logging
import logging.config
from pathlib import Path

import yaml

default_folder = Path.home().joinpath('.qt3-utils', 'logs')


# TODO: Updated config file and create a dynamic log formatter depending on the extra title and subtitle values.

def get_configured_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    This function loads a YAML configuration file for logging
    and configures a logger instance with the specified name.
    It ensures that the file-based log handler stores logs
    in a default folder located in the user's home directory.

    Parameters
    ----------
    name: str
        The name of the logger.

    Returns
    -------
    logging.Logger:
        A configured logger instance.

    Notes
    -----
    The function reads a YAML configuration file named
    'logger_config.yaml' to configure the logger.
    The configuration file should contain settings
    for handlers, log levels, and other logging parameters.

    Example
    -------
    To obtain a configured logger instance for a module:

    >>> lgr = get_configured_logger(__name__)
    >>> lgr.info("This is an informational log message.")
    >>> lgr.log(logging.WARN, "This is a warning.")


    """
    with open('logger_config.yaml', 'r') as f:
        config = yaml.safe_load(f.read())
        config['handlers']['file_handler']['filename'] = \
            f"{default_folder.joinpath(config['handlers']['file_handler']['filename'])}"
        logging.config.dictConfig(config)

    logger = logging.getLogger(name)

    return logger


class LoggableMixin:
    """
    The LoggableMixin class is designed to be used as a mixin
    in other classes to provide logging capabilities.

    It allows those classes to log messages related to their
    operations using a logger instance.
    """
    def __init__(self, logger=None, title: str = None, subtitle: str = None):
        """
        Parameters
        ----------
        logger: logging.Logger, optional
            The logger instance to use for logging.
            Defaults to None, which creates a new
            logger based on the object class name.
        title: str, optional
            The title to be used in log messages (default is None).
        subtitle: str, optional
            The subtitle to be used in log messages (default is None).
        """

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

        Parameters
        ----------
        message: str
            The message to log.
        level: int, optional
            The logging level (default is logging.INFO).
        """
        self._logger.log(
            level,
            message,
            extra={
                'title': self._logger_title,
                'subtitle': self._logger_subtitle
            },
            exc_info=True)
