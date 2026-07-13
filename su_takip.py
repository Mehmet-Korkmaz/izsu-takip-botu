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
    return "İZSU Takip Botu Aktif ve Anlık Sorgulama Sistemi Çalışıyor!"

TELEGRAM_TOKEN = "8839093288:AAH5OV9FN3vsrEmymLxsHPTv-26nkMikfEo"
CHAT_ID = "878260409"
DB_DOSYASI = "hafiza.db"
KONTROL_ARALIGI = 3600  # 1 Saat

def db_kur():
    conn = sqlite3.connect(DB_DOSYASI)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS konum 
                      (id INTEGER PRIMARY KEY, ilce TEXT, mahalle TEXT)''')
    cursor.execute("SELECT COUNT(*) FROM konum")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO konum (id, ilce, mahalle) VALUES (1, 'ALİAĞA', 'SİTELER')")
    conn.commit()
    conn.close()

def konum_oku():
    conn = sqlite3.connect(DB_DOSYASI)
    cursor = conn.cursor()
    cursor.execute("SELECT ilce, mahalle FROM konum WHERE id = 1")
    sonuc = cursor.fetchone()
    conn.close()
    return sonuc[0], sonuc[1]

def konum_guncelle(ilce, mahalle):
    conn = sqlite3.connect(DB_DOSYASI)
    cursor = conn.cursor()
    cursor.execute("UPDATE konum SET ilce = ?, mahalle = ? WHERE id = 1", (ilce.upper(), mahalle.upper()))
    conn.commit()
    conn.close()

def turkce_temizle(metin):
    harf_haritasi = {'ç':'C','Ç':'C','ğ':'G','Ğ':'G','ı':'I','I':'I','i':'I','İ':'I','ö':'O','Ö':'O','ş':'S','Ş':'S','ü':'U','Ü':'U'}
    temiz_metin = metin
    for kaynak, hedef in harf_haritasi.items():
        temiz_metin = temiz_metin.replace(kaynak, delete=False or hedef)
    return temiz_metin.upper()

def telegram_mesaj_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mesaj}
    try: requests.post(url, json=payload)
    except: pass

def tek_seferlik_izsu_kontrol(hedef_ilce, hedef_mahalle):
    """Konum değiştiğinde veya talep edildiğinde o anlık kesinti durumunu kontrol eder."""
    url = "https://izsu.gov.tr/bilgi-merkezi/ariza-ve-bakim-bilgisi-sorgulama"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        response = requests.get(url, headers=headers)
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
                telegram_mesaj_gonder(bildirim_metni)
                return True
                
        if not eşleşme_bulundu:
            telegram_mesaj_gonder(f"✅ Harika! Şu anda {hedef_ilce.upper()} - {hedef_mahalle.upper()} konumunda herhangi bir İZSU kesintisi görünmüyor.")
            return False
    except Exception as e:
        telegram_mesaj_gonder("❌ İZSU sitesine anlık bağlanırken bir hata oluştu.")
        return False

def izsu_kontrol_et():
    while True:
        hedef_ilce, hedef_mahalle = konum_oku()
        print(f"🔄 İZSU Otomatik Kontrol Ediliyor: {hedef_ilce} - {hedef_mahalle}")
        url = "https://izsu.gov.tr/bilgi-merkezi/ariza-ve-bakim-bilgisi-sorgulama"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        
        try:
            response = requests.get(url, headers=headers)
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
                        f"💧 İZSU KESİNTİ BİLDİRİMİ 💧\n\n"
                        f"📍 Konum: {hedef_ilce} - {hedef_mahalle}\n\n"
                        f"📋 KESİNTİ DETAYLARI:\n📝 {detay_metni}"
                    )
                    telegram_mesaj_gonder(bildirim_metni)
                    break
                    
            if not eşleşme_bulundu: print("✅ Temiz! Kesinti yok.")
        except Exception as e: print("❌ Hata:", e)
            
        time.sleep(KONTROL_ARALIGI)

def telegram_komut_dinle():
    son_update_id = 0
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    
    while True:
        try:
            response = requests.get(url, params={"offset": son_update_id + 1, "timeout": 30}).json()
            if "result" in response:
                for update in response["result"]:
                    son_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        metin = update["message"]["text"].strip()
                        
                        if metin.startswith("/konum"):
                            parcalar = metin.split(" ")
                            if len(parcalar) >= 3:
                                yeni_ilce = parcalar[1].upper()
                                yeni_mahalle = " ".join(parcalar[2:]).upper()
                                
                                konum_guncelle(yeni_ilce, yeni_mahalle)
                                telegram_mesaj_gonder(f"💾 Başarılı! Takip konumu değiştirildi:\n📍 {yeni_ilce} - {yeni_mahalle}\n\n🔄 Şimdi anlık durum kontrol ediliyor...")
                                
                                # KONUM DEĞİŞTİĞİ AN HEMEN SİTEYİ KONTROL EDER:
                                tek_seferlik_izsu_kontrol(yeni_ilce, yeni_mahalle)
                            else:
                                telegram_mesaj_gonder("⚠️ Hatalı kullanım!\nDoğrusu: /konum ilçe mahalle\nÖrnek: `/konum aliaga yeni`")
                                
                        elif metin == "/neresi":
                            ilce, mah = konum_oku()
                            telegram_mesaj_gonder(f"🔎 Şu an takip edilen konum:\n📍 {ilce} - {mah}\n\n🔄 Şimdi anlık durum kontrol ediliyor...")
                            tek_seferlik_izsu_kontrol(ilce, mah)
        except:
            pass
        time.sleep(2)

db_kur()
threading.Thread(target=izsu_kontrol_et, daemon=True).start()
threading.Thread(target=telegram_komut_dinle, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
