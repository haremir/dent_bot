from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from dentbot.exceptions import DatabaseError

class SQLiteAppointmentAdapter:
    """SQLite veritabanı için randevu ve klinik verisi adaptörü."""
    
    def __init__(self, db_url: str):
        # Format: sqlite:///path
        if db_url.startswith("sqlite:///"):
            self.db_path = db_url.replace("sqlite:///", "")
        else:
            self.db_path = db_url
            
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        """Veritabanı bağlantısını döndürür ve row_factory'yi ayarlar."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            raise DatabaseError(f"Veritabanına bağlanılamadı: {e}") from e

    # ------------------------------------
    # Lifecycle
    # ------------------------------------
    def init(self) -> None:
        """Tabloları oluşturur (CREATE TABLE IF NOT EXISTS)."""
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                
                # 1. DENTIST Tablosu (Aynı kaldı)
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

                # 2. TREATMENT Tablosu (Aynı kaldı)
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

                # 3. APPOINTMENT Tablosu (patient_chat_id eklendi)
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
                        patient_chat_id INTEGER, -- ⭐ YENİ ALAN EKLENDİ
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(dentist_id) REFERENCES dentists(id),
                        UNIQUE(dentist_id, appointment_date, time_slot) ON CONFLICT FAIL
                    )
                    """
                )
                conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Tablo başlatma hatası: {e}") from e

    # ------------------------------------
    # Yardımcı Metodlar (Aynı kaldı)
    # ------------------------------------
    def _get_by_id(self, table_name: str, id_value: int) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {table_name} WHERE id = ?", (id_value,))
            row = cur.fetchone()
            return dict(row) if row else None
            
    def _list_all(self, table_name: str, where_clause: Optional[str] = None, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.cursor()
            query = f"SELECT * FROM {table_name}"
            if where_clause:
                query += f" WHERE {where_clause}"
            query += " ORDER BY id DESC"
            cur.execute(query, params or ())
            return [dict(r) for r in cur.fetchall()]


    # ------------------------------------
    # Dentist CRUD (Aynı kaldı)
    # ------------------------------------
    def create_dentist(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._conn() as conn:
            cur = conn.cursor()
            fields = ', '.join(data.keys())
            placeholders = ', '.join('?' * len(data))
            values = tuple(data.values())
            
            cur.execute(f"INSERT INTO dentists ({fields}) VALUES ({placeholders})", values)
            dentist_id = cur.lastrowid
            conn.commit()
            return self._get_by_id('dentists', dentist_id) or {"id": dentist_id}

    def get_dentist(self, dentist_id: int) -> Optional[Dict[str, Any]]:
        return self._get_by_id('dentists', dentist_id)

    def list_dentists(self, is_active: Optional[bool] = True) -> List[Dict[str, Any]]:
        where = "is_active = ?" if is_active is not None else None
        params = (1,) if is_active else (0,) if is_active is not None else None
        return self._list_all('dentists', where, params)
        
    def update_dentist(self, dentist_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not data:
            return self.get_dentist(dentist_id)
            
        with self._conn() as conn:
            cur = conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
            values = tuple(data.values()) + (dentist_id,)
            
            cur.execute(f"UPDATE dentists SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return self.get_dentist(dentist_id)

    def delete_dentist(self, dentist_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM dentists WHERE id = ?", (dentist_id,))
            conn.commit()
            return cur.rowcount > 0

    # ------------------------------------
    # Treatment CRUD (Aynı kaldı)
    # ------------------------------------
    def create_treatment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._conn() as conn:
            cur = conn.cursor()
            fields = ', '.join(data.keys())
            placeholders = ', '.join('?' * len(data))
            values = tuple(data.values())
            
            try:
                cur.execute(f"INSERT INTO treatments ({fields}) VALUES ({placeholders})", values)
                treatment_id = cur.lastrowid
                conn.commit()
                return self._get_by_id('treatments', treatment_id) or {"id": treatment_id}
            except sqlite3.IntegrityError as e:
                 raise DatabaseError(f"Tedavi oluşturma hatası: {e}. Muhtemelen aynı isimde kayıt var.") from e


    def get_treatment(self, treatment_id: int) -> Optional[Dict[str, Any]]:
        return self._get_by_id('treatments', treatment_id)

    def list_treatments(self, is_active: Optional[bool] = True) -> List[Dict[str, Any]]:
        where = "is_active = ?" if is_active is not None else None
        params = (1,) if is_active else (0,) if is_active is not None else None
        return self._list_all('treatments', where, params)
        
    def update_treatment(self, treatment_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not data:
            return self.get_treatment(treatment_id)
            
        with self._conn() as conn:
            cur = conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
            values = tuple(data.values()) + (treatment_id,)
            
            cur.execute(f"UPDATE treatments SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return self.get_treatment(treatment_id)

    def delete_treatment(self, treatment_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM treatments WHERE id = ?", (treatment_id,))
            conn.commit()
            return cur.rowcount > 0


    # ------------------------------------
    # Appointment CRUD (Aynı kaldı)
    # ------------------------------------
    def create_appointment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                fields = ', '.join(data.keys())
                placeholders = ', '.join('?' * len(data))
                values = tuple(data.values())
                
                cur.execute(f"INSERT INTO appointments ({fields}) VALUES ({placeholders})", values)
                appointment_id = cur.lastrowid
                conn.commit()
                return self._get_by_id('appointments', appointment_id) or {"id": appointment_id}
        except sqlite3.IntegrityError as e:
            if 'UNIQUE constraint failed' in str(e):
                raise DatabaseError("Randevu çakışması: Aynı gün ve saatte bu doktor için zaten bir randevu mevcut.") from e
            raise DatabaseError(f"Randevu oluşturma hatası: {e}") from e


    def get_appointment(self, appointment_id: int) -> Optional[Dict[str, Any]]:
        return self._get_by_id('appointments', appointment_id)

    def list_appointments(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        where = "status = ?" if status else None
        params = (status,) if status else None
        return self._list_all('appointments', where, params)

    def list_appointments_by_dentist(self, dentist_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
        where = "dentist_id = ?"
        params = [dentist_id]
        if status:
            where += " AND status = ?"
            params.append(status)
        return self._list_all('appointments', where, tuple(params))
        
    def list_appointments_by_date(self, date: str, dentist_id: Optional[int] = None) -> List[Dict[str, Any]]:
        where = "appointment_date = ?"
        params = [date]
        if dentist_id:
            where += " AND dentist_id = ?"
            params.append(dentist_id)
        return self._list_all('appointments', where, tuple(params))

    def update_appointment(self, appointment_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not data:
            return self.get_appointment(appointment_id)

        try:
            with self._conn() as conn:
                cur = conn.cursor()
                set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
                values = tuple(data.values()) + (appointment_id,)
                
                cur.execute(f"UPDATE appointments SET {set_clause} WHERE id = ?", values)
                conn.commit()
                return self.get_appointment(appointment_id)
        except sqlite3.IntegrityError as e:
            if 'UNIQUE constraint failed' in str(e):
                raise DatabaseError("Randevu çakışması: Güncelleme, başka bir randevuyla çakışıyor.") from e
            raise DatabaseError(f"Randevu güncelleme hatası: {e}") from e


    def delete_appointment(self, appointment_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
            conn.commit()
            return cur.rowcount > 0

    # ------------------------------------
    # Slot & Approval İşlemleri (Aynı kaldı)
    # ------------------------------------
    def get_booked_slots(self, date: str, dentist_id: int) -> List[str]:
        """Belirtilen gün ve doktor için ONAYLANMIŞ veya BEKLEYEN dolu slotları döndürür."""
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT time_slot FROM appointments 
                WHERE appointment_date = ? AND dentist_id = ? 
                AND status IN ('pending', 'approved')
                """,
                (date, dentist_id)
            )
            return [row[0] for row in cur.fetchall()]

    def approve_appointment(self, appointment_id: int) -> Optional[Dict[str, Any]]:
        """Randevunun durumunu 'approved' olarak günceller."""
        return self.update_appointment(appointment_id, {"status": "approved"})

    def reject_appointment(self, appointment_id: int) -> Optional[Dict[str, Any]]:
        """Randevunun durumunu 'cancelled' olarak günceller (teknik olarak iptal sayılır)."""
        return self.update_appointment(appointment_id, {"status": "cancelled"})