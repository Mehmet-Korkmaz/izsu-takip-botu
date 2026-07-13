import os
import requests
import time
import threading
from bs4 import BeautifulSoup
from flask import Flask

# Flask Sunucusu (Render'ın kodu kapatmaması için gerekli)
app = Flask(__name__)

@app.route('/')
def home():
    return "İZSU Takip Botu Aktif ve Arka Planda Çalışıyor!"

TELEGRAM_TOKEN = "8839093288:AAH5OV9FN3vsrEmymLxsHPTv-26nkMikfEo"
CHAT_ID = "878260409"

# Doğrudan takip etmek istediğin yerleri buraya yazıyoruz (Render'da txt dosyası silinebileceği için en güvenlisi)
HEDEF_ILCE = "ALİAĞA"
HEDEF_MAHALLE = "SİTELER"
KONTROL_ARALIGI = 3600  # 1 Saat

def turkce_temizle(metin):
    harf_haritasi = {'ç':'C','Ç':'C','ğ':'G','Ğ':'G','ı':'I','I':'I','i':'I','İ':'I','ö':'O','Ö':'O','ş':'S','Ş':'S','ü':'U','Ü':'U'}
    temiz_metin = metin
    for kaynak, hedef in harf_haritasi.items():
        temiz_metin = temiz_metin.replace(kaynak, hedef)
    return temiz_metin.upper()

def telegram_mesaj_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mesaj}
    try:
        response = requests.post(url, json=payload)
    except Exception as e:
        print("❌ Telegram hatası:", e)

def izsu_kontrol_et():
    while True:
        print(f"🔄 İZSU Kontrol Ediliyor: {HEDEF_ILCE} - {HEDEF_MAHALLE}")
        url = "https://izsu.gov.tr/bilgi-merkezi/ariza-ve-bakim-bilgisi-sorgulama"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        
        try:
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, "html.parser")
            tablo_satirlari = soup.find_all("tr")
            
            aranacak_ilce = turkce_temizle(HEDEF_ILCE)
            aranacak_mahalle = turkce_temizle(HEDEF_MAHALLE)
            eşleşme_bulundu = False
            
            for satir in tablo_satirlari:
                temiz_satir_metni = turkce_temizle(satir.text)
                
                if aranacak_ilce in temiz_satir_metni and aranacak_mahalle in temiz_satir_metni:
                    eşleşme_bulundu = True
                    hucreler = [h.text.strip() for h in satir.find_all("td") if h.text.strip()]
                    detay_metni = "\n📝 ".join(hucreler) if hucreler else satir.text.strip()
                    
                    bildirim_metni = (
                        f"💧 İZSU KESİNTİ BİLDİRİMİ 💧\n\n"
                        f"📍 Konum: {HEDEF_ILCE.upper()} - {HEDEF_MAHALLE.upper()}\n\n"
                        f"📋 KESİNTİ DETAYLARI:\n📝 {detay_metni}"
                    )
                    telegram_mesaj_gonder(bildirim_metni)
                    break
                    
            if not eşleşme_bulundu:
                print("✅ Temiz! Kesinti yok.")
        except Exception as e:
            print("❌ Hata:", e)
            
        time.sleep(KONTROL_ARALIGI)

# Botu arka planda ayrı bir iş parçacığı (thread) olarak başlatıyoruz
threading.Thread(target=izsu_kontrol_et, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)