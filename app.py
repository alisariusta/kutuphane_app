from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from math import ceil
from sqlalchemy import or_, func, distinct, text
import requests
import os
from urllib.parse import quote
from dotenv import load_dotenv
import uuid
import time
import csv
import io
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup
import pandas as pd

# .env dosyasını yükle
load_dotenv()

# Environment değişkenlerini kontrol et
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
SEARCH_ENGINE_ID = os.getenv('SEARCH_ENGINE_ID')

print("Environment variables loaded:")
print(f"GOOGLE_API_KEY present: {'Yes' if GOOGLE_API_KEY else 'No'}")
print(f"SEARCH_ENGINE_ID present: {'Yes' if SEARCH_ENGINE_ID else 'No'}")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kutuphane.db'
app.config['UPLOAD_FOLDER'] = 'static/kitap_kapak'

# API anahtarlarını Flask config'e ekle
app.config['GOOGLE_API_KEY'] = GOOGLE_API_KEY
app.config['SEARCH_ENGINE_ID'] = SEARCH_ENGINE_ID

# Jinja2 ortamına max ve min fonksiyonlarını ekle
app.jinja_env.globals.update(max=max, min=min)

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

db = SQLAlchemy(app)

class Kitap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    baslik = db.Column(db.String(200), nullable=False)
    yazar = db.Column(db.String(100))
    yayinevi = db.Column(db.String(100))
    arka_kapak = db.Column(db.Text)
    kapak_resmi = db.Column(db.String(500))
    eklenme_tarihi = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Kitap {self.baslik}>'

# Arama önerilerini getir
@app.route('/arama-onerileri')
def arama_onerileri():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify([])
    
    try:
        # Kitap, yazar ve yayınevi önerilerini al
        kitaplar = Kitap.query.filter(
            or_(
                Kitap.baslik.ilike(f'%{q}%'),
                Kitap.yazar.ilike(f'%{q}%'),
                Kitap.yayinevi.ilike(f'%{q}%')
            )
        ).limit(10).all()
        
        oneriler = []
        for kitap in kitaplar:
            if q.lower() in kitap.baslik.lower():
                oneriler.append({
                    'tip': 'kitap',
                    'id': kitap.id,
                    'metin': kitap.baslik,
                    'alt_metin': f"{kitap.yazar} | {kitap.yayinevi}"
                })
            if q.lower() in kitap.yazar.lower() and not any(o['metin'] == kitap.yazar and o['tip'] == 'yazar' for o in oneriler):
                oneriler.append({
                    'tip': 'yazar',
                    'metin': kitap.yazar,
                    'alt_metin': 'Yazar'
                })
            if q.lower() in kitap.yayinevi.lower() and not any(o['metin'] == kitap.yayinevi and o['tip'] == 'yayinevi' for o in oneriler):
                oneriler.append({
                    'tip': 'yayinevi',
                    'metin': kitap.yayinevi,
                    'alt_metin': 'Yayınevi'
                })
        
        return jsonify(oneriler[:10])  # En fazla 10 öneri gönder
        
    except Exception as e:
        print(f"Arama önerileri hatası: {str(e)}")
        return jsonify([])

# Ana sayfa - Kitapları sayfalı şekilde listele
@app.route('/')
def ana_sayfa():
    try:
        sayfa = request.args.get('sayfa', 1, type=int)
        arama = request.args.get('arama', '')
        sayfa_basi = 15
        
        print(f"Ana sayfa isteği: Sayfa={sayfa}, Arama={arama}")
        
        # Arama sorgusu
        sorgu = Kitap.query
        if arama:
            sorgu = sorgu.filter(
                or_(
                    Kitap.baslik.ilike(f'%{arama}%'),
                    Kitap.yazar.ilike(f'%{arama}%'),
                    Kitap.yayinevi.ilike(f'%{arama}%')
                )
            )
        
        # Toplam kitap sayısı ve toplam sayfa sayısını hesapla
        try:
            toplam_kitap = sorgu.count()
            print(f"Toplam kitap sayısı: {toplam_kitap}")
        except Exception as e:
            print(f"Kitap sayısı hesaplanırken hata: {str(e)}")
            raise
        
        # Toplam yazar ve yayınevi sayısını hesapla
        toplam_yazar = db.session.query(Kitap.yazar).distinct().count()
        toplam_yayinevi = db.session.query(Kitap.yayinevi).distinct().count()
        
        toplam_sayfa = ceil(toplam_kitap / sayfa_basi)
        
        # İstenen sayfadaki kitapları al
        try:
            kitaplar = sorgu.order_by(Kitap.eklenme_tarihi.desc())\
                .offset((sayfa - 1) * sayfa_basi)\
                .limit(sayfa_basi)\
                .all()
            print(f"Bulunan kitap sayısı: {len(kitaplar)}")
        except Exception as e:
            print(f"Kitaplar alınırken hata: {str(e)}")
            raise
        
        return render_template('ana_sayfa.html', 
                            kitaplar=kitaplar, 
                            sayfa=sayfa, 
                            toplam_sayfa=toplam_sayfa,
                            toplam_kitap=toplam_kitap,
                            toplam_yazar=toplam_yazar,
                            toplam_yayinevi=toplam_yayinevi,
                            arama=arama)
    except Exception as e:
        print(f"Ana sayfa görüntülenirken hata: {str(e)}")
        return f"Bir hata oluştu: {str(e)}", 500

