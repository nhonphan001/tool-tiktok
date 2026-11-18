import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import db  # noqa: E402
from app.config import settings  # noqa: E402





def test_old_default_prices_removed(tmp_path):
    import sqlite3

    path = tmp_path / "old2.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany("INSERT INTO app_settings VALUES(?,?)",
                     [("gemini_price_input", "0.3"), ("gemini_price_output", "2.5"), ("usd_vnd_rate", "26000.0")])
    conn.commit()
    conn.close()
    old = settings.database_path
    settings.database_path = str(path)
    db.reset_connection()
    try:
        s = db.load_settings()
        assert "gemini_price_input" not in s and "gemini_price_output" not in s and s["usd_vnd_rate"] == "26000.0"
    finally:
        db.reset_connection()
        settings.database_path = old
