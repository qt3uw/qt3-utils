"""Load and merge shared YAML fragments used by multiple applications."""

from __future__ import annotations

import importlib.resources
from typing import Any, Dict

import yaml

CONFIG_FILES_PACKAGE = 'qt3utils.config_files'
SHARED_POSITIONERS_FILENAME = 'qt3_positioners_shared.yaml'


def merge_shared_positioners_into_app_config(config: Dict[str, Any]) -> None:
    """
    Merge Microstage / Piezo* blocks from package `qt3_positioners_shared.yaml`
    into the first (and only expected) top-level application key of `config`.
    """
    if not config:
        return
    app_name = next(iter(config))
    root = config[app_name]
    try:
        path = importlib.resources.files(CONFIG_FILES_PACKAGE).joinpath(SHARED_POSITIONERS_FILENAME)
    except (ModuleNotFoundError, FileNotFoundError):
        return
    if not path.is_file():
        return
    with path.open('r', encoding='utf-8') as f:
        shared = yaml.safe_load(f)
    if not shared:
        return
    for key, value in shared.items():
        root[key] = value
