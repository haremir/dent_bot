
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


class SQLiteReservationAdapter:
    def __init__(self, db_url: str):
        # Expecting format sqlite:///path
        if db_url.startswith("sqlite:///"):
            self.db_path = db_url.replace("sqlite:///", "")
        else:
            self.db_path = db_url
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    capacity INTEGER NOT NULL,
                    price_per_night REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'available',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS reservations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    full_name TEXT NOT NULL,
                    check_in TEXT NOT NULL,
                    check_out TEXT NOT NULL,
                    guests INTEGER NOT NULL,
                    phone TEXT,
                    email TEXT,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(room_id) REFERENCES rooms(id)
                )
                """
            )
            conn.commit()

    # ---------- Rooms CRUD ----------
    def create_room(self, name: str, capacity: int, price_per_night: float, status: str = "available") -> Dict[str, Any]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO rooms (name, capacity, price_per_night, status) VALUES (?, ?, ?, ?)",
                (name, capacity, price_per_night, status),
            )
            room_id = cur.lastrowid
            conn.commit()
            return self.get_room(room_id) or {"id": room_id}

    def get_room(self, room_id: int) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM rooms WHERE id = ?", (room_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_rooms(self, only_available: bool = False) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.cursor()
            if only_available:
                cur.execute("SELECT * FROM rooms WHERE status = 'available' ORDER BY id")
            else:
                cur.execute("SELECT * FROM rooms ORDER BY id")
            return [dict(r) for r in cur.fetchall()]

    def update_room_status(self, room_id: int, status: str) -> bool:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE rooms SET status = ? WHERE id = ?", (status, room_id))
            conn.commit()
            return cur.rowcount > 0

    # ---------- Reservations CRUD ----------
    def create_reservation(
        self,
        room_id: int,
        full_name: str,
        check_in: str,
        check_out: str,
        guests: int,
        phone: Optional[str],
        email: Optional[str],
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO reservations (room_id, full_name, check_in, check_out, guests, phone, email, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (room_id, full_name, check_in, check_out, guests, phone, email, notes),
            )
            reservation_id = cur.lastrowid
            conn.commit()
            return self.get_reservation(reservation_id) or {"id": reservation_id}

    def get_reservation(self, reservation_id: int) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_reservations_for_room(self, room_id: int) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM reservations WHERE room_id = ? ORDER BY id DESC", (room_id,))
            return [dict(r) for r in cur.fetchall()]

    def delete_reservation(self, reservation_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
            conn.commit()
            return cur.rowcount > 0

