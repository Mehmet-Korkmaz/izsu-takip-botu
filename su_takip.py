import os
import requests
import time
import threading
import psycopg2
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string

app = Flask(__name__)

TELEGRAM_TOKEN = "8839093288:AAH5OV9FN3vsrEmymLxsHPTv-26nkMikfEo"
# Render Environment panelinden gelecek olan Supabase adresi
DATABASE_URL = os.environ.get("DATABASE_URL")
KONTROL_ARALIGI = 60  # Test için 1 dakika (60 saniye) tutuyoruz

# İzmir'in tüm ilçeleri
IZMIR_ILCELERI = [
    "ALİAĞA", "BALÇOVA", "BAYINDIR", "BAYRAKLI", "BERGAMA", "BEYDAĞ", "BORNOVA", "BUCA",
    "ÇEŞME", "ÇİĞLİ", "DİKİLİ", "FOÇA", "GAZİEMİR", "GÜZELBAHÇE", "KARABAĞLAR", "KARABURUN",
    "KARŞIYAKA", "KEMALPAŞA", "KINIK", "KİRAZ", "KONAK", "MENDERES", "MENEMEN", "NARLIDERE",
    "ÖDEMİŞ", "SEFERİHİSAR", "SELÇUK", "TİRE", "TORBALI", "URLA"
]

# TEST İÇİN SAHTE İZSU VERİTABANI DEĞİŞKENİ
sahte_izsu_verisi = """
<tr>
    <td>ALİAĞA</td>
    <td>SİTELER MAHALLESİ</td>
    <td>14.07.2026 16:00</td>
    <td>Ana boru arızası nedeniyle bölgeye su verilememektedir.</td>
</tr>
"""

@app.route('/')
def home():
    return "İZSU Kalıcı Supabase Takip Botu Aktif!"

@app.route('/test-paneli', methods=['GET', 'POST'])
def test_paneli():
    global sahte_izsu_verisi
    if request.method == 'POST':
        sahte_izsu_verisi = request.form.get('izsu_html', '')
        return """
        <div style="color: green; font-weight: bold; margin-bottom: 20px;">✓ Sahte İZSU Verisi Güncellendi! Bot 1 dakika içinde kontrol edecek.</div>
        <a href="/test-paneli">Panele Geri Dön</a>
        """
    
    html_sablonu = """
    <html>
    <head><title>İZSU Simülatör Paneli</title></head>
    <body style="font-family: Arial, sans-serif; margin: 40px; background-color: #f4f6f9;">
        <h2>🧪 İZSU Kesinti Takip Test Paneli (Kalıcı Supabase Sürümü)</h2>
        <p>Aşağıdaki HTML alanını değiştirerek İZSU sitesinde kesinti varmış veya sular gelmiş gibi davranabilirsin.</p>
        <form method="POST">
            <textarea name="izsu_html" rows="12" style="width: 100%; font-family: monospace; padding: 10px; font-size: 14px;">{{ tablo_icerigi }}</textarea>
            <br><br>
            <input type="submit" value="İZSU Sitesini Güncelle (Kaydet)" style="padding: 10px 20px; background-color: #007bff; color: white; border: none; cursor: pointer; border-radius: 5px;">
        </form>
    </body>
    </html>
    """
    return render_template_string(html_sablonu, tablo_icerigi=sahte_izsu_verisi)

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    try:
        veri = request.get_json()
        if "message" in veri and "text" in veri["message"]:
            chat_id = veri["message"]["chat"]["id"]
            metin = veri["message"]["text"].strip()
            telegram_mesaj_isle(chat_id, metin)
    except Exception as e:
        print("Webhook İşleme Hatası:", e)
    return "OK", 200

