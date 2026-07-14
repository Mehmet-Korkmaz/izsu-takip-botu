import os
import requests
import time
import threading
import sqlite3
from bs4 import BeautifulSoup
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = "8839093288:AAH5OV9FN3vsrEmymLxsHPTv-26nkMikfEo"
DB_DOSYASI = "hafiza.db"
KONTROL_ARALIGI = 3600  # 1 Saat

# İzmir'in tüm ilçeleri (Kullanıcı komutsuz sadece ilçe adı yazarsa yakalamak için)
IZMIR_ILCELERI = [
    "ALİAĞA", "BALÇOVA", "BAYINDIR", "BAYRAKLI", "BERGAMA", "BEYDAĞ", "BORNOVA", "BUCA",
    "ÇEŞME", "ÇİĞLİ", "DİKİLİ", "FOÇA", "GAZİEMİR", "GÜZELBAHÇE", "KARABAĞLAR", "KARABURUN",
    "KARŞIYAKA", "KEMALPAŞA", "KINIK", "KİRAZ", "KONAK", "MENDERES", "MENEMEN", "NARLIDERE",
    "ÖDEMİŞ", "SEFERİHİSAR", "SELÇUK", "TİRE", "TORBALI", "URLA"
]

@app.route('/')
def home():
    return "İZSU Gelişmiş Webhook Takip Botu Aktif!"

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
    for kaynak, hotel in harf_haritasi.items():
        temiz_metin = temiz_metin.replace(kaynak, hotel)
    return temiz_metin.upper().strip()

