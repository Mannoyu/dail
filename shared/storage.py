import sqlite3
from contextlib import closing
from pathlib import Path

from shared.models import DailyReport


class Storage:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as conn, conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS reports (
                date TEXT, team TEXT, markdown TEXT, html TEXT,
                PRIMARY KEY(date, team))""")

    def save(self, report: DailyReport) -> None:
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO reports VALUES (?, ?, ?, ?)",
                (
                    report.date.isoformat(),
                    report.team_name,
                    report.markdown,
                    report.html,
                ),
            )

    def get(self, date: str, team: str) -> dict[str, str] | None:
        with closing(sqlite3.connect(self.path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM reports WHERE date=? AND team=?",
                (date, team),
            ).fetchone()
            return dict(row) if row else None
