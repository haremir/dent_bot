from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, ClassVar
import uuid

@dataclass
class Appointment:
    """Diş Kliniği Randevu Modeli."""

    # Zorunlu Alanlar
    dentist_id: int
    patient_name: str
    patient_phone: str
    patient_email: str
    appointment_date: str  # YYYY-MM-DD formatında string
    time_slot: str         # HH:MM formatında string
    treatment_type: str    # Örn: "Dolgu", "Kontrol"
    duration_minutes: int  # Tedavinin tahmini süresi

    # Opsiyonel Alanlar
    id: Optional[int] = field(default=None)
    notes: Optional[str] = field(default=None)
    patient_chat_id: Optional[int] = field(default=None) # ⭐ KRİTİK: Hasta Telegram Chat ID'si eklendi

    # Durum ve Zaman Bilgileri (Sınıf değişkenleri)
    STATUS_PENDING: ClassVar[str] = "pending"
    STATUS_APPROVED: ClassVar[str] = "approved"
    STATUS_COMPLETED: ClassVar[str] = "completed"
    STATUS_CANCELLED: ClassVar[str] = "cancelled"
    
    status: str = field(default=STATUS_PENDING)
    created_at: Optional[datetime] = field(default_factory=datetime.now)

    # ------------------------------------
    # Metodlar
    # ------------------------------------

    def get_reference_code(self) -> str:
        """'APT-000123' formatında referans kodu üretir."""
        if self.id is not None:
            return f"APT-{self.id:06d}"
        return f"TEMP-{uuid.uuid4().hex[:6].upper()}"

    def is_pending(self) -> bool:
        return self.status == self.STATUS_PENDING

    def is_approved(self) -> bool:
        return self.status == self.STATUS_APPROVED

    def is_completed(self) -> bool:
        return self.status == self.STATUS_COMPLETED

    def is_cancelled(self) -> bool:
        return self.status == self.STATUS_CANCELLED

    def to_dict(self) -> Dict[str, Any]:
        data = self.__dict__.copy()
        if isinstance(data.get('created_at'), datetime):
            data['created_at'] = data['created_at'].isoformat()
        
        for key in list(data.keys()):
            if key.startswith('STATUS_'):
                data.pop(key)
                
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Appointment:
        data = data.copy()
        created_at_str = data.get('created_at')
        if created_at_str and isinstance(created_at_str, str):
            try:
                data['created_at'] = datetime.fromisoformat(created_at_str)
            except ValueError:
                data['created_at'] = None
                
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in field_names}

        return cls(**filtered_data)