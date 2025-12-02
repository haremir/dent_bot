
from __future__ import annotations

from typing import Protocol, runtime_checkable, Optional, Dict, Any, List


@runtime_checkable
class ReservationAdapter(Protocol):
    # lifecycle
    def init(self) -> None: ...

    # rooms
    def create_room(self, name: str, capacity: int, price_per_night: float, status: str = "available") -> Dict[str, Any]: ...
    def get_room(self, room_id: int) -> Optional[Dict[str, Any]]: ...
    def list_rooms(self, only_available: bool = False) -> List[Dict[str, Any]]: ...
    def update_room_status(self, room_id: int, status: str) -> bool: ...

    # reservations
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
    ) -> Dict[str, Any]: ...

    def get_reservation(self, reservation_id: int) -> Optional[Dict[str, Any]]: ...
    def list_reservations_for_room(self, room_id: int) -> List[Dict[str, Any]]: ...
    def delete_reservation(self, reservation_id: int) -> bool: ...