# Kitap detay sayfası
@app.route('/kitap/<int:id>')
def kitap_detay(id):
    kitap = Kitap.query.get_or_404(id)
    return render_template('kitap_detay.html', kitap=kitap)

# Yeni kitap ekle
@app.route('/kitap_ekle', methods=['GET', 'POST'])
def kitap_ekle():
    if request.method == 'POST':
        try:
            # Kitap bilgilerini al
            baslik = request.form.get('baslik')
            yazar = request.form.get('yazar')
            yayinevi = request.form.get('yayinevi')
            arka_kapak = request.form.get('arka_kapak')

            # Yeni kitap oluştur
            yeni_kitap = Kitap(
                baslik=baslik,
                yazar=yazar,
                yayinevi=yayinevi,
                arka_kapak=arka_kapak
            )

            # Kapak resmi işleme
            yukleme_tipi = request.form.get('yukleme_tipi')
            kapak_resmi = None

            if yukleme_tipi == 'google':
                # Google'dan seçilen resim
                secili_kapak = request.form.get('secili_kapak')
                if secili_kapak:
                    response = requests.get(secili_kapak)
                    if response.status_code == 200:
                        kapak_resmi = response.content
            elif yukleme_tipi == 'dosya':
                # Dosya yükleme
                if 'kapak_dosya' in request.files:
                    dosya = request.files['kapak_dosya']
                    if dosya and dosya.filename:
                        kapak_resmi = dosya.read()
            elif yukleme_tipi == 'url':
                # URL'den yükleme
                kapak_url = request.form.get('kapak_url')
                if kapak_url:
                    response = requests.get(kapak_url)
                    if response.status_code == 200:
                        kapak_resmi = response.content

            # Kapak resmini kaydet
            if kapak_resmi:
                # Benzersiz dosya adı oluştur
                dosya_adi = f"{yeni_kitap.id}_{int(time.time())}.jpg"
                dosya_yolu = os.path.join(app.config['UPLOAD_FOLDER'], dosya_adi)
                
                # Resmi kaydet
                with open(dosya_yolu, 'wb') as f:
                    f.write(kapak_resmi)
                
                yeni_kitap.kapak_resmi = dosya_adi

            # Veritabanına kaydet
            db.session.add(yeni_kitap)
            db.session.commit()

            flash('Kitap başarıyla eklendi!', 'success')
            return redirect(url_for('ana_sayfa'))

        except Exception as e:
            db.session.rollback()
            flash(f'Kitap eklenirken bir hata oluştu: {str(e)}', 'error')
            return redirect(url_for('kitap_ekle'))

    return render_template('kitap_ekle.html')

