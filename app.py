from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
import os
import json
from datetime import datetime
from modules.veri_isleyici import VeriIsleyici
from modules.analiz import ArsaAnalizci
from modules.sunum_olusturucu import SunumOlusturucu
from modules.web_scraping import ParselSorgu, SahibindenScraper, InsaatAlaniHesaplayici

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__)

# Dizin yapılandırması
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates/sunum')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# Dizinleri oluştur
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Modülleri başlat
veri_isleyici = VeriIsleyici(DATA_DIR)
analizci = ArsaAnalizci()
sunum_olusturucu = SunumOlusturucu(TEMPLATES_DIR)
parsel_sorgu = ParselSorgu()
sahibinden_scraper = SahibindenScraper()
insaat_hesaplayici = InsaatAlaniHesaplayici()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/parselsorgu', methods=['POST'])
def parselsorgu():
    """
    Parselsorgu.tkgm.gov.tr'den parsel bilgilerini çeker.
    """
    try:
        data = request.json
        il = data.get('il')
        ilce = data.get('ilce')
        mahalle = data.get('mahalle')
        ada = data.get('ada')
        parsel = data.get('parsel')
        
        # Parsel bilgilerini çek
        sonuc = parsel_sorgu.sorgula(il, ilce, mahalle, ada, parsel)
        
        return jsonify(sonuc)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/bolge-fiyat', methods=['POST'])
def bolge_fiyat():
    """
    Sahibinden.com'dan bölge fiyat bilgilerini çeker.
    """
    try:
        data = request.json
        il = data.get('il')
        ilce = data.get('ilce')
        mahalle = data.get('mahalle')
        imar_durumu = data.get('imar_durumu')
        
        # Bölge fiyat bilgilerini çek
        sonuc = sahibinden_scraper.get_arsa_fiyatlari(il, ilce, mahalle, imar_durumu)
        
        return jsonify(sonuc)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/submit', methods=['POST'])
def submit():
    # Form verilerini al
    arsa_data = {
        'konum': {
            'il': request.form.get('il'),
            'ilce': request.form.get('ilce'),
            'mahalle': request.form.get('mahalle')
        },
        'parsel': {
            'ada': request.form.get('ada'),
            'parsel': request.form.get('parsel')
        },
        'metrekare': float(request.form.get('metrekare')),
        'imar_durumu': request.form.get('imar_durumu'),
        'fiyat': float(request.form.get('fiyat')),
        'bolge_fiyat': float(request.form.get('bolge_fiyat')),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # TAKS/KAKS bilgileri varsa ekle
    if request.form.get('taks') and request.form.get('kaks'):
        taks = float(request.form.get('taks'))
        kaks = float(request.form.get('kaks'))
        
        # İnşaat alanı hesapla
        insaat_hesaplama = insaat_hesaplayici.hesapla(arsa_data['metrekare'], taks, kaks)
        
        # Hata kontrolü
        if 'error' in insaat_hesaplama:
            return redirect(url_for('index'))
        
        arsa_data['taks'] = taks
        arsa_data['kaks'] = kaks
        arsa_data['insaat_hesaplama'] = insaat_hesaplama
    
    # Analiz et
    arsa_data = analizci.analiz_et(arsa_data)
    
    # Özet metinleri oluştur
    arsa_data['ozet'] = analizci.ozetle(arsa_data)
    
    # Verileri kaydet
    file_id = veri_isleyici.kaydet(arsa_data)
    
    # Sonuç sayfasına yönlendir
    return redirect(url_for('sonuc', file_id=file_id))

@app.route('/sonuc/<file_id>')
def sonuc(file_id):
    # Verileri yükle
    arsa_data = veri_isleyici.yukle(file_id)
    
    # Dosya yoksa ana sayfaya yönlendir
    if not arsa_data:
        return redirect(url_for('index'))
    
    return render_template('sonuc.html', arsa=arsa_data, file_id=file_id)

@app.route('/generate/<format>/<file_id>')
def generate(format, file_id):
    # Verileri yükle
    arsa_data = veri_isleyici.yukle(file_id)
    
    # Dosya yoksa ana sayfaya yönlendir
    if not arsa_data:
        return redirect(url_for('index'))
    
    # Dosya adı oluştur
    konum = f"{arsa_data['konum']['il']}_{arsa_data['konum']['ilce']}"
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    if format == 'word':
        # Word belgesi oluştur
        output_filename = f"arsa_analiz_{konum}_{timestamp}.docx"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        sunum_olusturucu.olustur_word(arsa_data, output_path)
        return send_file(output_path, as_attachment=True, download_name=output_filename)
    
    elif format == 'ppt':
        # PowerPoint sunumu oluştur
        output_filename = f"arsa_analiz_{konum}_{timestamp}.pptx"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        sunum_olusturucu.olustur_powerpoint(arsa_data, output_path)
        return send_file(output_path, as_attachment=True, download_name=output_filename)
    
    else:
        # Geçersiz format
        return redirect(url_for('sonuc', file_id=file_id))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
