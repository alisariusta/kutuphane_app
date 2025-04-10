# Kütüphane Uygulaması

Bu uygulama, kişisel kütüphanenizi dijital ortamda yönetmenizi sağlayan bir web uygulamasıdır.

## Özellikler

- Kitap ekleme, düzenleme ve silme
- Kitap detaylarını otomatik getirme (Kitapyurdu)
- Kapak resmi arama ve yükleme
- Kitap arama ve filtreleme
- İstatistikler ve grafikler

## Kurulum

1. Gerekli Python paketlerini yükleyin:
```bash
pip install -r requirements.txt
```

2. `.env` dosyası oluşturun ve gerekli API anahtarlarını ekleyin:
```
GOOGLE_API_KEY=your_google_api_key
SEARCH_ENGINE_ID=your_search_engine_id
```

3. Uygulamayı çalıştırın:
```bash
python app.py
```

4. Tarayıcınızda `http://localhost:3000` adresine gidin.

## Kullanılan Teknolojiler

- Python
- Flask
- SQLite
- Bootstrap
- Chart.js
- BeautifulSoup4

## Lisans

MIT 