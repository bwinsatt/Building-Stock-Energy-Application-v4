"""SQLite database for project/building/assessment persistence."""
import json
import os
import sqlite3
from datetime import datetime, timezone


class Database:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.environ.get(
            "DATABASE_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "buildingstock.db")
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def init(self):
        """Create tables if they don't exist."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id          INTEGER PRIMARY KEY,
                    name        TEXT NOT NULL,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS buildings (
                    id              INTEGER PRIMARY KEY,
                    project_id      INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    address         TEXT,
                    building_input  JSON,
                    utility_data    JSON,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS assessments (
                    id          INTEGER PRIMARY KEY,
                    building_id INTEGER REFERENCES buildings(id) ON DELETE CASCADE,
                    result      JSON,
                    calibrated  BOOLEAN,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def _row_to_dict(self, row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        d = dict(row)
        for key in ("building_input", "utility_data", "result"):
            if key in d and d[key] is not None:
                d[key] = json.loads(d[key])
        if "calibrated" in d and d["calibrated"] is not None:
            d["calibrated"] = bool(d["calibrated"])
        return d

    # --- Projects ---

    def create_project(self, name: str) -> dict:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO projects (name) VALUES (?)", (name,)
            )
            return self._row_to_dict(
                conn.execute("SELECT * FROM projects WHERE id = ?", (cursor.lastrowid,)).fetchone()
            )

    def list_projects(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY created_at").fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_project(self, project_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row is None:
                return None
            project = self._row_to_dict(row)
            buildings = conn.execute(
                "SELECT * FROM buildings WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            ).fetchall()
            project["buildings"] = [self._row_to_dict(b) for b in buildings]
            return project

    def delete_project(self, project_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    # --- Buildings ---

    def create_building(
        self, project_id: int, address: str,
        building_input: dict, utility_data: dict | None = None,
    ) -> dict:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO buildings (project_id, address, building_input, utility_data) VALUES (?, ?, ?, ?)",
                (project_id, address, json.dumps(building_input),
                 json.dumps(utility_data) if utility_data else None),
            )
            return self._row_to_dict(
                conn.execute("SELECT * FROM buildings WHERE id = ?", (cursor.lastrowid,)).fetchone()
            )

    # --- Assessments ---

    def save_assessment(self, building_id: int, result: dict, calibrated: bool) -> dict:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO assessments (building_id, result, calibrated) VALUES (?, ?, ?)",
                (building_id, json.dumps(result), calibrated),
            )
            return self._row_to_dict(
                conn.execute("SELECT * FROM assessments WHERE id = ?", (cursor.lastrowid,)).fetchone()
            )

    def get_assessments(self, building_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM assessments WHERE building_id = ? ORDER BY created_at",
                (building_id,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
