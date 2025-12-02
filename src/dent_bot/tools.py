from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, Optional

from dent_bot.adapters.base import ReservationAdapter
from dent_bot.config import get_config

# Global adapter instance
_adapter: Optional[ReservationAdapter] = None


def _with_reference_code(reservation: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Ensure reservation dict contains a human friendly reference code."""
    if not reservation:
        return reservation
    if "reference_code" not in reservation and reservation.get("id") is not None:
        reservation["reference_code"] = f"RSV-{reservation['id']:06d}"
    return reservation


def _extract_reservation_id(reservation_id: Any) -> int:
    """
    Extract integer ID from reservation_id parameter.
    Handles both integer IDs and RSV-XXXXXX format strings.
    """
    if isinstance(reservation_id, int):
        return reservation_id
    
    if isinstance(reservation_id, str):
        # Handle RSV-000005 format
        if reservation_id.startswith("RSV-"):
            try:
                return int(reservation_id.split("-")[1])
            except (IndexError, ValueError):
                raise ValueError(f"Invalid reservation ID format: {reservation_id}")
        # Try direct conversion
        try:
            return int(reservation_id)
        except ValueError:
            raise ValueError(f"Invalid reservation ID: {reservation_id}")
    
    raise ValueError(f"Reservation ID must be int or str, got {type(reservation_id)}")


def get_adapter() -> ReservationAdapter:
    """
    Get or create the database adapter instance from config.
    
    Adapter is created via config.create_adapter() which ensures
    each tenant/hotel uses its own database configuration.
    
    Returns:
        ReservationAdapter: Database adapter instance
    """
    global _adapter
    if _adapter is None:
        # ⭐ DEĞİŞTİ: Config'ten adapter oluştur
        config = get_config()
        _adapter = config.create_adapter()
    return _adapter


def set_adapter(adapter: ReservationAdapter) -> None:
    """
    Set a custom adapter instance (useful for testing).
    
    Args:
        adapter: Adapter instance to use globally
    """
    global _adapter
    _adapter = adapter


def tool(func: Callable) -> Callable:
    """Decorator to mark a function as a tool."""
    func._is_tool = True
    func._tool_name = func.__name__
    func._tool_description = func.__doc__ or ""
    return func


def _dates_overlap(
    check_in1: str, check_out1: str, check_in2: str, check_out2: str
) -> bool:
    """Check if two date ranges overlap."""
    d1_in = datetime.strptime(check_in1, "%Y-%m-%d")
    d1_out = datetime.strptime(check_out1, "%Y-%m-%d")
    d2_in = datetime.strptime(check_in2, "%Y-%m-%d")
    d2_out = datetime.strptime(check_out2, "%Y-%m-%d")
    
    # Overlap if: d1_in < d2_out and d2_in < d1_out
    return d1_in < d2_out and d2_in < d1_out


def _validate_date_format(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def _validate_phone(phone: str) -> bool:
    digits = [c for c in phone if c.isdigit()]
    return len(digits) >= 10

def _validate_email(email: str) -> bool:
    return "@" in email and "." in email


@tool
def get_room_prices() -> str:
    """
    Get prices for all available rooms.
    
    Returns:
        Formatted string with room information and prices.
    """
    adapter = get_adapter()
    rooms = adapter.list_rooms(only_available=True)
    
    if not rooms:
        return "Mevcut oda bulunmamaktadır."
    
    result = "Mevcut Odalar:\n"
    for room in rooms:
        result += f"\n• {room['name']}\n"
        result += f"  Kapasite: {room['capacity']} kişi\n"
        result += f"  Fiyat: ₺{room['price_per_night']}/gece\n"
    
    return result


@tool
def check_availability(
    check_in: str, check_out: str, guests: int
) -> str:
    """
    Check room availability for given dates and guest count.
    
    Args:
        check_in: Check-in date (YYYY-MM-DD)
        check_out: Check-out date (YYYY-MM-DD)
        guests: Number of guests
    
    Returns:
        Formatted string with available rooms or error message.
    """
    if not _validate_date_format(check_in):
        return f"❌ Hata: Geçersiz giriş tarihi formatı. YYYY-MM-DD şeklinde giriniz."
    if not _validate_date_format(check_out):
        return f"❌ Hata: Geçersiz çıkış tarihi formatı. YYYY-MM-DD şeklinde giriniz."
    adapter = get_adapter()
    
    all_rooms = adapter.list_rooms(only_available=True)
    suitable_rooms = [r for r in all_rooms if r["capacity"] >= guests]
    
    available_rooms = []
    for room in suitable_rooms:
        reservations = adapter.list_reservations_for_room(room["id"])
        
        has_conflict = False
        for res in reservations:
            if _dates_overlap(check_in, check_out, res["check_in"], res["check_out"]):
                has_conflict = True
                break
        
        if not has_conflict:
            available_rooms.append({
                "id": room["id"],
                "name": room["name"],
                "capacity": room["capacity"],
                "price_per_night": room["price_per_night"],
            })
    
    if not available_rooms:
        return f"❌ {check_in} - {check_out} tarihleri arasında {guests} kişi için uygun oda bulunmamaktadır."
    
    result = f"Uygun Odalar ({check_in} - {check_out}):\n"
    for room in available_rooms:
        result += f"\n• {room['name']} (ID: {room['id']})\n"
        result += f"  Kapasite: {room['capacity']} kişi\n"
        result += f"  Fiyat: ₺{room['price_per_night']}/gece\n"
    
    return result


@tool
def create_reservation(
    room_id: int,
    full_name: str,
    check_in: str,
    check_out: str,
    guests: int,
    phone: str,
    email: str,
    notes: Optional[str] = None,
) -> str:
    """
    Create a new reservation.
    
    Args:
        room_id: Room ID
        full_name: Guest full name
        check_in: Check-in date (YYYY-MM-DD)
        check_out: Check-out date (YYYY-MM-DD)
        guests: Number of guests
        phone: Phone number
        email: Email address
        notes: Optional notes
    
    Returns:
        Formatted string with reservation details or error message.
    """
    if not _validate_date_format(check_in):
        return f"❌ Hata: Geçersiz giriş tarihi formatı. YYYY-MM-DD şeklinde giriniz."
    if not _validate_date_format(check_out):
        return f"❌ Hata: Geçersiz çıkış tarihi formatı. YYYY-MM-DD şeklinde giriniz."
    if not _validate_phone(phone):
        return "❌ Hata: Geçersiz telefon numarası. Lütfen en az 10 haneli bir numara giriniz."
    if not _validate_email(email):
        return "❌ Hata: Geçersiz e-posta adresi. Lütfen geçerli bir e-posta giriniz."
    adapter = get_adapter()

    if not phone or not phone.strip():
        return "❌ Hata: Telefon numarası zorunludur. Lütfen geçerli bir telefon numarası sağlayınız."
    
    if not email or not email.strip():
        return "❌ Hata: E-posta adresi zorunludur. Lütfen geçerli bir e-posta sağlayınız."
    
    room = adapter.get_room(room_id)
    if not room:
        return f"❌ Hata: ID {room_id} ile oda bulunamadı."
    
    if room["status"] != "available":
        return f"❌ Hata: Oda {room_id} müsait değil (Durum: {room['status']})"
    
    if room["capacity"] < guests:
        return f"❌ Hata: Oda {room_id} sadece {room['capacity']} kişi alabilir, {guests} kişi istendi."
    
    reservations = adapter.list_reservations_for_room(room_id)
    for res in reservations:
        if _dates_overlap(check_in, check_out, res["check_in"], res["check_out"]):
            return f"❌ Hata: Oda {room_id} istenilen tarihler için zaten rezerve edilmiş."
    
    reservation = adapter.create_reservation(
        room_id=room_id,
        full_name=full_name,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        phone=phone.strip(),
        email=email.strip(),
        notes=notes,
    )
    _with_reference_code(reservation)
    
    result = "Rezervasyon başarıyla oluşturuldu!\n"
    result += f"\nReferans Kodu: {reservation['reference_code']}\n"
    result += f"Misafir: {reservation['full_name']}\n"
    result += f"Oda: {room['name']} (ID: {room_id})\n"
    result += f"Giriş: {reservation['check_in']}\n"
    result += f"Çıkış: {reservation['check_out']}\n"
    result += f"Kişi Sayısı: {reservation['guests']}\n"
    result += f"Telefon: {phone.strip()}\n"
    result += f"E-posta: {email.strip()}\n"
    if notes:
        result += f"Notlar: {notes}\n"
    
    return result


@tool
def update_reservation(
    reservation_id: Any,
    room_id: Optional[int] = None,
    full_name: Optional[str] = None,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    guests: Optional[int] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    """
    Update an existing reservation.
    
    Args:
        reservation_id: Reservation ID (integer or RSV-XXXXXX format)
        room_id: New room ID (optional)
        full_name: New guest name (optional)
        check_in: New check-in date (optional, YYYY-MM-DD)
        check_out: New check-out date (optional, YYYY-MM-DD)
        guests: New guest count (optional)
        phone: New phone number (optional)
        email: New email address (optional)
        notes: New notes (optional)
    
    Returns:
        Formatted string with updated reservation details or error message.
    """
    adapter = get_adapter()
    
    # Extract reservation ID
    try:
        res_id = _extract_reservation_id(reservation_id)
    except ValueError as e:
        return f"❌ Hata: {str(e)}"
    
    # Get existing reservation
    existing = adapter.get_reservation(res_id)
    if not existing:
        return f"❌ Hata: ID {res_id} ile rezervasyon bulunamadı."
    
    # Prepare updated fields (keep existing if not provided)
    new_room_id = room_id if room_id is not None else existing["room_id"]
    new_full_name = full_name if full_name is not None else existing["full_name"]
    new_check_in = check_in if check_in is not None else existing["check_in"]
    new_check_out = check_out if check_out is not None else existing["check_out"]
    new_guests = guests if guests is not None else existing["guests"]
    new_phone = phone.strip() if phone is not None else existing.get("phone", "")
    new_email = email.strip() if email is not None else existing.get("email", "")
    new_notes = notes if notes is not None else existing.get("notes")
    
    # Validate dates if provided
    if check_in and not _validate_date_format(check_in):
        return f"❌ Hata: Geçersiz giriş tarihi formatı. YYYY-MM-DD şeklinde giriniz."
    if check_out and not _validate_date_format(check_out):
        return f"❌ Hata: Geçersiz çıkış tarihi formatı. YYYY-MM-DD şeklinde giriniz."
    
    # Validate phone and email if provided
    if phone and not _validate_phone(phone):
        return "❌ Hata: Geçersiz telefon numarası. Lütfen en az 10 haneli bir numara giriniz."
    if email and not _validate_email(email):
        return "❌ Hata: Geçersiz e-posta adresi. Lütfen geçerli bir e-posta giriniz."
    
    # Check room availability and capacity
    room = adapter.get_room(new_room_id)
    if not room:
        return f"❌ Hata: ID {new_room_id} ile oda bulunamadı."
    
    if room["status"] != "available":
        return f"❌ Hata: Oda {new_room_id} müsait değil (Durum: {room['status']})"
    
    if room["capacity"] < new_guests:
        return f"❌ Hata: Oda {new_room_id} sadece {room['capacity']} kişi alabilir, {new_guests} kişi istendi."
    
    # ⭐ ÖNEMLİ: Tarih çakışması kontrolü - KENDİ REZERVASYONUNU HARIÇ TUT
    reservations = adapter.list_reservations_for_room(new_room_id)
    for res in reservations:
        # Kendi rezervasyonumuzu atla
        if res["id"] == res_id:
            continue
        
        # Diğer rezervasyonlarla çakışma kontrolü
        if _dates_overlap(new_check_in, new_check_out, res["check_in"], res["check_out"]):
            return f"❌ Hata: Oda {new_room_id} bu tarihler için başka bir rezervasyonla çakışıyor."
    
    # Update reservation
    updated = adapter.update_reservation(
        reservation_id=res_id,
        room_id=new_room_id,
        full_name=new_full_name,
        check_in=new_check_in,
        check_out=new_check_out,
        guests=new_guests,
        phone=new_phone,
        email=new_email,
        notes=new_notes,
    )
    
    if not updated:
        return f"❌ Hata: Rezervasyon {res_id} güncellenemedi."
    
    _with_reference_code(updated)
    
    result = "Rezervasyon başarıyla güncellendi!\n"
    result += f"\nReferans Kodu: {updated['reference_code']}\n"
    result += f"Misafir: {updated['full_name']}\n"
    result += f"Oda: {room['name']} (ID: {new_room_id})\n"
    result += f"Giriş: {updated['check_in']}\n"
    result += f"Çıkış: {updated['check_out']}\n"
    result += f"Kişi Sayısı: {updated['guests']}\n"
    if updated.get('phone'):
        result += f"Telefon: {updated['phone']}\n"
    if updated.get('email'):
        result += f"E-posta: {updated['email']}\n"
    if updated.get('notes'):
        result += f"Notlar: {updated['notes']}\n"
    
    return result


@tool
def get_reservation(reservation_id: Any) -> str:
    """
    Get reservation details by ID.
    
    Args:
        reservation_id: Reservation ID (integer or RSV-XXXXXX format)
    
    Returns:
        Formatted string with reservation details or error message.
    """
    adapter = get_adapter()
    
    try:
        res_id = _extract_reservation_id(reservation_id)
    except ValueError as e:
        return f"❌ Hata: {str(e)}"
    
    reservation = adapter.get_reservation(res_id)
    _with_reference_code(reservation)
    
    if not reservation:
        return f"❌ Hata: ID {res_id} ile rezervasyon bulunamadı."
    
    result = "Rezervasyon Detayları:\n"
    result += f"\nReferans Kodu: {reservation['reference_code']}\n"
    result += f"Misafir: {reservation['full_name']}\n"
    result += f"Oda ID: {reservation['room_id']}\n"
    result += f"Giriş: {reservation['check_in']}\n"
    result += f"Çıkış: {reservation['check_out']}\n"
    result += f"Kişi Sayısı: {reservation['guests']}\n"
    if reservation.get('phone'):
        result += f"Telefon: {reservation['phone']}\n"
    if reservation.get('email'):
        result += f"E-posta: {reservation['email']}\n"
    if reservation.get('notes'):
        result += f"Notlar: {reservation['notes']}\n"
    
    return result


@tool
def cancel_reservation(reservation_id: Any) -> str:
    """
    Cancel a reservation by ID.
    
    Args:
        reservation_id: Reservation ID (integer or RSV-XXXXXX format)
    
    Returns:
        Formatted string with success status or error message.
    """
    adapter = get_adapter()
    
    try:
        res_id = _extract_reservation_id(reservation_id)
    except ValueError as e:
        return f"❌ Hata: {str(e)}"
    
    reservation = adapter.get_reservation(res_id)
    if not reservation:
        return f"❌ Hata: ID {res_id} ile rezervasyon bulunamadı."
    
    success = adapter.delete_reservation(res_id)
    
    if success:
        return f"✅ Rezervasyon {res_id} başarıyla iptal edilmiştir."
    else:
        return f"❌ Hata: Rezervasyon {res_id} iptal edilemedi."