# Kitap düzenle
@app.route('/kitap_duzenle/<int:id>', methods=['GET', 'POST'])
def kitap_duzenle(id):
    kitap = Kitap.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # Kitap bilgilerini güncelle
            kitap.baslik = request.form.get('baslik')
            kitap.yazar = request.form.get('yazar')
            kitap.yayinevi = request.form.get('yayinevi')
            kitap.arka_kapak = request.form.get('arka_kapak')

            # Kapak resmi işleme
            yukleme_tipi = request.form.get('yukleme_tipi')
            kapak_resmi = None

            if yukleme_tipi == 'google':
                # Google'dan seçilen resim
                secili_kapak = request.form.get('secili_kapak')
                if secili_kapak:
                    response = requests.get(secili_kapak)
                    if response.status_code == 200:
                        kapak_resmi = response.content
            elif yukleme_tipi == 'dosya':
                # Dosya yükleme
                if 'kapak_dosya' in request.files:
                    dosya = request.files['kapak_dosya']
                    if dosya and dosya.filename:
                        kapak_resmi = dosya.read()
            elif yukleme_tipi == 'url':
                # URL'den yükleme
                kapak_url = request.form.get('kapak_url')
                if kapak_url:
                    response = requests.get(kapak_url)
                    if response.status_code == 200:
                        kapak_resmi = response.content

            # Kapak resmini kaydet
            if kapak_resmi:
                # Eski resmi sil
                if kitap.kapak_resmi:
                    eski_resim_yolu = os.path.join(app.config['UPLOAD_FOLDER'], kitap.kapak_resmi)
                    if os.path.exists(eski_resim_yolu):
                        os.remove(eski_resim_yolu)

                # Yeni resmi kaydet
                dosya_adi = f"{kitap.id}_{int(time.time())}.jpg"
                dosya_yolu = os.path.join(app.config['UPLOAD_FOLDER'], dosya_adi)
                
                with open(dosya_yolu, 'wb') as f:
                    f.write(kapak_resmi)
                
                kitap.kapak_resmi = dosya_adi

            # Veritabanına kaydet
            db.session.commit()
            flash('Kitap başarıyla güncellendi!', 'success')
            return redirect(url_for('ana_sayfa'))

        except Exception as e:
            db.session.rollback()
            flash(f'Kitap güncellenirken bir hata oluştu: {str(e)}', 'error')
            return redirect(url_for('kitap_duzenle', id=id))

    return render_template('kitap_duzenle.html', kitap=kitap)

# Kitap sil
@app.route('/kitap/sil/<int:id>')
def kitap_sil(id):
    kitap = Kitap.query.get_or_404(id)
    
    try:
        db.session.delete(kitap)
        db.session.commit()
        flash('Kitap başarıyla silindi!', 'success')
    except:
        flash('Kitap silinirken bir hata oluştu.', 'error')
    
    return redirect(url_for('ana_sayfa'))

# Yazar detay sayfası
@app.route('/yazar/<string:yazar_adi>')
def yazar_detay(yazar_adi):
    sayfa = request.args.get('sayfa', 1, type=int)
    sayfa_basi = 15
    
    # Yazara ait kitapları al
    sorgu = Kitap.query.filter(Kitap.yazar == yazar_adi)
    toplam_kitap = sorgu.count()
    toplam_sayfa = ceil(toplam_kitap / sayfa_basi)
    
    kitaplar = sorgu.order_by(Kitap.eklenme_tarihi.desc())\
        .offset((sayfa - 1) * sayfa_basi)\
        .limit(sayfa_basi)\
        .all()
    
    return render_template('yazar_detay.html', 
                         yazar=yazar_adi,
                         kitaplar=kitaplar,
                         sayfa=sayfa,
                         toplam_sayfa=toplam_sayfa)

# Yayınevi detay sayfası
@app.route('/yayinevi/<string:yayinevi_adi>')
def yayinevi_detay(yayinevi_adi):
    sayfa = request.args.get('sayfa', 1, type=int)
    sayfa_basi = 15
    
    # Yayınevine ait kitapları al
    sorgu = Kitap.query.filter(Kitap.yayinevi == yayinevi_adi)
    toplam_kitap = sorgu.count()
    toplam_sayfa = ceil(toplam_kitap / sayfa_basi)
    
    kitaplar = sorgu.order_by(Kitap.eklenme_tarihi.desc())\
        .offset((sayfa - 1) * sayfa_basi)\
        .limit(sayfa_basi)\
        .all()
    
    return render_template('yayinevi_detay.html', 
                         yayinevi=yayinevi_adi,
                         kitaplar=kitaplar,
                         sayfa=sayfa,
                         toplam_sayfa=toplam_sayfa)