# SUPABASE POSTGRESQL VERİTABANI BAĞLANTISI VE TABLO KURULUMU
def db_kur():
    if not DATABASE_URL:
        print("HATA: DATABASE_URL Environment Variable bulunamadı!")
        return
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS kullanicilar 
                          (chat_id TEXT PRIMARY KEY, ilce TEXT, mahalle TEXT, son_durum TEXT)''')
        conn.commit()
        cursor.close()
        conn.close()
        print("Supabase Bağlantısı Başarılı ve Tablo Hazır!")
    except Exception as e:
        print("Supabase Kurulum Hatası:", e)

def kullanici_guncelle_veya_ekle(chat_id, ilce, mahalle):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO kullanicilar (chat_id, ilce, mahalle, son_durum) VALUES (%s, %s, %s, NULL)
                          ON CONFLICT (chat_id) DO UPDATE SET ilce = EXCLUDED.ilce, mahalle = EXCLUDED.mahalle, son_durum = NULL""",
                       (str(chat_id), ilce.upper().strip(), mahalle.upper().strip()))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("Kullanıcı güncelleme hatası:", e)

def kullanici_son_durum_guncelle(chat_id, yeni_durum):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("UPDATE kullanicilar SET son_durum = %s WHERE chat_id = %s", (yeni_durum, str(chat_id)))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("Son durum güncelleme hatası:", e)

def kullanici_oku(chat_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT ilce, mahalle FROM kullanicilar WHERE chat_id = %s", (str(chat_id),))
        sonuc = cursor.fetchone()
        cursor.close()
        conn.close()
        return sonuc if sonuc else ("ALİAĞA", "SİTELER")
    except:
        return ("ALİAĞA", "SİTELER")

def tum_kullanicilari_getir_detayli():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, ilce, mahalle, son_durum FROM kullanicilar")
        sonuclar = cursor.fetchall()
        cursor.close()
        conn.close()
        return sonuclar
    except Exception as e:
        print("Kullanıcı listesi çekme hatası:", e)
        return []

def turkce_temizle(metin):
    if not metin: return ""
    harf_haritasi = {'ç':'C','Ç':'C','ğ':'G','Ğ':'G','ı':'I','I':'I','i':'I','İ':'I','ö':'O','Ö':'O','ş':'S','Ş':'S','ü':'U','Ü':'U'}
    temiz_metin = metin
    for kaynak, hotel in harf_haritasi.items():
        temiz_metin = temiz_metin.replace(kaynak, hotel)
    return temiz_metin.upper().strip()

def telegram_mesaj_gonder(chat_id, mesaj, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": str(chat_id), "text": mesaj, "parse_mode": "Markdown"}
    if reply_markup: payload["reply_markup"] = reply_markup
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except: return None

def telegram_mesaj_sabitle(chat_id, message_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/pinChatMessage"
    payload = {"chat_id": str(chat_id), "message_id": message_id, "disable_notification": True}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def test_izsu_tablo_oku():
    soup = BeautifulSoup(sahte_izsu_verisi, "html.parser")
    return soup.find_all("tr")

def tek_seferlik_izsu_kontrol(chat_id, hedef_ilce, hedef_mahalle):
    try:
        tablo_satirlari = test_izsu_tablo_oku()
        aranacak_ilce = turkce_temizle(hedef_ilce)
        aranacak_mahalle = turkce_temizle(hedef_mahalle)
        
        kesintiler = []
        for satir in tablo_satirlari:
            temiz_satir_metni = turkce_temizle(satir.text)
            if aranacak_mahalle == "TUMU":
                if aranacak_ilce in temiz_satir_metni:
                    hucreler = [h.text.strip() for h in satir.find_all("td") if h.text.strip()]
                    if hucreler: kesintiler.append("\n📝 ".join(hucreler))
            else:
                if aranacak_ilce in temiz_satir_metni and aranacak_mahalle in temiz_satir_metni:
                    hucreler = [h.text.strip() for h in satir.find_all("td") if h.text.strip()]
                    if hucreler:
                        kesintiler.append("\n📝 ".join(hucreler))
                        break
                        
        if kesintiler:
            yeni_hafiza_durumu = "||".join(kesintiler)
            kullanici_son_durum_guncelle(chat_id, yeni_hafiza_durumu)
            bildirim_metni = f"💧 *İZSU KESİNTİ BİLDİRİMİ* 💧\n\n📍 Konum: {hedef_ilce.upper()}"
            if aranacak_mahalle != "TUMU": bildirim_metni += f" - {hedef_mahalle.upper()}"
            bildirim_metni += "\n\n📋 BULUNAN KESİNTİLER:\n\n" + "\n\n──────────────────\n\n".join(kesintiler)
            telegram_mesaj_gonder(chat_id, bildirim_metni)
        else:
            kullanici_son_durum_guncelle(chat_id, "YOK")
            konum_str = f"{hedef_ilce.upper()}" + (f" - {hedef_mahalle.upper()}" if aranacak_mahalle != "TUMU" else " (Tüm Mahalleler)")
            telegram_mesaj_gonder(chat_id, f"✅ Harika! Şu anda *{konum_str}* konumunda herhangi bir İZSU kesintisi görünmüyor.")
    except Exception as e:
        print("Sorgu Hatası:", e)

def telegram_mesaj_isle(chat_id, metin):
    klavye_butonlari = {
        "keyboard": [[{"text": "🔎 Konumumu Sorgula"}, {"text": "❓ Nasıl Kullanılır?"}]],
        "resize_keyboard": True, "one_time_keyboard": False
    }
    parcalar = metin.split(" ")
    ilk_kelime = turkce_temizle(parcalar[0])

    if not metin.startswith("/") and ilk_kelime in IZMIR_ILCELERI:
        metin = f"/konum {metin}"

    metin_temiz = turkce_temizle(metin)

    if metin == "/start" or metin == "❓ Nasıl Kullanılır?":
        kullanici_guncelle_veya_ekle(chat_id, "ALİAĞA", "SİTELER")
        hosgeldin_mesaji = (
            "👋 *İZSU Kalıcı Bulut Botuna Hoş Geldiniz!*\n\n"
            "Takip etmek istediğiniz konumu direkt yazıp gönderin.\n"
            "👉 *Örnek:* `aliağa siteler` yazıp gönderin."
        )
        sonuc = telegram_mesaj_gonder(chat_id, hosgeldin_mesaji, reply_markup=klavye_butonlari)
        if sonuc and "result" in sonuc:
            telegram_mesaj_sabitle(chat_id, sonuc["result"]["message_id"])
            
    elif metin.startswith("/konum"):
        parcalar = metin.split(" ")
        if len(parcalar) == 2:
            yeni_ilce = parcalar[1].upper()
            kullanici_guncelle_veya_ekle(chat_id, yeni_ilce, "TUMU")
            telegram_mesaj_gonder(chat_id, f"💾 Başarılı! Takip konumunuz tüm *{yeni_ilce}* geneli olarak ayarlandı.", reply_markup=klavye_butonlari)
            tek_seferlik_izsu_kontrol(chat_id, yeni_ilce, "TUMU")
        elif len(parcalar) >= 3:
            yeni_ilce = parcalar[1].upper()
            yeni_mahalle = " ".join(parcalar[2:]).upper()
            kullanici_guncelle_veya_ekle(chat_id, yeni_ilce, yeni_mahalle)
            telegram_mesaj_gonder(chat_id, f"💾 Başarılı! Takip konumunuz kaydedildi:\n📍 {yeni_ilce} - {yeni_mahalle}", reply_markup=klavye_butonlari)
            tek_seferlik_izsu_kontrol(chat_id, yeni_ilce, yeni_mahalle)

    elif metin == "/neresi" or metin == "🔎 Konumumu Sorgula":
        ilce, mah = kullanici_oku(chat_id)
        mah_str = "Tüm Mahalleler" if mah == "TUMU" else mah
        telegram_mesaj_gonder(chat_id, f"🔎 Şu an takip ettiğiniz konum:\n📍 {ilce} - {mah_str}", reply_markup=klavye_butonlari)
        tek_seferlik_izsu_kontrol(chat_id, ilce, mah)

def izsu_otomatik_kontrol_et():
    while True:
        try:
            kullanicilar = tum_kullanicilari_getir_detayli()
            if kullanicilar:
                tablo_satirlari = test_izsu_tablo_oku()
                satirlar_temiz = []
                for satir in tablo_satirlari:
                    hucreler = [h.text.strip() for h in satir.find_all("td") if h.text.strip()]
                    if hucreler: satirlar_temiz.append((turkce_temizle(satir.text), hucreler))

                for chat_id, hedef_ilce, hedef_mahalle, eski_durum in kullanicilar:
                    aranacak_ilce = turkce_temizle(hedef_ilce)
                    aranacak_mahalle = turkce_temizle(hedef_mahalle)
                    
                    kesintiler = []
                    for temiz_satir_metni, hucreler in satirlar_temiz:
                        if aranacak_mahalle == "TUMU":
                            if aranacak_ilce in temiz_satir_metni: kesintiler.append("\n📝 ".join(hucreler))
                        else:
                            if aranacak_ilce in temiz_satir_metni and aranacak_mahalle in temiz_satir_metni:
                                kesintiler.append("\n📝 ".join(hucreler))
                                break
                                
                    yeni_durum = "||".join(kesintiler) if kesintiler else "YOK"
                    if eski_durum is None: eski_durum = "YOK"
                    
                    if eski_durum != yeni_durum:
                        if yeni_durum == "YOK":
                            bildirim_metni = f"🎉 *MÜJDE! SULARINIZ GELDİ!* 💧\n\n📍 *{hedef_ilce.upper()}"
                            if aranacak_mahalle != "TUMU": bildirim_metni += f" - {hedef_mahalle.upper()}"
                            bildirim_metni += "* konumundaki su kesintisi sona erdi. ✅"
                            telegram_mesaj_gonder(chat_id, bildirim_metni)
                        else:
                            formatli_kesintiler = yeni_durum.replace("||", "\n\n──────────────────\n\n")
                            bildirim_metni = f"🚨 *YENİ İZSU BİLDİRİMİ* 🚨\n\n📍 Konum: {hedef_ilce.upper()}"
                            if aranacak_mahalle != "TUMU": bildirim_metni += f" - {hedef_mahalle.upper()}"
                            bildirim_metni += "\n\n📋 BULUNAN KESİNTİ DETAYLARI:\n\n" + formatli_kesintiler
                            telegram_mesaj_gonder(chat_id, bildirim_metni)
                        
                        kullanici_son_durum_guncelle(chat_id, yeni_durum)
        except Exception as e:
            print("Otomatik kontrol hatası:", e)
        time.sleep(KONTROL_ARALIGI)

def webhook_set():
    time.sleep(5)
    base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://izsu-takip-botu.onrender.com")
    webhook_url = f"{base_url}/webhook"
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    try: requests.post(api_url, json={"url": webhook_url}, timeout=10)
    except: pass

db_kur()
threading.Thread(target=izsu_otomatik_kontrol_et, daemon=True).start()
threading.Thread(target=webhook_set, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
