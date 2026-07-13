import os
import requests
import time
import threading
import sqlite3
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "İZSU Çoklu Kullanıcı Destekli Takip Botu Aktif ve Kararlı Çalışıyor!"

TELEGRAM_TOKEN = "8839093288:AAH5OV9FN3vsrEmymLxsHPTv-26nkMikfEo"
DB_DOSYASI = "hafiza.db"
KONTROL_ARALIGI = 3600  # 1 Saat

def db_kur():
    conn = sqlite3.connect(DB_DOSYASI)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS kullanıcılar 
                      (chat_id TEXT PRIMARY KEY, ilce TEXT, mahalle TEXT)''')
    conn.commit()
    conn.close()

def kullanıcı_guncelle_veya_ekle(chat_id, ilce, mahalle):
    conn = sqlite3.connect(DB_DOSYASI)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO kullanıcılar (chat_id, ilce, mahalle) VALUES (?, ?, ?)", 
                   (str(chat_id), ilce.upper().strip(), mahalle.upper().strip()))
    conn.commit()
    conn.close()

def kullanıcı_oku(chat_id):
    conn = sqlite3.connect(DB_DOSYASI)
    cursor = conn.cursor()
    cursor.execute("SELECT ilce, mahalle FROM kullanıcılar WHERE chat_id = ?", (str(chat_id),))
    sonuc = cursor.fetchone()
    conn.close()
    return sonuc if sonuc else ("ALİAĞA", "SİTELER")

def tum_kullanıcıları_getir():
    conn = sqlite3.connect(DB_DOSYASI)
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, ilce, mahalle FROM kullanıcılar")
    sonuclar = cursor.fetchall()
    conn.close()
    return sonuclar

def turkce_temizle(metin):
    if not metin:
        return ""
    harf_haritasi = {'ç':'C','Ç':'C','ğ':'G','Ğ':'G','ı':'I','I':'I','i':'I','İ':'I','ö':'O','Ö':'O','ş':'S','Ş':'S','ü':'U','Ü':'U'}
    temiz_metin = metin
    for kaynak, hedef in harf_haritasi.items():
        temiz_metin = temiz_metin.replace(kaynak, hedef)
    return temiz_metin.upper().strip()

def telegram_mesaj_gonder(chat_id, mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": str(chat_id), "text": mesaj}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def tek_seferlik_izsu_kontrol(chat_id, hedef_ilce, hedef_mahalle):
    url = "https://izsu.gov.tr/bilgi-merkezi/ariza-ve-bakim-bilgisi-sorgulama"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, "html.parser")
        tablo_satirlari = soup.find_all("tr")
        
        aranacak_ilce = turkce_temizle(hedef_ilce)
        aranacak_mahalle = turkce_temizle(hedef_mahalle)
        eşleşme_bulundu = False
        
        for satir in tablo_satirlari:
            temiz_satir_metni = turkce_temizle(satir.text)
            
            if aranacak_ilce in temiz_satir_metni and aranacak_mahalle in temiz_satir_metni:
                eşleşme_bulundu = True
                hucreler = [h.text.strip() for h in satir.find_all("td") if h.text.strip()]
                detay_metni = "\n📝 ".join(hucreler) if hucreler else satir.text.strip()
                
                bildirim_metni = (
                    f"💧 ANLIK İZSU KESİNTİ BİLDİRİMİ 💧\n\n"
                    f"📍 Konum: {hedef_ilce.upper()} - {hedef_mahalle.upper()}\n\n"
                    f"📋 KESİNTİ DETAYLARI:\n📝 {detay_metni}"
                )
                telegram_mesaj_gonder(chat_id, bildirim_metni)
                return
                
        if not eşleşme_bulundu:
            telegram_mesaj_gonder(chat_id, f"✅ Harika! Şu anda {hedef_ilce.upper()} - {hedef_mahalle.upper()} konumunda herhangi bir İZSU kesintisi görünmüyor.")
    except Exception as e:
        print("Sorgu Hatası:", e)
        telegram_mesaj_gonder(chat_id, "❌ İZSU sitesine bağlanırken sistemsel bir hata oluştu. Lütfen birkaç dakika sonra tekrar deneyin.")

def izsu_otomatik_kontrol_et():
    while True:
        try:
            kullanıcılar = tum_kullanıcıları_getir()
            if kullanıcılar:
                url = "https://izsu.gov.tr/bilgi-merkezi/ariza-ve-bakim-bilgisi-sorgulama"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = requests.get(url, headers=headers, timeout=20)
                soup = BeautifulSoup(response.content, "html.parser")
                tablo_satirlari = soup.find_all("tr")
                
                for chat_id, hedef_ilce, hedef_mahalle in kullanıcılar:
                    aranacak_ilce = turkce_temizle(hedef_ilce)
                    aranacak_mahalle = turkce_temizle(hedef_mahalle)
                    
                    for satir in tablo_satirlari:
                        temiz_satir_metni = turkce_temizle(satir.text)
                        if aranacak_ilce in temiz_satir_metni and aranacak_mahalle in temiz_satir_metni:
                            hucreler = [h.text.strip() for h in satir.find_all("td") if h.text.strip()]
                            detay_metni = "\n📝 ".join(hucreler) if hucreler else satir.text.strip()
                            
                            bildirim_metni = (
                                f"💧 İZSU KESİNTİ BİLDİRİMİ 💧\n\n"
                                f"📍 Konum: {hedef_ilce.upper()} - {hedef_mahalle.upper()}\n\n"
                                f"📋 KESİNTİ DETAYLARI:\n📝 {detay_metni}"
                            )
                            telegram_mesaj_gonder(chat_id, bildirim_metni)
                            break
        except Exception as e:
            print("Otomatik kontrol hatası:", e)
        time.sleep(KONTROL_ARALIGI)

def telegram_komut_dinle():
    son_update_id = 0
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    
    while True:
        try:
            response = requests.get(url, params={"offset": son_update_id + 1, "timeout": 30}, timeout=35).json()
            if "result" in response:
                for update in response["result"]:
                    son_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        metin = update["message"]["text"].strip()
                        
                        if metin == "/start":
                            kullanıcı_guncelle_veya_ekle(chat_id, "ALİAĞA", "SİTELER")
                            telegram_mesaj_gonder(chat_id, "👋 İZSU Takip Botuna Hoş Geldiniz!\n\nVarsayılan konumunuz 'ALİAĞA - SİTELER' olarak ayarlandı.\n\n✍️ Değiştirmek için:\n`/konum ilçe mahalle` yazabilirsiniz.\nÖrnek: `/konum aliaga yeni`\n\n🔎 Mevcut konumunuzu sorgulamak için: `/neresi` yazabilirsiniz.")
                        
                        elif metin.startswith("/konum"):
                            parcalar = metin.split(" ")
                            if len(parcalar) >= 3:
                                yeni_ilce = parcalar[1].upper()
                                yeni_mahalle = " ".join(parcalar[2:]).upper()
                                
                                kullanıcı_guncelle_veya_ekle(chat_id, yeni_ilce, yeni_mahalle)
                                telegram_mesaj_gonder(chat_id, f"💾 Başarılı! Takip konumunuz kaydedildi:\n📍 {yeni_ilce} - {yeni_mahalle}\n\n🔄 Şimdi anlık durum kontrol ediliyor...")
                                tek_seferlik_izsu_kontrol(chat_id, yeni_ilce, yeni_mahalle)
                            else:
                                telegram_mesaj_gonder(chat_id, "⚠️ Hatalı kullanım!\nDoğrusu: /konum ilçe mahalle\nÖrnek: `/konum aliaga yeni`")
                                
                        elif metin == "/neresi":
                            ilce, mah = kullanıcı_oku(chat_id)
                            telegram_mesaj_gonder(chat_id, f"🔎 Şu an takip ettiğiniz konum:\n📍 {ilce} - {mah}\n\n🔄 Şimdi anlık durum kontrol ediliyor...")
                            tek_seferlik_izsu_kontrol(chat_id, ilce, mah)
        except Exception as e:
            print("Telegram dinleme hatası:", e)
        time.sleep(2)

db_kur()
threading.Thread(target=izsu_otomatik_kontrol_et, daemon=True).start()
threading.Thread(target=telegram_komut_dinle, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
