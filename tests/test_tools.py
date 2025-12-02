"""
Tests for hotel_bot tools module.

All tool functions are tested here in an organized manner.
"""
import gc
import os
import tempfile
import time

import pytest

from dent_bot.adapters.sqlite_adapter import SQLiteReservationAdapter
from dent_bot.tools import (
    cancel_reservation,
    check_availability,
    create_reservation,
    get_reservation,
    get_room_prices,
    set_adapter,
)


# ============================================================================
# Test Fixtures and Helpers
# ============================================================================

def make_db_url(tmpdir: str) -> str:
    """Create a database URL for testing."""
    db_path = os.path.join(tmpdir, "hotel_bot_test.db")
    return f"sqlite:///{db_path}"


def seed_sample_rooms(db: SQLiteReservationAdapter) -> None:
    rooms = [
        ("Standard 101", 2, 80.0, "available"),
        ("Deluxe 201", 3, 120.0, "available"),
        ("Suite 301", 4, 200.0, "available"),
        ("Economy 001", 1, 60.0, "maintenance"),
    ]
    for name, capacity, price, status in rooms:
        db.create_room(name=name, capacity=capacity, price_per_night=price, status=status)


def setup_test_db():
    """Create and initialize a test database."""
    td = tempfile.TemporaryDirectory()
    db = SQLiteReservationAdapter(make_db_url(td.name))
    db.init()
    seed_sample_rooms(db)
    set_adapter(db)
    return td, db


def cleanup_test_db(td, db):
    """Clean up test database resources."""
    set_adapter(None)
    del db
    gc.collect()
    time.sleep(0.1)
    td.cleanup()


# ============================================================================
# Tests for get_room_prices()
# ============================================================================

class TestGetRoomPrices:
    """Test suite for get_room_prices tool."""

    def test_get_room_prices(self):
        """Test get_room_prices tool function."""
        td, db = setup_test_db()
        try:
            result = get_room_prices()

            # Verify result structure
            assert "rooms" in result
            assert isinstance(result["rooms"], list)
            assert len(result["rooms"]) > 0

            # Verify room structure
            for room in result["rooms"]:
                assert "id" in room
                assert "name" in room
                assert "capacity" in room
                assert "price_per_night" in room
                assert "status" in room
                assert room["status"] == "available"
        finally:
            cleanup_test_db(td, db)

    def test_get_room_prices_only_available(self):
        """Test that get_room_prices only returns available rooms."""
        td, db = setup_test_db()
        try:
            # Mark one room as occupied
            rooms = db.list_rooms()
            if rooms:
                db.update_room_status(rooms[0]["id"], "occupied")

            result = get_room_prices()

            # Verify all returned rooms are available
            for room in result["rooms"]:
                assert room["status"] == "available"
        finally:
            cleanup_test_db(td, db)


# ============================================================================
# Tests for check_availability()
# ============================================================================

class TestCheckAvailability:
    """Test suite for check_availability tool."""

    def test_check_availability(self):
        """Test check_availability tool function."""
        td, db = setup_test_db()
        try:
            result = check_availability(
                check_in="2025-12-01",
                check_out="2025-12-03",
                guests=2
            )

            # Verify result structure
            assert "check_in" in result
            assert "check_out" in result
            assert "guests" in result
            assert "available_rooms" in result
            assert result["check_in"] == "2025-12-01"
            assert result["check_out"] == "2025-12-03"
            assert result["guests"] == 2
            assert isinstance(result["available_rooms"], list)

            # Verify room structure
            for room in result["available_rooms"]:
                assert "id" in room
                assert "name" in room
                assert "capacity" in room
                assert "price_per_night" in room
                assert room["capacity"] >= 2
        finally:
            cleanup_test_db(td, db)

    def test_check_availability_filters_by_capacity(self):
        """Test that check_availability filters rooms by guest capacity."""
        td, db = setup_test_db()
        try:
            # Request room for 5 guests (should filter out smaller rooms)
            result = check_availability(
                check_in="2025-12-01",
                check_out="2025-12-03",
                guests=5
            )

            # Verify all returned rooms can accommodate 5 guests
            for room in result["available_rooms"]:
                assert room["capacity"] >= 5
        finally:
            cleanup_test_db(td, db)

    def test_check_availability_excludes_conflicting_dates(self):
        """Test that check_availability excludes rooms with conflicting reservations."""
        td, db = setup_test_db()
        try:
            rooms = db.list_rooms()
            if not rooms:
                pytest.skip("No rooms available for test")

            first_room = rooms[0]

            # Create a reservation for the room
            db.create_reservation(
                room_id=first_room["id"],
                full_name="Test User",
                check_in="2025-12-01",
                check_out="2025-12-05",
                guests=2,
                phone=None,
                email=None,
            )

            # Check availability for overlapping dates
            result = check_availability(
                check_in="2025-12-02",
                check_out="2025-12-04",
                guests=2
            )

            # Verify the reserved room is not in available_rooms
            available_ids = [r["id"] for r in result["available_rooms"]]
            assert first_room["id"] not in available_ids

            # Check availability for non-overlapping dates
            result2 = check_availability(
                check_in="2025-12-10",
                check_out="2025-12-12",
                guests=2
            )

            # Verify the room is available for non-overlapping dates
            available_ids2 = [r["id"] for r in result2["available_rooms"]]
            assert first_room["id"] in available_ids2
        finally:
            cleanup_test_db(td, db)


