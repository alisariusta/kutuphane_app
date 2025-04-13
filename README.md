# Kütüphane Uygulaması

Bu uygulama, kişisel kütüphanenizi yönetmenize yardımcı olan bir web uygulamasıdır. Kitaplarınızı ekleyebilir, düzenleyebilir, silebilir ve kategorize edebilirsiniz.

## Özellikler

- Kitap ekleme, düzenleme ve silme
- Google Books API entegrasyonu ile kitap bilgilerini otomatik doldurma
- Kitap kapak resimlerini Google'dan arama veya dosya yükleme
- Yazar ve yayınevi bazlı filtreleme
- Toplu kitap yükleme (CSV dosyası ile)
- Excel ve CSV formatlarında dışa aktarma
- Karanlık tema

## Kurulum

1. Python 3.9 veya üstü sürümünün yüklü olduğundan emin olun.

2. Uygulamayı indirin ve zip dosyasını açın:
   ```
   unzip kutuphane_app.zip
   cd kutuphane_app
   ```

3. Gerekli paketleri yükleyin:
   ```
   pip install -r requirements.txt
   ```

4. Google Books API için API anahtarı ve Arama Motoru ID'si alın:
   - [Google Cloud Console](https://console.cloud.google.com/) adresine gidin
   - Yeni bir proje oluşturun
   - Books API'yi etkinleştirin
   - Kimlik bilgileri oluşturun ve API anahtarınızı alın
   - [Google Programmable Search Engine](https://programmablesearchengine.google.com/about/) adresinden bir arama motoru oluşturun ve ID'sini alın

5. `.env` dosyasını düzenleyin ve API anahtarınızı ve Arama Motoru ID'nizi ekleyin:
   ```
   GOOGLE_API_KEY=your_api_key_here
   SEARCH_ENGINE_ID=your_search_engine_id_here
   ```

## Kullanım

1. Uygulamayı başlatın:
   ```
   python app.py
   ```

2. Tarayıcınızda `http://127.0.0.1:3000` adresine gidin.

3. Ana sayfada kitaplarınızı görüntüleyebilir, arama yapabilir ve yeni kitap ekleyebilirsiniz.

4. "Yeni Kitap Ekle" butonuna tıklayarak kitap ekleyebilirsiniz. Kitap adını girdikten sonra "Kitap Detaylarını Getir" butonuna tıklayarak Google Books API'den kitap bilgilerini otomatik olarak doldurabilirsiniz.

5. Kitap detay sayfasında kitabı düzenleyebilir veya silebilirsiniz.

6. "Toplu Kitap Yükle" sayfasından CSV dosyası ile birden fazla kitap ekleyebilirsiniz.

7. "Dışa Aktar" menüsünden kitaplarınızı Excel veya CSV formatında dışa aktarabilirsiniz.

## Veritabanı

Uygulama, SQLite veritabanı kullanmaktadır. Veritabanı dosyası (`kutuphane.db`) otomatik olarak oluşturulacaktır.

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır. 