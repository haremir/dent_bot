# hotel_bot

AI destekli çok-kanal otel rezervasyon asistanı. Modern Python, Groq (Llama), özelleştirilebilir adapter ve tool mimarisi ile Telegram başta olmak üzere birden fazla platformdan kullanılabilir.

---

## Özellikler

- **Ana Akıllı Fonksiyonlar:**
  - Oda fiyatı, müsaitlik, rezervasyon oluşturma (flow kontrollü), rezervasyon sorgulama, iptal ve güncelleme.
  - Tüm rezervasyon işlemleri için zorunlu doğrulama: tarih, isim, telefon (10+ hane), email (geçerli format) kontrolü.
  - Tüm cevaplarda gerçek müşteri dilini otomatik algılayıp kullanır (Türkçe/İngilizce).

- **Tool/Fonksiyon Listesi:**
  - `get_room_prices` — Oda ve fiyat listesini getirir (daima DB'den!).
  - `check_availability` — Belirli tarihlerde uygun odaları listeler.
  - `create_reservation` — Tüm müşteri ve rezervasyon bilgileri tam ise rezervasyon oluşturur.
  - `get_reservation` — Referans ya da ID ile rezervasyon bilgilerini getirir.
  - `cancel_reservation` — Rezervasyon iptal işlemleri (ID/Referans ile).
  - `update_reservation` — Belirli alanlarda (tarih, kişi sayısı, oda vb.) değişiklik yapar.

- **Gelişmiş Özellikler:**
  - SQLite tabanlı veri saklama (adapter ile gelişmiş veri kaynakları eklenebilir: Excel, API vb.)
  - LLM fallback: Önce Groq, başarısız olursa Ollama (lokal) ile yanıt
  - Doğrudan Groq, Telegram yapılandırması için kolay .env desteği
  - Her şey Python ile modüler ve kolay özelleştirilebilir!

---

## Kolay Kurulum ve Kullanım

1) **Ortam Değişkenlerini Tanımla**

Bir `.env` dosyasına aşağıdakileri ekle:

```env
ENV=development

GROQ_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-70b-versatile
LLM_TIMEOUT=15

TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

DATABASE_URL=sqlite:///hotel_bot.db

HOTEL_NAME=Demo Hotel
HOTEL_PHONE=+90 555 555 55 55
HOTEL_EMAIL=info@demo-hotel.com
```

2) **Bağımlılıkları yükle**

```bash
uv sync       # ya da
pip install -e .
```

3) **Botu çalıştır**

```bash
python -m src.hotel_bot.main
```

---

## Kullanım Akışı

- Kullanıcı bir platformdan (örn. Telegram) mesaj gönderir.
- Asistan müşterinin dilini algılar.
- Sadece gerçek ve eksiksiz bilgiyle rezervasyon oluşturur.
- Tüm oda ve rezervasyon bilgisini daima ilgili veritabanı araçları ile (tool fonksiyonları) sağlar. Hayali/placeholder veri veya varsayım **kullanmaz**.
- Yanıt akışı ve tool zorunlulukları PROMPT ile merkezi olarak yönetilir.

---

## Sistem Promptu & Zorunlu Akış

Model aşağıdaki iş akışına keskin şekilde uyar:

```
You are a professional hotel reservation assistant.

CRITICAL: Respond in customer's language (Turkish/English/etc.)

ALWAYS USE TOOLS FOR:
- Room prices → get_room_prices
- Availability → check_availability
- Reservation lookup → get_reservation (need ID)
- Cancel reservation → cancel_reservation (need ID)
- New booking → create_reservation (after getting all info)

NEVER DESCRIBE ROOMS WITHOUT get_room_prices!
NEVER ANSWER RESERVATION QUERIES WITHOUT get_reservation/cancel_reservation!

MANDATORY FLOW:
1. Ask check-in date
2. Ask check-out date
3. Call check_availability
4. Ask for guest count
5. Ask for full name (verify real)
6. Ask for phone (10+ digits)
7. Ask for email (@ and domain)
8. Verify all data is real
9. Only then call create_reservation
```

---

## Test & Geliştirici Notları

- Tüm fonksiyonlar için birim testleri `tests/` klasöründe.
- Gelişmiş validasyon araçları ve veri entegrasyonu için adapter ve config yapıları kullanılabilir.
- Bot kodu ve akışı, baştan sona modüler şekilde özelleştirilebilir.