# ============================================================================
# Tests for create_reservation()
# ============================================================================

class TestCreateReservation:
    """Test suite for create_reservation tool."""

    def test_create_reservation(self):
        """Test create_reservation tool function."""
        td, db = setup_test_db()
        try:
            rooms = db.list_rooms(only_available=True)
            if not rooms:
                pytest.skip("No available rooms for test")

            first_room = rooms[0]

            result = create_reservation(
                room_id=first_room["id"],
                full_name="John Doe",
                check_in="2025-12-01",
                check_out="2025-12-03",
                guests=2,
                phone="+1234567890",
                email="john@example.com",
                notes="Test reservation"
            )

            # Verify result structure
            assert "success" in result
            assert result["success"] is True
            assert "reservation" in result

            reservation = result["reservation"]
            assert reservation["room_id"] == first_room["id"]
            assert reservation["full_name"] == "John Doe"
            assert reservation["check_in"] == "2025-12-01"
            assert reservation["check_out"] == "2025-12-03"
            assert reservation["guests"] == 2
            assert reservation["phone"] == "+1234567890"
            assert reservation["email"] == "john@example.com"
            assert reservation["notes"] == "Test reservation"
            assert "id" in reservation
            assert reservation["reference_code"].startswith("RSV-")
        finally:
            cleanup_test_db(td, db)

    def test_create_reservation_invalid_room(self):
        """Test create_reservation with invalid room ID."""
        td, db = setup_test_db()
        try:
            result = create_reservation(
                room_id=99999,
                full_name="John Doe",
                check_in="2025-12-01",
                check_out="2025-12-03",
                guests=2,
                phone="+1234567890",
            )

            # Verify error response
            assert "error" in result
            assert "not found" in result["error"].lower()
        finally:
            cleanup_test_db(td, db)

    def test_create_reservation_exceeds_capacity(self):
        """Test create_reservation with more guests than room capacity."""
        td, db = setup_test_db()
        try:
            rooms = db.list_rooms(only_available=True)
            if not rooms:
                pytest.skip("No available rooms for test")

            # Find a room with capacity < 5
            small_room = None
            for room in rooms:
                if room["capacity"] < 5:
                    small_room = room
                    break

            if not small_room:
                pytest.skip("No small room available for test")

            result = create_reservation(
                room_id=small_room["id"],
                full_name="John Doe",
                check_in="2025-12-01",
                check_out="2025-12-03",
                guests=10,  # More than capacity
                phone="+1234567890",
            )

            # Verify error response
            assert "error" in result
            assert "accommodate" in result["error"].lower() or "capacity" in result["error"].lower()
        finally:
            cleanup_test_db(td, db)

    def test_create_reservation_date_conflict(self):
        """Test create_reservation with conflicting dates."""
        td, db = setup_test_db()
        try:
            rooms = db.list_rooms(only_available=True)
            if not rooms:
                pytest.skip("No available rooms for test")

            first_room = rooms[0]

            # Create first reservation
            db.create_reservation(
                room_id=first_room["id"],
                full_name="First User",
                check_in="2025-12-01",
                check_out="2025-12-05",
                guests=2,
                phone=None,
                email=None,
            )

            # Try to create overlapping reservation
            result = create_reservation(
                room_id=first_room["id"],
                full_name="Second User",
                check_in="2025-12-02",
                check_out="2025-12-04",
                guests=2,
                phone="+1234567890",
            )
            # Verify error response
            assert "error" in result
            assert "reserved" in result["error"].lower() or "conflict" in result["error"].lower()
        finally:
            cleanup_test_db(td, db)

    def test_create_reservation_requires_contact_info(self):
        """Ensure at least one contact detail is required."""
        td, db = setup_test_db()
        try:
            rooms = db.list_rooms(only_available=True)
            if not rooms:
                pytest.skip("No available rooms for test")

            first_room = rooms[0]

            result = create_reservation(
                room_id=first_room["id"],
                full_name="John Doe",
                check_in="2025-12-01",
                check_out="2025-12-03",
                guests=2,
            )

            assert "error" in result
            assert "iletişim" in result["error"]
        finally:
            cleanup_test_db(td, db)


