import gc
import os
import tempfile
import time

from dent_bot.adapters.sqlite_adapter import SQLiteReservationAdapter


def make_db_url(tmpdir: str) -> str:
    db_path = os.path.join(tmpdir, "hotel_bot_test.db")
    return f"sqlite:///{db_path}"


def test_sqlite_adapter_crud_flow():
    with tempfile.TemporaryDirectory() as td:
        db = SQLiteReservationAdapter(make_db_url(td))

        try:
            # init schema and sample data
            db.init()
            rooms_to_create = [
                ("Standard 101", 2, 80.0, "available"),
                ("Deluxe 201", 3, 120.0, "available"),
                ("Suite 301", 4, 200.0, "available"),
                ("Economy 001", 1, 60.0, "maintenance"),
            ]
            for args in rooms_to_create:
                db.create_room(*args)

            # rooms list and first available
            rooms = db.list_rooms()
            assert len(rooms) >= 4
            first_room = rooms[0]

            # create reservation
            res = db.create_reservation(
                room_id=first_room["id"],
                full_name="Test User",
                check_in="2025-11-20",
                check_out="2025-11-22",
                guests=2,
                phone=None,
                email=None,
            )
            assert isinstance(res["id"], int)

            # get + list
            fetched = db.get_reservation(res["id"])
            assert fetched is not None
            lst = db.list_reservations_for_room(first_room["id"])
            assert any(r["id"] == res["id"] for r in lst)

            # update room status
            ok = db.update_room_status(first_room["id"], "occupied")
            assert ok is True
        finally:
            # Windows'ta SQLite bağlantılarının kapanması için cleanup
            del db
            gc.collect()
            time.sleep(0.1)  # Windows'ta dosya kilidinin serbest bırakılması için kısa bekleme