@app.route('/kitap/kapak_ara/<int:id>')
def kapak_ara(id):
    if id == 0:  # Yeni kitap durumu
        baslik = request.args.get('baslik', '')
        yazar = request.args.get('yazar', '')
        arama_terimi = f"{baslik} {yazar} kitap kapağı"
    else:
        kitap = Kitap.query.get_or_404(id)
        arama_terimi = f"{kitap.baslik} {kitap.yazar} kitap kapağı"
    
    # Google Custom Search API kullanarak resim arama
    GOOGLE_API_KEY = app.config['GOOGLE_API_KEY']
    SEARCH_ENGINE_ID = app.config['SEARCH_ENGINE_ID']
    
    print("API çağrısı öncesi kontrol:")
    print(f"GOOGLE_API_KEY: {GOOGLE_API_KEY}")
    print(f"SEARCH_ENGINE_ID: {SEARCH_ENGINE_ID}")
    print(f"Arama terimi: {arama_terimi}")
    
    if not GOOGLE_API_KEY or not SEARCH_ENGINE_ID:
        print("API anahtarları bulunamadı!")
        return jsonify({'error': 'API yapılandırması eksik! Lütfen GOOGLE_API_KEY ve SEARCH_ENGINE_ID değerlerini kontrol edin.'})
    
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'key': GOOGLE_API_KEY,
        'cx': SEARCH_ENGINE_ID,
        'q': arama_terimi,
        'searchType': 'image',
        'num': 10,
        'imgSize': 'large',
        'imgType': 'photo',
        'safe': 'active'
    }
    
    print("API isteği parametreleri:")
    print(params)
    
    try:
        print(f"API çağrısı yapılıyor...")
        response = requests.get(url, params=params)
        print(f"API yanıt status kodu: {response.status_code}")
        print(f"API yanıt içeriği: {response.text[:500]}...")  # İlk 500 karakteri göster
        
        response.raise_for_status()
        results = response.json()
        
        if 'error' in results:
            print(f"Google API hatası: {results['error']}")
            return jsonify({'error': f"Google API hatası: {results['error'].get('message', 'Bilinmeyen hata')}"})
        
        images = []
        if 'items' in results:
            for item in results['items']:
                images.append({
                    'url': item['link'],
                    'thumbnail': item.get('image', {}).get('thumbnailLink', item['link'])
                })
            print(f"{len(images)} adet resim bulundu")
        else:
            print("Hiç resim bulunamadı")
        
        return jsonify({'images': images})
    except requests.exceptions.RequestException as e:
        print(f"API çağrısı sırasında hata: {str(e)}")
        print(f"Tam hata detayı: {e.response.text if hasattr(e, 'response') else 'Detay yok'}")
        return jsonify({'error': f'API çağrısı sırasında hata oluştu: {str(e)}'})
    except Exception as e:
        print(f"Beklenmeyen hata: {str(e)}")
        return jsonify({'error': f'Beklenmeyen bir hata oluştu: {str(e)}'})

@app.route('/kitap/kapak_kaydet/<int:id>', methods=['POST'])
def kapak_kaydet(id):
    image_url = request.form.get('image_url')
    
    if not image_url:
        return jsonify({'error': 'Resim URL\'i gerekli'})
    
    try:
        # Resmi indir
        response = requests.get(image_url)
        if response.status_code == 200:
            # Dosya adını oluştur
            if id == 0:  # Yeni kitap durumu
                # Geçici bir dosya adı oluştur
                temp_id = str(uuid.uuid4())
                dosya_adi = f"temp_{temp_id}{os.path.splitext(image_url)[1]}"
            else:
                dosya_adi = f"kitap_{id}_kapak{os.path.splitext(image_url)[1]}"
            
            dosya_yolu = os.path.join(app.config['UPLOAD_FOLDER'], dosya_adi)
            
            # Resmi kaydet
            with open(dosya_yolu, 'wb') as f:
                f.write(response.content)
            
            if id != 0:  # Mevcut kitap için veritabanını güncelle
                kitap = Kitap.query.get_or_404(id)
                kitap.kapak_resmi = dosya_adi
                db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Kapak resmi başarıyla kaydedildi',
                'image_path': f"/static/kitap_kapak/{dosya_adi}"
            })
    except Exception as e:
        return jsonify({'error': str(e)})
    
    return jsonify({'error': 'Resim kaydedilemedi'})

@app.route('/kitap_ara')
def kitap_ara():
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify([])

        # Google Custom Search API'yi kullanarak resim araması yap
        search_url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': os.getenv('GOOGLE_API_KEY'),
            'cx': os.getenv('SEARCH_ENGINE_ID'),
            'q': query,
            'searchType': 'image',
            'num': 10,
            'imgSize': 'medium',
            'imgType': 'photo',
            'safe': 'active'
        }

        response = requests.get(search_url, params=params)
        data = response.json()

        if 'items' in data:
            return jsonify([item['link'] for item in data['items']])
        else:
            return jsonify([])

    except Exception as e:
        print(f"Arama hatası: {str(e)}")
        return jsonify([])