# ============================================================================
# Tests for get_reservation()
# ============================================================================

class TestGetReservation:
    """Test suite for get_reservation tool."""

    def test_get_reservation(self):
        """Test get_reservation tool function."""
        td, db = setup_test_db()
        try:
            rooms = db.list_rooms(only_available=True)
            if not rooms:
                pytest.skip("No available rooms for test")

            first_room = rooms[0]

            # Create a reservation
            created = db.create_reservation(
                room_id=first_room["id"],
                full_name="John Doe",
                check_in="2025-12-01",
                check_out="2025-12-03",
                guests=2,
                phone="+1234567890",
                email="john@example.com",
            )

            reservation_id = created["id"]

            result = get_reservation(reservation_id)

            # Verify result structure
            assert "reservation" in result
            reservation = result["reservation"]

            assert reservation["id"] == reservation_id
            assert reservation["room_id"] == first_room["id"]
            assert reservation["full_name"] == "John Doe"
            assert reservation["check_in"] == "2025-12-01"
            assert reservation["check_out"] == "2025-12-03"
            assert reservation["guests"] == 2
            assert reservation["phone"] == "+1234567890"
            assert reservation["email"] == "john@example.com"
            assert reservation["reference_code"].startswith("RSV-")
        finally:
            cleanup_test_db(td, db)

    def test_get_reservation_not_found(self):
        """Test get_reservation with non-existent reservation ID."""
        td, db = setup_test_db()
        try:
            result = get_reservation(99999)

            # Verify error response
            assert "error" in result
            assert "not found" in result["error"].lower()
        finally:
            cleanup_test_db(td, db)


# ============================================================================
# Tests for cancel_reservation()
# ============================================================================

class TestCancelReservation:
    """Test suite for cancel_reservation tool."""

    def test_cancel_reservation(self):
        """Test cancel_reservation tool function."""
        td, db = setup_test_db()
        try:
            rooms = db.list_rooms(only_available=True)
            if not rooms:
                pytest.skip("No available rooms for test")

            first_room = rooms[0]

            # Create a reservation
            created = db.create_reservation(
                room_id=first_room["id"],
                full_name="John Doe",
                check_in="2025-12-01",
                check_out="2025-12-03",
                guests=2,
                phone=None,
                email=None,
            )

            reservation_id = created["id"]

            # Verify reservation exists
            assert db.get_reservation(reservation_id) is not None

            result = cancel_reservation(reservation_id)

            # Verify result structure
            assert "success" in result
            assert result["success"] is True
            assert "message" in result
            assert str(reservation_id) in result["message"]

            # Verify reservation is deleted
            assert db.get_reservation(reservation_id) is None
        finally:
            cleanup_test_db(td, db)

    def test_cancel_reservation_not_found(self):
        """Test cancel_reservation with non-existent reservation ID."""
        td, db = setup_test_db()
        try:
            result = cancel_reservation(99999)

            # Verify error response
            assert "error" in result
            assert "not found" in result["error"].lower()
        finally:
            cleanup_test_db(td, db)


