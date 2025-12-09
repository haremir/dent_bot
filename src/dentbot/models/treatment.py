from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class Treatment:
    """Diş Tedavi Modeli (Hizmet/Ürün)."""
    
    # Zorunlu Alanlar
    name: str # Örn: "Diş Temizliği", "Dolgu"
    duration_minutes: int # Tedavinin tahmini süresi (Slot hesaplaması için KRİTİK)

    # Opsiyonel Alanlar
    id: Optional[int] = field(default=None)
    price: Optional[float] = field(default=None)
    description: Optional[str] = field(default=None)
    
    # İş Akışı Ayarları
    requires_approval: bool = field(default=True) # Bu randevu için doktor onayı gerekli mi?
    is_active: bool = field(default=True)

    # ------------------------------------
    # Metodlar
    # ------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Dataclass'ı veritabanı/JSON uyumlu bir sözlüğe çevirir."""
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Treatment:
        """Sözlükten dataclass örneği oluşturur."""
        
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in field_names}

        return cls(**filtered_data)