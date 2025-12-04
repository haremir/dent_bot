from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

@dataclass
class Dentist:
    """Diş Hekimi Modeli."""
    
    # Zorunlu Alanlar
    full_name: str
    specialty: str # Örn: "Ortodonti", "Genel Diş Hekimi"
    
    # Opsiyonel Alanlar (Sistem/İletişim)
    id: Optional[int] = field(default=None)
    phone: Optional[str] = field(default=None)
    email: Optional[str] = field(default=None)
    telegram_chat_id: Optional[int] = field(default=None) # Doktor paneli bildirimleri için
    is_active: bool = field(default=True)

    # Çalışma Saatleri ve Slot Ayarları
    working_days: List[str] = field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    start_time: str = field(default="09:00") # HH:MM
    end_time: str = field(default="18:00")   # HH:MM
    break_start: str = field(default="12:00") # Öğle Arası Başlangıcı
    break_end: str = field(default="13:00")   # Öğle Arası Bitişi
    slot_duration: int = field(default=30)  # Dakika cinsinden randevu süresi
    
    # ------------------------------------
    # Metodlar
    # ------------------------------------

    def works_on_day(self, day_name: str) -> bool:
        """Verilen günde çalışıyor mu kontrol eder."""
        return day_name in self.working_days

    def to_dict(self) -> Dict[str, Any]:
        """Dataclass'ı veritabanı/JSON uyumlu bir sözlüğe çevirir."""
        data = self.__dict__.copy()
        # Önemli: working_days listesini virgülle ayrılmış string yap (SQLite için)
        data['working_days'] = ",".join(self.working_days)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Dentist:
        """Sözlükten dataclass örneği oluşturur."""
        data = data.copy()
        
        # Önemli: working_days stringini listeye çevir
        working_days_str = data.pop('working_days', "")
        if isinstance(working_days_str, str) and working_days_str:
            data['working_days'] = [d.strip() for d in working_days_str.split(",")]
        else:
            data['working_days'] = []

        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in field_names}

        return cls(**filtered_data)