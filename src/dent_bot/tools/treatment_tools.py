from __future__ import annotations
from typing import List, Optional, Dict, Any
import logging

# Adım 23'te oluşturulacak utility'ler ve diğer servis/model katmanları
from dentbot.tools import tool, get_adapter 
from dentbot.models import Treatment 
from dentbot.exceptions import AppointmentError

logger = logging.getLogger(__name__)


# ------------------------------------
# TOOLS IMPLEMENTATION
# ------------------------------------

@tool
def get_treatment_list(is_active: bool = True) -> str:
    """
    Klinikte sunulan tüm aktif tedavi hizmetlerini süreleri ve fiyat bilgileriyle (varsa) listeler.
    Bu aracı, kullanıcı hangi tedavileri sunduğunuzu veya bir tedavinin fiyatını/süresini sorduğunda kullanın.
    
    Args:
        is_active: Sadece aktif tedavileri listelemek için (default True).
        
    Returns:
        Tedavi adlarını, sürelerini ve fiyatlarını içeren formatlanmış bir string.
    """
    adapter = get_adapter()
    treatments_data = adapter.list_treatments(is_active=is_active)
    
    if not treatments_data:
        return "Klinikte şu anda listelenecek aktif tedavi hizmeti bulunmamaktadır."
    
    result = "Klinik Tedavi Hizmetleri:\n"
    for data in treatments_data:
        treatment = Treatment.from_dict(data)
        
        # Fiyatı formatla
        price_str = f"₺{treatment.price:,.2f}" if treatment.price is not None else "Fiyat bilgisi için iletişime geçin"
        
        result += f"\n• **{treatment.name}**\n"
        result += f"  ID: {treatment.id} (Sistem Referansı)\n"
        result += f"  Tahmini Süre: {treatment.duration_minutes} dakika\n"
        result += f"  Fiyat Aralığı: {price_str}\n"
        result += f"  Onay Gerekli: {'Evet' if treatment.requires_approval else 'Hayır'}\n"
    
    return result

@tool
def get_treatment_duration(treatment_name: str) -> str:
    """
    Belirli bir tedavi adının tahmini süresini dakika cinsinden döndürür.
    Bu aracı, LLM randevu oluşturmadan önce randevu slotunu hesaplamak için kullanır.
    
    Args:
        treatment_name: Sorgulanacak tedavinin adı (örneğin: "Dolgu", "Diş Temizliği").
        
    Returns:
        Tedavinin süresini belirten formatlanmış bir string veya hata mesajı.
    """
    adapter = get_adapter()
    # Not: Tedavi adıyla sorgulama yapabilmek için tüm listeyi çekip Python'da filtreliyoruz.
    # Alternatif olarak adapter'a get_treatment_by_name metodu eklenebilir.
    treatments_data = adapter.list_treatments(is_active=True)
    
    found_treatment = None
    # İsimleri küçük harfe çevirerek tam eşleşme arayalım.
    normalized_name = treatment_name.strip().lower()
    
    for data in treatments_data:
        treatment = Treatment.from_dict(data)
        if treatment.name.strip().lower() == normalized_name:
            found_treatment = treatment
            break
            
    if not found_treatment:
        return f"❌ Hata: '{treatment_name}' adında aktif bir tedavi bulunamadı. Lütfen listeden kontrol edin."

    return (
        f"✅ Tedavi Süresi: '{found_treatment.name}' tedavisi için tahmini süre "
        f"**{found_treatment.duration_minutes} dakika**dır."
    )