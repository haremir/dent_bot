from __future__ import annotations

import sqlite3
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from dentbot.exceptions import DatabaseError

logger = logging.getLogger(__name__)

class SQLiteAppointmentAdapter:
    """SQLite veritabanı için tam kapsamlı randevu ve klinik veri adaptörü."""
    
    def __init__(self, db_url: str):
        # Format: sqlite:///path
        if db_url.startswith("sqlite:///"):
            self.db_path = db_url.replace("sqlite:///", "")
        else:
            self.db_path = db_url
            
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"SQLiteAdapter başlatıldı. Veritabanı yolu: {self.db_path}")

    def _conn(self) -> sqlite3.Connection:
        """Veritabanı bağlantısını döndürür ve row_factory'yi ayarlar."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logger.error(f"Veritabanı bağlantı hatası: {e}")
            raise DatabaseError(f"Veritabanına bağlanılamadı: {e}") from e

    # ------------------------------------
    # Lifecycle
    # ------------------------------------
    def init(self) -> None:
        """Tabloları eksiksiz oluşturur."""
        logger.info("Veritabanı tabloları kontrol ediliyor/oluşturuluyor...")
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                
                # 1. DENTIST Tablosu
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dentists (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        full_name TEXT NOT NULL,
                        specialty TEXT NOT NULL,
                        phone TEXT,
                        email TEXT,
                        telegram_chat_id INTEGER,
                        working_days TEXT NOT NULL, 
                        start_time TEXT NOT NULL,    
                        end_time TEXT NOT NULL,      
                        break_start TEXT,
                        break_end TEXT,
                        slot_duration INTEGER NOT NULL DEFAULT 30,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # 2. TREATMENT Tablosu
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS treatments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        duration_minutes INTEGER NOT NULL,
                        price REAL,
                        description TEXT,
                        requires_approval INTEGER NOT NULL DEFAULT 1,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # 3. APPOINTMENT Tablosu
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS appointments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dentist_id INTEGER NOT NULL,
                        patient_name TEXT NOT NULL,
                        patient_phone TEXT NOT NULL,
                        patient_email TEXT NOT NULL,
                        appointment_date TEXT NOT NULL, 
                        time_slot TEXT NOT NULL,        
                        treatment_type TEXT NOT NULL,   
                        duration_minutes INTEGER NOT NULL,
                        notes TEXT,
                        status TEXT NOT NULL DEFAULT 'pending',
                        patient_chat_id INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(dentist_id) REFERENCES dentists(id)
                    )
                    """
                )
                conn.commit()
                logger.info("Tablo başlatma işlemi başarıyla tamamlandı.")
        except sqlite3.Error as e:
            logger.error(f"Tablo başlatma sırasında SQLite hatası: {e}")
            raise DatabaseError(f"Tablo başlatma hatası: {e}") from e

    # ------------------------------------
    # Yardımcı Metodlar
    # ------------------------------------
    def _get_by_id(self, table_name: str, id_value: int) -> Optional[Dict[str, Any]]:
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute(f"SELECT * FROM {table_name} WHERE id = ?", (id_value,))
                row = cur.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"{table_name} tablosundan ID:{id_value} çekilirken hata: {e}")
            return None
            
    def _list_all(self, table_name: str, where_clause: Optional[str] = None, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                query = f"SELECT * FROM {table_name}"
                if where_clause:
                    query += f" WHERE {where_clause}"
                query += " ORDER BY id DESC"
                cur.execute(query, params or ())
                return [dict(r) for r in cur.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"{table_name} listelenirken hata: {e}")
            return []

    # ------------------------------------
    # Dentist CRUD
    # ------------------------------------
    def create_dentist(self, data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Yeni doktor oluşturuluyor: {data.get('full_name')}")
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                fields = ', '.join(data.keys())
                placeholders = ', '.join('?' * len(data))
                values = tuple(data.values())
                cur.execute(f"INSERT INTO dentists ({fields}) VALUES ({placeholders})", values)
                dentist_id = cur.lastrowid
                conn.commit()
                return self._get_by_id('dentists', dentist_id) or {"id": dentist_id}
        except sqlite3.Error as e:
            logger.error(f"Doktor oluşturma hatası: {e}")
            raise DatabaseError(f"Doktor oluşturulamadı: {e}")

    def get_dentist(self, dentist_id: int) -> Optional[Dict[str, Any]]:
        return self._get_by_id('dentists', dentist_id)

    def list_dentists(self, is_active: Optional[bool] = True) -> List[Dict[str, Any]]:
        where = "is_active = ?" if is_active is not None else None
        params = (1,) if is_active is True else (0,) if is_active is False else None
        return self._list_all('dentists', where, params)
        
    def update_dentist(self, dentist_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not data: return self.get_dentist(dentist_id)
        logger.info(f"Doktor ID:{dentist_id} güncelleniyor: {list(data.keys())}")
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
                values = tuple(data.values()) + (dentist_id,)
                cur.execute(f"UPDATE dentists SET {set_clause} WHERE id = ?", values)
                conn.commit()
                return self.get_dentist(dentist_id)
        except sqlite3.Error as e:
            logger.error(f"Doktor güncelleme hatası: {e}")
            return None

    def update_dentist_chat_id(self, dentist_id: int, chat_id: int) -> Optional[Dict[str, Any]]:
        """Doktorun Telegram Chat ID'sini kaydeder."""
        return self.update_dentist(dentist_id, {"telegram_chat_id": chat_id})

    def delete_dentist(self, dentist_id: int) -> bool:
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM dentists WHERE id = ?", (dentist_id,))
                conn.commit()
                return cur.rowcount > 0
        except sqlite3.Error:
            return False

    # ------------------------------------
    # Treatment CRUD
    # ------------------------------------
    def create_treatment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Yeni tedavi ekleniyor: {data.get('name')}")
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                fields = ', '.join(data.keys())
                placeholders = ', '.join('?' * len(data))
                values = tuple(data.values())
                cur.execute(f"INSERT INTO treatments ({fields}) VALUES ({placeholders})", values)
                tid = cur.lastrowid
                conn.commit()
                return self._get_by_id('treatments', tid) or {"id": tid}
        except sqlite3.IntegrityError as e:
            logger.warning(f"Tedavi zaten mevcut: {data.get('name')}")
            raise DatabaseError(f"Tedavi zaten mevcut: {e}")
        except sqlite3.Error as e:
            raise DatabaseError(f"Tedavi oluşturma hatası: {e}")

    def get_treatment(self, treatment_id: int) -> Optional[Dict[str, Any]]:
        return self._get_by_id('treatments', treatment_id)

    def list_treatments(self, is_active: Optional[bool] = True) -> List[Dict[str, Any]]:
        where = "is_active = ?" if is_active is not None else None
        params = (1,) if is_active is True else (0,) if is_active is False else None
        return self._list_all('treatments', where, params)

    # ------------------------------------
    # Appointment CRUD
    # ------------------------------------
    def create_appointment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Yeni randevu kaydı denemesi: Hasta {data.get('patient_name')}")
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                fields = ', '.join(data.keys())
                placeholders = ', '.join('?' * len(data))
                values = tuple(data.values())
                cur.execute(f"INSERT INTO appointments ({fields}) VALUES ({placeholders})", values)
                app_id = cur.lastrowid
                conn.commit()
                logger.info(f"Randevu başarıyla oluşturuldu. ID: {app_id}")
                return self._get_by_id('appointments', app_id) or {"id": app_id}
        except sqlite3.Error as e:
            logger.error(f"Randevu oluşturma hatası: {e}")
            raise DatabaseError(f"Randevu kaydedilemedi: {e}")

    def get_appointment(self, appointment_id: int) -> Optional[Dict[str, Any]]:
        return self._get_by_id('appointments', appointment_id)

    def list_appointments(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        where = "status = ?" if status else None
        params = (status,) if status else None
        return self._list_all('appointments', where, params)

    def update_appointment(self, appointment_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        logger.info(f"Randevu ID:{appointment_id} güncelleniyor. Yeni durum: {data.get('status')}")
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
                values = tuple(data.values()) + (appointment_id,)
                cur.execute(f"UPDATE appointments SET {set_clause} WHERE id = ?", values)
                conn.commit()
                return self.get_appointment(appointment_id)
        except sqlite3.Error as e:
            logger.error(f"Randevu güncelleme hatası: {e}")
            return None

    def approve_appointment(self, appointment_id: int) -> Optional[Dict[str, Any]]:
        return self.update_appointment(appointment_id, {"status": "approved"})

    def reject_appointment(self, appointment_id: int) -> Optional[Dict[str, Any]]:
        return self.update_appointment(appointment_id, {"status": "cancelled"})

    # ⭐ KRİTİK DEĞİŞİKLİK: Sadece saat değil, süre bilgisini de dönüyoruz
    def get_booked_slots(self, date: str, dentist_id: int) -> List[Dict[str, Any]]:
        """Belirtilen gün için dolu randevuların aralıklarını (saat ve süre) döner."""
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT time_slot, duration_minutes 
                    FROM appointments 
                    WHERE appointment_date = ? AND dentist_id = ? 
                    AND status IN ('pending', 'approved')
                    """,
                    (date, dentist_id)
                )
                return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Booked slots çekilirken hata: {e}")
            return []