def telegram_mesaj_gonder(chat_id, mesaj, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": str(chat_id), "text": mesaj, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except:
        return None

def telegram_mesaj_sabitle(chat_id, message_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/pinChatMessage"
    payload = {"chat_id": str(chat_id), "message_id": message_id, "disable_notification": True}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def tek_seferlik_izsu_kontrol(chat_id, hedef_ilce, hedef_mahalle):
    url = "https://izsu.gov.tr/bilgi-merkezi/ariza-ve-bakim-bilgisi-sorgulama"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, "html.parser")
        tablo_satirlari = soup.find_all("tr")
        
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
            bildirim_metni = f"💧 *İZSU KESİNTİ BİLDİRİMİ* 💧\n\n📍 Konum: {hedef_ilce.upper()}"
            if aranacak_mahalle != "TUMU":
                bildirim_metni += f" - {hedef_mahalle.upper()}"
            
            bildirim_metni += "\n\n📋 BULUNAN KESİNTİLER:\n\n" + "\n\n──────────────────\n\n".join(kesintiler)
            telegram_mesaj_gonder(chat_id, bildirim_metni)
        else:
            konum_str = f"{hedef_ilce.upper()}" + (f" - {hedef_mahalle.upper()}" if aranacak_mahalle != "TUMU" else " (Tüm Mahalleler)")
            telegram_mesaj_gonder(chat_id, f"✅ Harika! Şu anda *{konum_str}* konumunda herhangi bir İZSU kesintisi görünmüyor.")
            
    except Exception as e:
        print("Sorgu Hatası:", e)
        telegram_mesaj_gonder(chat_id, "❌ İZSU sitesine bağlanırken bir hata oluştu.")

def telegram_mesaj_isle(chat_id, metin):
    # Mesaj kutusunun altında duracak pratik butonlar
    klavye_butonlari = {
        "keyboard": [
            [{"text": "🔎 Konumumu Sorgula"}, {"text": "❓ Nasıl Kullanılır?"}]
        ],
        "resize_keyboard": True, # Butonların boyutu kibar dursun
        "one_time_keyboard": False # Sürekli orada kalsınlar
    }

    metin_temiz = turkce_temizle(metin)

    if metin == "/start" or metin == "❓ Nasıl Kullanılır?":
        kullanıcı_guncelle_veya_ekle(chat_id, "ALİAĞA", "SİTELER")
        
        hosgeldin_mesaji = (
            "👋 *İZSU Takip Botuna Hoş Geldiniz!*\n\n"
            "✍️ *Kullanım Şekilleri:*\n\n"
            "1️⃣ *Sadece İlçe Takibi İçin:*\n"
            "`/konum` yazıp boşluk bırakarak sadece ilçenizi ekleyin.\n"
            "_(Örnek: `/konum aliağa` )_\n\n"
            "2️⃣ *Nokta Atışı Mahalle Takibi İçin:*\n"
            "`/konum` yazıp boşluk bırakarak ilçe ve mahalle ekleyin.\n"
            "_(Örnek: `/konum aliağa siteler` )_\n\n"
            "🔎 Durumu sorgulamak için aşağıdaki butona basabilir veya direkt `/neresi` yazabilirsiniz."
        )
        
        sonuc = telegram_mesaj_gonder(chat_id, hosgeldin_mesaji, reply_markup=klavye_butonlari)
        if sonuc and "result" in sonuc:
            msg_id = sonuc["result"]["message_id"]
            telegram_mesaj_sabitle(chat_id, msg_id)
            
    elif metin.startswith("/konum"):
        parcalar = metin.split(" ")
        if len(parcalar) == 2:
            yeni_ilce = parcalar[1].upper()
            kullanıcı_guncelle_veya_ekle(chat_id, yeni_ilce, "TUMU")
            telegram_mesaj_gonder(chat_id, f"💾 Başarılı! Takip konumunuz tüm *{yeni_ilce}* geneli olarak ayarlandı.\n\n🔄 Şimdi anlık durum kontrol ediliyor...", reply_markup=klavye_butonlari)
            tek_seferlik_izsu_kontrol(chat_id, yeni_ilce, "TUMU")
        elif len(parcalar) >= 3:
            yeni_ilce = parcalar[1].upper()
            yeni_mahalle = " ".join(parcalar[2:]).upper()
            kullanıcı_guncelle_veya_ekle(chat_id, yeni_ilce, yeni_mahalle)
            telegram_mesaj_gonder(chat_id, f"💾 Başarılı! Takip konumunuz kaydedildi:\n📍 {yeni_ilce} - {yeni_mahalle}\n\n🔄 Şimdi anlık durum kontrol ediliyor...", reply_markup=klavye_butonlari)
            tek_seferlik_izsu_kontrol(chat_id, yeni_ilce, yeni_mahalle)
        else:
            telegram_mesaj_gonder(chat_id, "⚠️ Hatalı kullanım!\nDoğrusu: `/konum ilçe` veya `/konum ilçe mahalle`\nÖrnek: `/konum aliağa siteler`", reply_markup=klavye_butonlari)

    elif metin == "/neresi" or metin == "🔎 Konumumu Sorgula":
        ilce, mah = kullanıcı_oku(chat_id)
        mah_str = "Tüm Mahalleler" if mah == "TUMU" else mah
        telegram_mesaj_gonder(chat_id, f"🔎 Şu an takip ettiğiniz konum:\n📍 {ilce} - {mah_str}\n\n🔄 Şimdi anlık durum kontrol ediliyor...", reply_markup=klavye_butonlari)
        tek_seferlik_izsu_kontrol(chat_id, ilce, mah)

    # 🌟 1. EKLEME: Selamlaşma ve Teşekkür Algılayıcı
    elif metin_temiz in ["SELAM", "MERHABA", "SLM", "MRB", "SA", "AS"]:
        telegram_mesaj_gonder(chat_id, "👋 Merhaba! Size nasıl yardımcı olabilirim? Takip konumunuzu sorgulamak için aşağıdaki butonları kullanabilirsiniz.", reply_markup=klavye_butonlari)
        
    elif metin_temiz in ["TESEKKUR", "TESEKKURLER", "SAOL", "SAGOL", "EYVALLAH"]:
        telegram_mesaj_gonder(chat_id, "🌸 Rica ederim! Görevim size kesintisiz su bilgisi ulaştırmak. Herhangi bir kesintide anında bildirim göndereceğim.", reply_markup=klavye_butonlari)

    # 🌟 2. EKLEME: Sadece İlçe Adı Yazıldığında Yakalama
    elif metin_temiz in IZMIR_ILCELERI:
        telegram_mesaj_gonder(chat_id, f"💡 Sanırım takip konumunuzu değiştirmek istiyorsunuz.\n\nKonumunuzu *{metin_temiz}* yapmak için lütfen aşağıdaki gibi yazıp gönderin:\n\n`/konum {metin.lower()}`", reply_markup=klavye_butonlari)

    # 🌟 3. EKLEME: Anlaşılmayan Diğer Tüm Mesajlar İçin Gelişmiş Fallback
    else:
        yardim_mesaji = (
            "⚠️ *Gönderdiğiniz mesajı tam anlayamadım...*\n\n"
            "Beni kontrol etmek için alttaki butonları kullanabilir ya da şu komutları yazabilirsiniz:\n\n"
            "📍 *Yeni Konum Ayarlamak İçin:*\n"
            "`/konum ilçe` veya `/konum ilçe mahalle`\n\n"
            "🔎 *Mevcut Konumu Sorgulamak İçin:*\n"
            "`/neresi` yazabilirsiniz."
        )
        telegram_mesaj_gonder(chat_id, yardim_mesaji, reply_markup=klavye_butonlari)

def izsu_otomatik_kontrol_et():
    while True:
        try:
            kullanıcılar = tum_kullanıcıları_getir()
            if kullanıcılar:
                url = "https://izsu.gov.tr/bilgi-merkezi/ariza-ve-bakim-bilgisi-sorgulama"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                response = requests.get(url, headers=headers, timeout=20)
                soup = BeautifulSoup(response.content, "html.parser")
                tablo_satirlari = soup.find_all("tr")
                
                for chat_id, hedef_ilce, hedef_mahalle in kullanıcılar:
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
                        bildirim_metni = f"💧 *İZSU OTOMATİK BİLDİRİM* 💧\n\n📍 Konum: {hedef_ilce.upper()}"
                        if aranacak_mahalle != "TUMU": bildirim_metni += f" - {hedef_mahalle.upper()}"
                        bildirim_metni += "\n\n📋 KESİNTİLER:\n\n" + "\n\n──────────────────\n\n".join(kesintiler)
                        telegram_mesaj_gonder(chat_id, bildirim_metni)
        except Exception as e:
            print("Otomatik kontrol hatası:", e)
        time.sleep(KONTROL_ARALIGI)

def webhook_set():
    time.sleep(5)
    base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://izsu-takip-botu.onrender.com")
    webhook_url = f"{base_url}/webhook"
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    try:
        r = requests.post(api_url, json={"url": webhook_url}, timeout=10)
        print("Telegram Webhook Durumu:", r.json())
    except Exception as e:
        print("Webhook Kurulum Hatası:", e)

db_kur()
threading.Thread(target=izsu_otomatik_kontrol_et, daemon=True).start()
threading.Thread(target=webhook_set, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
