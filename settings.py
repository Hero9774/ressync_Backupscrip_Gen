"""Persistenz der zuletzt benutzten GUI-Einstellungen.

Speichert/lädt alle Eingaben außer dem Passwort (Sicherheit).
Ablage: ~/.config/nas-backup-generator/settings.json
"""
import json
import os
from typing import Any

SETTINGS_DIR  = os.path.expanduser("~/.config/nas-backup-generator")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

# Liste der zu persistierenden tk.Variable-Attribute (auf App-Ebene)
_TK_VAR_FIELDS = [
    # Ziel
    "nas_host", "nas_user", "nas_ssh_port", "ssh_key", "nas_base",
    "log_file", "service_name", "auth_mode", "pass_file",
    # Zeitplan
    "sched_hour", "sched_min", "sched_sec", "sched_freq",
    "sched_wd_single", "sched_dom", "persistent",
    # Aufbewahrung
    "max_snapshots", "dpkg_backup",
    "calc_base_gb", "calc_change_pct",
    # Ausgabe
    "output_dir",
]

# Listen-Attribute (Python-Listen, keine tk.Variables)
_LIST_FIELDS = ["_sources", "_excludes"]


def load() -> dict[str, Any]:
    """Lädt gespeicherte Einstellungen oder {} bei Fehler."""
    if not os.path.isfile(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def save(app) -> None:
    """Persistiert alle relevanten Einstellungen aus dem App-Objekt."""
    data: dict[str, Any] = {}
    for field in _TK_VAR_FIELDS:
        var = getattr(app, field, None)
        if var is not None:
            try:
                data[field] = var.get()
            except Exception:
                pass
    for field in _LIST_FIELDS:
        val = getattr(app, field, None)
        if isinstance(val, list):
            data[field] = list(val)

    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except OSError:
        pass  # Stilles Scheitern: Persistenz ist „nice to have"


def apply_to(app, data: dict[str, Any]) -> None:
    """Wendet geladene Einstellungen auf das App-Objekt an (nach Defaults)."""
    if not data:
        return
    for field in _TK_VAR_FIELDS:
        if field in data:
            var = getattr(app, field, None)
            if var is not None:
                try:
                    var.set(data[field])
                except Exception:
                    pass
    for field in _LIST_FIELDS:
        if field in data and isinstance(data[field], list):
            setattr(app, field, list(data[field]))