@app.route('/arama_sonuclari')
def arama_sonuclari():
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify([])
    
    # Arama sorgusunu küçük harfe çevir
    query_lower = query.lower()
    
    # Veritabanından arama yap
    kitaplar = Kitap.query.filter(
        db.or_(
            db.func.lower(Kitap.baslik).like(f'%{query_lower}%'),
            db.func.lower(Kitap.yazar).like(f'%{query_lower}%'),
            db.func.lower(Kitap.yayinevi).like(f'%{query_lower}%')
        )
    ).limit(10).all()
    
    sonuclar = []
    for kitap in kitaplar:
        sonuclar.append({
            'id': kitap.id,
            'baslik': kitap.baslik,
            'yazar': kitap.yazar,
            'yayinevi': kitap.yayinevi
        })
    
    return jsonify(sonuclar)

@app.route('/toplu-kitap-yukle', methods=['GET', 'POST'])
def toplu_kitap_yukle():
    if request.method == 'POST':
        if 'csv_dosya' not in request.files:
            flash('Dosya seçilmedi', 'error')
            return redirect(request.url)
        
        file = request.files['csv_dosya']
        if file.filename == '':
            flash('Dosya seçilmedi', 'error')
            return redirect(request.url)
        
        if not file.filename.endswith('.csv'):
            flash('Lütfen CSV dosyası yükleyin', 'error')
            return redirect(request.url)
        
        try:
            # CSV dosyasını oku
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)
            
            kitaplar = []
            for row in csv_reader:
                kitap = {
                    'baslik': row.get('baslik', '').strip() if row.get('baslik') else '',
                    'yazar': row.get('yazar', '').strip() if row.get('yazar') else '',
                    'yayinevi': row.get('yayinevi', '').strip() if row.get('yayinevi') else '',
                    'arka_kapak': row.get('arka_kapak', '').strip() if row.get('arka_kapak') else '',
                    'hata': None
                }
                
                # Zorunlu alanları kontrol et
                if not kitap['baslik']:
                    kitap['hata'] = 'Kitap adı boş olamaz'
                elif not kitap['yazar']:
                    kitap['hata'] = 'Yazar adı boş olamaz'
                elif not kitap['yayinevi']:
                    kitap['hata'] = 'Yayınevi boş olamaz'
                
                kitaplar.append(kitap)
            
            # Session'a kitapları kaydet
            session['yuklenecek_kitaplar'] = kitaplar
            
            return render_template('toplu_kitap_onizleme.html', 
                                 kitaplar=kitaplar, 
                                 dosya_adi=secure_filename(file.filename))
            
        except Exception as e:
            flash(f'Dosya okuma hatası: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('toplu_kitap_yukle.html')

@app.route('/toplu-kitap-kaydet', methods=['POST'])
def toplu_kitap_kaydet():
    if 'yuklenecek_kitaplar' not in session:
        flash('Oturum süresi dolmuş, lütfen dosyayı tekrar yükleyin', 'error')
        return redirect(url_for('toplu_kitap_yukle'))
    
    secili_indexler = request.form.getlist('secili_kitaplar')
    kitaplar = session['yuklenecek_kitaplar']
    
    eklenen = 0
    hatali = 0
    
    for index in secili_indexler:
        try:
            kitap_data = kitaplar[int(index)]
            if not kitap_data['hata']:  # Sadece hatasız kitapları ekle
                yeni_kitap = Kitap(
                    baslik=kitap_data['baslik'],
                    yazar=kitap_data['yazar'],
                    yayinevi=kitap_data['yayinevi'],
                    arka_kapak=kitap_data['arka_kapak']
                )
                
                # Kapak URL'si varsa kaydet
                if kitap_data['kapak_url']:
                    try:
                        response = requests.get(kitap_data['kapak_url'])
                        if response.status_code == 200:
                            dosya_adi = f"kitap_{yeni_kitap.id}_kapak"
                            dosya_yolu = os.path.join(app.config['UPLOAD_FOLDER'], dosya_adi)
                            with open(dosya_yolu, 'wb') as f:
                                f.write(response.content)
                            yeni_kitap.kapak_resmi = dosya_adi
                    except:
                        pass  # Kapak indirme hatası olursa yoksay
                
                db.session.add(yeni_kitap)
                eklenen += 1
        except:
            hatali += 1
    
    try:
        db.session.commit()
        flash(f'{eklenen} kitap başarıyla eklendi. {hatali} kitap eklenemedi.', 'success')
    except:
        db.session.rollback()
        flash('Kitaplar eklenirken bir hata oluştu', 'error')
    
    # Session'dan geçici verileri temizle
    session.pop('yuklenecek_kitaplar', None)
    
    return redirect(url_for('ana_sayfa'))

@app.route('/yazarlar')
def yazarlar():
    # Benzersiz yazarları al
    yazarlar = db.session.query(Kitap.yazar, db.func.count(Kitap.id).label('kitap_sayisi')) \
        .group_by(Kitap.yazar) \
        .order_by(Kitap.yazar) \
        .all()
    return render_template('yazarlar.html', yazarlar=yazarlar)

@app.route('/yayinevleri')
def yayinevleri():
    # Benzersiz yayınevlerini al
    yayinevleri = db.session.query(Kitap.yayinevi, db.func.count(Kitap.id).label('kitap_sayisi')) \
        .group_by(Kitap.yayinevi) \
        .order_by(Kitap.yayinevi) \
        .all()
    return render_template('yayinevleri.html', yayinevleri=yayinevleri)

@app.route('/kitap_detay_ara')
def kitap_detay_ara():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Arama terimi gerekli'})
    
    try:
        sonuclar = []
        
        # Kitapyurdu'ndan ara
        ky_url = f"https://www.kitapyurdu.com/index.php?route=product/search&filter_name={quote(query)}"
        ky_response = requests.get(ky_url, headers={'User-Agent': 'Mozilla/5.0'})
        if ky_response.status_code == 200:
            soup = BeautifulSoup(ky_response.text, 'html.parser')
            # İlk 20 kitabı al
            kitap_kartlari = soup.select('div.product-grid div.product-cr')[:20]
            print(f"Bulunan kitap kartı sayısı: {len(kitap_kartlari)}")
            
            for kart in kitap_kartlari:
                try:
                    # Kitap detay linkini al
                    link = kart.select_one('div.name a')
                    if not link:
                        print("Link bulunamadı")
                        continue
                        
                    kitap_url = link['href']
                    print(f"Kitap URL: {kitap_url}")
                    
                    if not kitap_url.startswith('http'):
                        kitap_url = 'https://www.kitapyurdu.com' + kitap_url
                    
                    # Kitap detay sayfasını aç
                    kitap_response = requests.get(kitap_url, headers={'User-Agent': 'Mozilla/5.0'})
                    if kitap_response.status_code == 200:
                        kitap_soup = BeautifulSoup(kitap_response.text, 'html.parser')
                        
                        # Başlık
                        baslik_elem = kitap_soup.select_one('h1.pr_header__heading')
                        baslik = baslik_elem.text.strip() if baslik_elem else ''
                        print(f"Başlık: {baslik}")
                        
                        # Yazar - Daha basit bir seçici kullanalım
                        yazar_elem = kitap_soup.select_one('.pr_producers__manufacturer')
                        yazar = yazar_elem.text.strip() if yazar_elem else ''
                        print(f"Yazar: {yazar}")
                        
                        # Yayınevi - Daha basit bir seçici kullanalım
                        yayinevi_elem = kitap_soup.select_one('.pr_producers__publisher')
                        yayinevi = yayinevi_elem.text.strip() if yayinevi_elem else ''
                        print(f"Yayınevi: {yayinevi}")
                        
                        # Arka kapak
                        arka_kapak_elem = kitap_soup.select_one('div#description_text')
                        arka_kapak = arka_kapak_elem.text.strip() if arka_kapak_elem else ''
                        print(f"Arka kapak uzunluğu: {len(arka_kapak)}")
                        
                        # Eğer başlık varsa, Google'dan kapak resmi ara
                        if baslik:
                            # Google Custom Search API'yi kullanarak resim araması yap
                            search_url = "https://www.googleapis.com/customsearch/v1"
                            params = {
                                'key': os.getenv('GOOGLE_API_KEY'),
                                'cx': os.getenv('SEARCH_ENGINE_ID'),
                                'q': f"{baslik} {yazar} kitap kapağı",
                                'searchType': 'image',
                                'num': 5,
                                'imgSize': 'medium',
                                'imgType': 'photo',
                                'safe': 'active'
                            }
                            
                            try:
                                response = requests.get(search_url, params=params)
                                data = response.json()
                                
                                kapak_url = ''
                                if 'items' in data and len(data['items']) > 0:
                                    kapak_url = data['items'][0]['link']
                            except:
                                kapak_url = ''
                            
                            sonuc = {
                                'baslik': baslik,
                                'yazar': yazar,
                                'yayinevi': yayinevi,
                                'arka_kapak': arka_kapak,
                                'kapak_url': kapak_url
                            }
                            sonuclar.append(sonuc)
                            print("Sonuç eklendi")
                except Exception as e:
                    print(f"Kitap detayı alınırken hata: {str(e)}")
                    continue
        
        print(f"Toplam bulunan sonuç sayısı: {len(sonuclar)}")
        return jsonify({'items': sonuclar})
            
    except Exception as e:
        print(f"Kitap arama hatası: {str(e)}")  # Hata mesajını logla
        return jsonify({'error': str(e)})

@app.route('/export/excel')
def export_excel():
    try:
        # Tüm kitapları veritabanından çek
        kitaplar = Kitap.query.order_by(Kitap.baslik).all()
        
        # Kitapları listeye dönüştür
        kitap_listesi = []
        for kitap in kitaplar:
            kitap_listesi.append({
                'Kitap Adı': kitap.baslik,
                'Yazar': kitap.yazar,
                'Yayınevi': kitap.yayinevi,
                'Arka Kapak': kitap.arka_kapak,
                'Eklenme Tarihi': kitap.eklenme_tarihi.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Pandas DataFrame oluştur
        df = pd.DataFrame(kitap_listesi)
        
        # Excel dosyası oluştur
        tarih = datetime.now().strftime('%Y%m%d_%H%M%S')
        dosya_adi = f'kutuphane_export_{tarih}.xlsx'
        excel_path = os.path.join(app.root_path, 'static', 'exports', dosya_adi)
        
        # Exports klasörünü oluştur (yoksa)
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)
        
        # Excel'e aktar
        df.to_excel(excel_path, index=False, sheet_name='Kitaplar')
        
        # Dosyayı kullanıcıya gönder
        return send_file(excel_path, 
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        as_attachment=True,
                        download_name=dosya_adi)
    
    except Exception as e:
        print(f"Excel dışa aktarma hatası: {str(e)}")
        flash('Dışa aktarma sırasında bir hata oluştu.', 'error')
        return redirect(url_for('ana_sayfa'))

@app.route('/export/csv')
def export_csv():
    try:
        # Tüm kitapları veritabanından çek
        kitaplar = Kitap.query.order_by(Kitap.baslik).all()
        
        # Kitapları listeye dönüştür
        kitap_listesi = []
        for kitap in kitaplar:
            kitap_listesi.append({
                'Kitap Adı': kitap.baslik,
                'Yazar': kitap.yazar,
                'Yayınevi': kitap.yayinevi,
                'Arka Kapak': kitap.arka_kapak,
                'Eklenme Tarihi': kitap.eklenme_tarihi.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Pandas DataFrame oluştur
        df = pd.DataFrame(kitap_listesi)
        
        # CSV dosyası oluştur
        tarih = datetime.now().strftime('%Y%m%d_%H%M%S')
        dosya_adi = f'kutuphane_export_{tarih}.csv'
        csv_path = os.path.join(app.root_path, 'static', 'exports', dosya_adi)
        
        # Exports klasörünü oluştur (yoksa)
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        # CSV'ye aktar (UTF-8 ile Türkçe karakterler için)
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        
        # Dosyayı kullanıcıya gönder
        return send_file(csv_path,
                        mimetype='text/csv',
                        as_attachment=True,
                        download_name=dosya_adi)
    
    except Exception as e:
        print(f"CSV dışa aktarma hatası: {str(e)}")
        flash('Dışa aktarma sırasında bir hata oluştu.', 'error')
        return redirect(url_for('ana_sayfa'))

@app.route('/istatistikler')
def istatistikler():
    # Toplam sayılar
    toplam_kitap = db.session.query(func.count(Kitap.id)).scalar()
    toplam_yazar = db.session.query(func.count(distinct(Kitap.yazar))).scalar()
    toplam_yayinevi = db.session.query(func.count(distinct(Kitap.yayinevi))).scalar()
    ortalama_kitap = round(toplam_kitap / toplam_yazar if toplam_yazar > 0 else 0, 1)

    # Yayınevi dağılımı
    yayinevi_dagilimi = db.session.query(
        Kitap.yayinevi,
        func.count(Kitap.id).label('kitap_sayisi')
    ).group_by(Kitap.yayinevi).order_by(text('kitap_sayisi DESC')).limit(6).all()

    yayinevi_etiketler = [item[0] for item in yayinevi_dagilimi]
    yayinevi_veriler = [item[1] for item in yayinevi_dagilimi]

    # Yazar dağılımı
    yazar_dagilimi = db.session.query(
        Kitap.yazar,
        func.count(Kitap.id).label('kitap_sayisi')
    ).group_by(Kitap.yazar).order_by(text('kitap_sayisi DESC')).limit(10).all()

    yazar_etiketler = [item[0] for item in yazar_dagilimi]
    yazar_veriler = [item[1] for item in yazar_dagilimi]

    # Aylık trend
    aylik_trend = db.session.query(
        func.strftime('%Y-%m', Kitap.eklenme_tarihi).label('ay'),
        func.count(Kitap.id).label('kitap_sayisi')
    ).group_by('ay').order_by('ay').limit(12).all()

    aylik_trend_etiketler = [item[0] for item in aylik_trend]
    aylik_trend_veriler = [item[1] for item in aylik_trend]

    # Radar grafiği için veriler
    radar_etiketler = ['Kitap Sayısı', 'Yazar Sayısı', 'Yayınevi Sayısı', 'Kapak Resmi', 'Arka Kapak']
    radar_yayinevi_veriler = [
        toplam_kitap,
        toplam_yazar,
        toplam_yayinevi,
        db.session.query(func.count(Kitap.id)).filter(Kitap.kapak_resmi.isnot(None)).scalar(),
        db.session.query(func.count(Kitap.id)).filter(Kitap.arka_kapak.isnot(None)).scalar()
    ]
    radar_yazar_veriler = [v/max(radar_yayinevi_veriler)*100 for v in radar_yayinevi_veriler]
    radar_yayinevi_veriler = [v/max(radar_yayinevi_veriler)*100 for v in radar_yayinevi_veriler]

    # Detaylı istatistikler
    en_uzun_arka_kapak = db.session.query(func.max(func.length(Kitap.arka_kapak))).scalar() or 0
    kapak_resmi_olan = db.session.query(func.count(Kitap.id)).filter(Kitap.kapak_resmi.isnot(None)).scalar()
    son_eklenen_kitap = db.session.query(Kitap.baslik).order_by(Kitap.eklenme_tarihi.desc()).first()[0]
    ortalama_arka_kapak = round(db.session.query(func.avg(func.length(Kitap.arka_kapak))).scalar() or 0, 1)

    # Filtreleme için listeler
    yayinevleri = [item[0] for item in db.session.query(distinct(Kitap.yayinevi)).all()]
    yazarlar = [item[0] for item in db.session.query(distinct(Kitap.yazar)).all()]

    return render_template('istatistikler.html',
                         toplam_kitap=toplam_kitap,
                         toplam_yazar=toplam_yazar,
                         toplam_yayinevi=toplam_yayinevi,
                         ortalama_kitap=ortalama_kitap,
                         yayinevi_etiketler=yayinevi_etiketler,
                         yayinevi_veriler=yayinevi_veriler,
                         yazar_etiketler=yazar_etiketler,
                         yazar_veriler=yazar_veriler,
                         aylik_trend_etiketler=aylik_trend_etiketler,
                         aylik_trend_veriler=aylik_trend_veriler,
                         radar_etiketler=radar_etiketler,
                         radar_yayinevi_veriler=radar_yayinevi_veriler,
                         radar_yazar_veriler=radar_yazar_veriler,
                         en_uzun_arka_kapak=en_uzun_arka_kapak,
                         kapak_resmi_olan=kapak_resmi_olan,
                         son_eklenen_kitap=son_eklenen_kitap,
                         ortalama_arka_kapak=ortalama_arka_kapak,
                         yayinevleri=yayinevleri,
                         yazarlar=yazarlar)

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            print("Veritabanı tabloları oluşturuldu")
            
            # Veritabanında kitap sayısını kontrol et
            kitap_sayisi = Kitap.query.count()
            print(f"Veritabanında {kitap_sayisi} kitap var")
            
        except Exception as e:
            print(f"Veritabanı oluşturulurken hata: {str(e)}")
    
    app.run(host='0.0.0.0', port=3000) 