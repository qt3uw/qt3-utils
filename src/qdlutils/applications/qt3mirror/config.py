"""Load and validate qt3mirror flipper YAML configuration."""
from __future__ import annotations

import importlib.resources
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

N_FLIPPERS = 4


@dataclass(frozen=True)
class FlipperPreset:
    """GUI preset: button label and flipper index → line high (up) or low (down)."""

    label: str
    targets: Tuple[Tuple[int, bool], ...]

    def targets_dict(self) -> Dict[int, bool]:
        return dict(self.targets)


@dataclass(frozen=True)
class Qt3MirrorConfig:
    device: str
    flipper_names: List[str]
    flipper_lines: List[str]
    sync_pulse_low_ms: float
    sync_pulse_high_ms: float
    source_label: str
    presets: Tuple[FlipperPreset, ...]


def _require_mapping(data: Any, path: str) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a mapping, got {type(data).__name__}")
    return data


def _direction_to_bool(value: Any) -> bool:
    if not isinstance(value, str):
        raise ValueError(f"target direction must be a string 'up' or 'down', got {type(value).__name__}")
    v = value.strip().lower()
    if v == "up":
        return True
    if v == "down":
        return False
    raise ValueError(f"target direction must be 'up' or 'down', got {value!r}")


# Used when `presets` is omitted from YAML (custom configs).
_DEFAULT_PRESET_SPECS: List[Dict[str, Any]] = [
    {"label": "White Light", "targets": {"M6": "up", "M8": "up"}},
    {"label": "Camera", "targets": {"M6": "up"}},
    {"label": "SNSPD", "targets": {"M6": "down", "M7": "up"}},
    {"label": "Photodiode", "targets": {"M6": "down", "M7": "down", "M5": "up"}},
    {"label": "Spectrometer", "targets": {"M5": "down", "M6": "down", "M7": "down"}},
]


def _parse_presets(
    raw: Any,
    name_to_index: Dict[str, int],
    path_prefix: str,
) -> Tuple[FlipperPreset, ...]:
    if raw is None:
        entries = _DEFAULT_PRESET_SPECS
    else:
        if not isinstance(raw, list):
            raise ValueError(f"{path_prefix} must be a list or omitted")
        entries = raw

    out: List[FlipperPreset] = []
    for j, entry in enumerate(entries):
        em = _require_mapping(entry, f"{path_prefix}[{j}]")
        label = em.get("label")
        if not label or not isinstance(label, str):
            raise ValueError(f"{path_prefix}[{j}] requires string 'label'")
        targets_raw = em.get("targets")
        tm = _require_mapping(targets_raw, f"{path_prefix}[{j}].targets")
        pairs: List[Tuple[int, bool]] = []
        for name_key, dir_val in tm.items():
            if not isinstance(name_key, str):
                raise ValueError(f"{path_prefix}[{j}].targets keys must be flipper name strings")
            name_key = name_key.strip()
            if name_key not in name_to_index:
                raise ValueError(
                    f"{path_prefix}[{j}].targets: unknown flipper name {name_key!r}; "
                    f"expected one of {sorted(name_to_index)}"
                )
            pairs.append((name_to_index[name_key], _direction_to_bool(dir_val)))
        pairs.sort(key=lambda x: x[0])
        out.append(FlipperPreset(label=label.strip(), targets=tuple(pairs)))
    return tuple(out)


def load_flipper_config(path: Optional[str] = None) -> Qt3MirrorConfig:
    """
    Load flipper layout from a YAML file.

    If ``path`` is None, loads bundled ``qt3mirror_base.yaml``.
    """
    if path:
        p = Path(path).expanduser()
        if not p.is_file():
            raise FileNotFoundError(f"Config not found: {p}")
        with p.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        source_label = str(p.resolve())
    else:
        root = importlib.resources.files("qdlutils.applications.qt3mirror.config_files")
        yaml_path = root.joinpath("qt3mirror_base.yaml")
        with yaml_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        source_label = "qt3mirror_base.yaml (bundled)"

    data = _require_mapping(raw, "root")

    device = data.get("device")
    if not device or not isinstance(device, str):
        raise ValueError("config requires non-empty string key 'device'")

    sync_low = float(data.get("sync_pulse_low_ms", 15.0))
    sync_high = float(data.get("sync_pulse_high_ms", 15.0))
    if sync_low < 0 or sync_high < 0:
        raise ValueError("sync pulse durations must be >= 0")

    flippers = data.get("flippers")
    if not isinstance(flippers, list) or len(flippers) != N_FLIPPERS:
        raise ValueError(f"config requires 'flippers' to be a list of exactly {N_FLIPPERS} entries")

    names: List[str] = []
    lines: List[str] = []
    for i, entry in enumerate(flippers):
        fe = _require_mapping(entry, f"flippers[{i}]")
        name = fe.get("name")
        line = fe.get("line")
        if not name or not isinstance(name, str):
            raise ValueError(f"flippers[{i}] requires string 'name'")
        if not line or not isinstance(line, str):
            raise ValueError(f"flippers[{i}] requires string 'line'")
        names.append(name.strip())
        lines.append(line.strip())

    name_to_index = {n: i for i, n in enumerate(names)}
    presets = _parse_presets(data.get("presets"), name_to_index, "presets")

    return Qt3MirrorConfig(
        device=device.strip(),
        flipper_names=names,
        flipper_lines=lines,
        sync_pulse_low_ms=sync_low,
        sync_pulse_high_ms=sync_high,
        source_label=source_label,
        presets=presets,
    )
