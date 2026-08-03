"""Configurable, safer file storage for Railway deployments."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

import inspection_bot as bot

log = logging.getLogger(__name__)


def _atomic_json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def install_runtime_config() -> None:
    data_dir = Path(os.getenv("DATA_DIR", "/app")).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)

    bot.BASE_DIR = data_dir
    bot.SESSIONS_DIR = data_dir / "sessions"
    bot.PHOTOS_DIR = data_dir / "photos"
    bot.REPORTS_DIR = data_dir / "reports"
    for directory in (bot.SESSIONS_DIR, bot.PHOTOS_DIR, bot.REPORTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    template_override = os.getenv("TEMPLATE_PATH")
    bot.TEMPLATE_PATH = (
        Path(template_override).expanduser()
        if template_override
        else Path(__file__).parent / "Template.docx"
    )
    bot.DB_PATH = data_dir / "projects.json"

    seed_db = Path(__file__).parent / "projects.json"
    if not bot.DB_PATH.exists() and seed_db.exists() and seed_db.resolve() != bot.DB_PATH.resolve():
        bot.DB_PATH.write_text(seed_db.read_text(encoding="utf-8"), encoding="utf-8")

    def load_db() -> dict:
        for path in (bot.DB_PATH, seed_db):
            if not path.exists():
                continue
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                log.exception("Could not read project database from %s", path)
        return {"inspection_types": [], "projects": []}

    def save_db(database: dict) -> None:
        _atomic_json_write(bot.DB_PATH, database)

    def session_path(chat_id: int) -> Path:
        return bot.SESSIONS_DIR / f"{chat_id}.json"

    def load_session(chat_id: int) -> dict:
        path = session_path(chat_id)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.exception("Could not read session %s", path)
            return {}

    def save_session(chat_id: int, data: dict) -> None:
        _atomic_json_write(session_path(chat_id), data)

    def clear_session(chat_id: int) -> None:
        try:
            session_path(chat_id).unlink()
        except FileNotFoundError:
            pass

    bot.load_db = load_db
    bot.save_db = save_db
    bot.get_projects = lambda: load_db().get("projects", [])
    bot.get_inspection_types = lambda: load_db().get("inspection_types", [])
    bot.session_path = session_path
    bot.load_session = load_session
    bot.save_session = save_session
    bot.clear_session = clear_session

    log.info("Runtime data directory: %s", data_dir)
