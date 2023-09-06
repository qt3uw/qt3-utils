import logging
import logging.config
from pathlib import Path

import yaml

default_folder = Path.home().joinpath('.qt3-utils', 'logs')


def get_configured_logger(name: str) -> logging.Logger:
    with open('logger_config.yaml', 'r') as f:
        config = yaml.safe_load(f.read())
        config['handlers']['file_handler']['filename'] = \
            f"{default_folder.joinpath(config['handlers']['file_handler']['filename'])}"
        logging.config.dictConfig(config)

    logger = logging.getLogger(name)

    return logger
