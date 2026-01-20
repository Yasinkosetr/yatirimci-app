import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import yfinance as yf
import time
import hashlib

# --- 1. AYARLAR ---
st.set_page_config(page_title="Yatırımcı Pro V9.0", layout="wide", initial_sidebar_state="expanded")

# --- 2. TASARIM ---
st.markdown(
    """
    <style>
    .stApp {background-color: #0E1117; background-image: linear-gradient(to right, #0f2027, #203a43, #2c5364);}
    [data-testid="stSidebar"] {background-color: #1c1c1e; border-right: 1px solid #333;}
    html, body, [class*="css"] {font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #E0E0E0;}
    .stButton>button {background-image: linear-gradient(19deg, #F4D03F 0%, #16A085 100%); color: white; border: none; border-radius: 10px; width: 100%;}
    [data-testid="stMetricValue"] {font-size: 1.4rem !important; color: #00ff00;}
    /* Tablo ve metrik kutularını özelleştirme */
    div[data-testid="stMetric"] {background-color: rgba(255,255,255,0.05); padding: 10px; border-radius: 10px; text-align: center;}
    </style>
    """, unsafe_allow_html=True
)

# --- 3. GÜVENLİK ---
def sifrele(sifre): return hashlib.sha256(str.encode(sifre)).hexdigest()
def sifre_kontrol(girilen, db_sifre): return sifrele(girilen) == db_sifre

# --- 4. GOOGLE SHEETS ---
def get_sheets():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets ayarı bulunamadı.")
            st.stop()
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], ['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        # 👇 LİNKİ BURAYA YAPIŞTIR 👇
        sheet_url = "https://docs.google.com/spreadsheets/d/1ijPoTKNsXZBMxdRdMa7cpEhbSYt9kMwoqf5nZFNi7S8/edit?gid=499369690#gid=499369690"
        spreadsheet = client.open_by_url(sheet_url)
        return spreadsheet.worksheet("Islemler"), spreadsheet.worksheet("Uyeler")
    except Exception as e:
        st.error(f"Veri tabanı hatası: {e}")
        st.stop()

ws_islemler, ws_uyeler = get_sheets()

# --- 5. YARDIMCI FONKSİYONLAR ---
def zorla_sayi_yap(deger):
    try:
        metin = str(deger).strip().replace("TL", "").replace("$", "").replace(" ", "")
        if "," in metin: metin = metin.replace(".", "").replace(",", ".")
        elif metin.count(".") > 1: metin = metin.replace(".", "")
        return float(metin)
    except: return 0.0

@st.cache_data(ttl=60)
def veri_getir_ozel(hisse_kodu):
    sembol = str(hisse_kodu).strip().upper()
    if not sembol.endswith(".IS") and "-" not in sembol:
        # Önce TR dene
        try:
            tik = yf.Ticker(f"{sembol}.IS")
            h = tik.history(period="1d")
            if not h.empty: return h['Close'].iloc[-1], tik.info.get('longName', sembol), f"{sembol}.IS"
        except: pass
    
    # Global dene
    try:
        tik = yf.Ticker(sembol)
        h = tik.history(period="1d")
        if not h.empty: return h['Close'].iloc[-1], tik.info.get('longName', sembol), sembol
    except: pass
    return None, sembol, sembol

@st.cache_data(ttl=300)
def piyasa_verileri_getir():
    return ['THYAO.IS', 'GARAN.IS', 'ASELS.IS', 'SASA.IS', 'EREGL.IS', 'TUPRS.IS', 'FROTO.IS', 'KCHOL.IS', 'SISE.IS', 'BIMAS.IS', 'AKBNK.IS', 'HEKTS.IS', 'PETKM.IS', 'KONTR.IS', 'ASTOR.IS']

def portfoy_hesapla(df):
    if df.empty: return {}, 0.0
    if 'Tarih' in df.columns: df['Tarih'] = pd.to_datetime(df['Tarih'], errors='coerce')
    df = df.sort_values(by='Tarih')
    portfoy, gerceklesen = {}, 0.0
    for _, row in df.iterrows():
        h, i, a, f = row['Hisse Adı'], row['İşlem'], zorla_sayi_yap(row['Lot']), zorla_sayi_yap(row['Fiyat'])
        if h not in portfoy: portfoy[h] = {'Adet': 0.0, 'Ort_Maliyet': 0.0}
        mevcut = portfoy[h]
        if i == "Alış":
            toplam_adet = mevcut['Adet'] + a
            mevcut['Ort_Maliyet'] = ((mevcut['Adet'] * mevcut['Ort_Maliyet']) + (a * f)) / toplam_adet if toplam_adet > 0 else 0
            mevcut['Adet'] = toplam_adet
        elif i == "Satış":
            gerceklesen += (f - mevcut['Ort_Maliyet']) * a
            mevcut['Adet'] = max(0, mevcut['Adet'] - a)
    return portfoy, gerceklesen

# 🔥 HİSSE DETAY SAYFASI İÇİN PERFORMANS HESAPLAYICI 🔥
def hisse_performans_analizi(sembol):
    ticker = yf.Ticker(sembol)
    # Geçmiş verileri çek (5 yıllık)
    hist = ticker.history(period="5y")
    
    if hist.empty: return None
    
    suan = hist['Close'].iloc[-1]
    
    # Zaman dilimlerine göre değişim hesapla
    def degisim(gun):
        if len(hist) > gun:
            eski = hist['Close'].iloc[-gun-1]
            yuzde = ((suan - eski) / eski) * 100
            return yuzde
        return 0.0

    return {
        "Fiyat": suan,
        "1 Gün": degisim(1),
        "1 Hafta": degisim(5),
        "1 Ay": degisim(21),
        "3 Ay": degisim(63),
        "1 Yıl": degisim(252),
        "5 Yıl": degisim(1260) # Yaklaşık iş günü
    }

# --- 6. GİRİŞ SİSTEMİ ---
if 'giris_yapildi' not in st.session_state: st.session_state.giris_yapildi = False
if 'kullanici_adi' not in st.session_state: st.session_state.kullanici_adi = ""
# Seçilen hisseyi hafızada tutmak için:
if 'secilen_hisse_detay' not in st.session_state: st.session_state.secilen_hisse_detay = None

def giris_sayfasi():
    st.markdown("<h1 style='text-align: center;'>🔐 Yatırımcı Pro Giriş</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Giriş", "Kayıt"])
    with t1:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            u = st.text_input("Kullanıcı")
            p = st.text_input("Şifre", type="password")
            if st.button("Giriş"):
                udf = pd.DataFrame(ws_uyeler.get_all_records())
                if not udf.empty and u in udf['Kullanıcı Adı'].values:
                    if sifre_kontrol(p, udf[udf['Kullanıcı Adı']==u]['Şifre'].values[0]):
                        st.session_state.giris_yapildi = True
                        st.session_state.kullanici_adi = u
                        st.rerun()
                    else: st.error("Hatalı Şifre")
                else: st.error("Kullanıcı Yok")
    with t2:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            nu = st.text_input("Yeni Kullanıcı")
            np = st.text_input("Yeni Şifre", type="password")
            if st.button("Kayıt Ol"):
                try:
                    ws_uyeler.append_row([nu, sifrele(np), datetime.now().strftime("%Y-%m-%d")])
                    st.success("Kayıt Başarılı")
                except: st.error("Hata")

if not st.session_state.giris_yapildi:
    giris_sayfasi()
    st.stop()

# --- ANA VERİ YÜKLEME ---
try:
    df_tum = pd.DataFrame(ws_islemler.get_all_records())
    if not df_tum.empty:
        df_tum.columns = df_tum.columns.str.strip()
        df = df_tum[df_tum['Kullanıcı'] == st.session_state.kullanici_adi].copy()
        if 'Lot' in df.columns: df['Lot'] = df['Lot'].apply(zorla_sayi_yap)
        if 'Fiyat' in df.columns: df['Fiyat'] = df['Fiyat'].apply(zorla_sayi_yap)
    else: df = pd.DataFrame()
except: df = pd.DataFrame()

# --- MENÜ ---
with st.sidebar:
    st.write(f"👤 **{st.session_state.kullanici_adi}**")
    secim = st.radio("Menü", ["📊 Canlı Portföy", "📈 Borsa Takip", "🚀 Halka Arzlar", "🧠 Portföy Analizi", "➕ İşlem Ekle", "📝 İşlem Geçmişi"])
    st.divider()
    if st.button("🔄 Yenile"): st.cache_data.clear(); st.rerun()
    if st.button("🔒 Çıkış"): 
        st.session_state.giris_yapildi = False
        st.session_state.secilen_hisse_detay = None # Çıkışta hisse seçimini sıfırla
        st.rerun()

# =========================================================
# 🔥 HİSSE DETAY SAYFASI GÖSTERME FONKSİYONU 🔥
# =========================================================
def hisse_detay_goster(sembol):
    st.button("⬅️ Geri Dön", on_click=lambda: st.session_state.update(secilen_hisse_detay=None))
    
    with st.spinner(f"{sembol} analiz ediliyor..."):
        fiyat, isim, tam_kod = veri_getir_ozel(sembol)
        analiz = hisse_performans_analizi(tam_kod)
        
    if analiz:
        st.header(f"📈 {isim} ({tam_kod})")
        st.metric("Anlık Fiyat", f"{analiz['Fiyat']:.2f} ₺")
        
        # 1. TAVAN / TABAN (Sadece BIST için)
        if tam_kod.endswith(".IS"):
            tavan = analiz['Fiyat'] * 1.10
            taban = analiz['Fiyat'] * 0.90
            c1, c2 = st.columns(2)
            c1.metric("🟢 Tavan Fiyat (%10)", f"{tavan:.2f} ₺")
            c2.metric("🔴 Taban Fiyat (-%10)", f"{taban:.2f} ₺")
        
        st.divider()
        
        # 2. PERFORMANS TABLOSU (METRİK OLARAK)
        st.subheader("📊 Performans Karnesi")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("1 Gün", f"%{analiz['1 Gün']:.2f}", delta=f"{analiz['1 Gün']:.2f}")
        col2.metric("1 Hafta", f"%{analiz['1 Hafta']:.2f}", delta=f"{analiz['1 Hafta']:.2f}")
        col3.metric("3 Ay", f"%{analiz['3 Ay']:.2f}", delta=f"{analiz['3 Ay']:.2f}")
        col4.metric("1 Yıl", f"%{analiz['1 Yıl']:.2f}", delta=f"{analiz['1 Yıl']:.2f}")
        col5.metric("5 Yıl", f"%{analiz['5 Yıl']:.2f}", delta=f"{analiz['5 Yıl']:.2f}")
        
        st.divider()
        
        # 3. YAPAY ZEKA YORUMU (SİMÜLASYON)
        st.subheader("🤖 Yapay Zeka Yorumu")
        yorum = ""
        
        # Algoritmik Yorum Oluşturucu
        if analiz['1 Yıl'] > 100:
            yorum += "🚀 **Uzun Vade:** Hisse son 1 yılda müthiş bir ralli yapmış (%100 üzeri). Yatırımcısını güldürmüş. "
        elif analiz['1 Yıl'] < -20:
            yorum += "🔻 **Uzun Vade:** Hisse son 1 yılda ciddi değer kaybetmiş. Ucuz kalmış olabilir ya da şirkette sorun olabilir. "
            
        if analiz['1 Gün'] < -3 and analiz['1 Hafta'] > 5:
            yorum += "📉 **Kısa Vade:** Haftalık trend yukarı olsa da bugün sert bir satış yemiş. Kâr satışı olabilir. "
        elif analiz['1 Gün'] > 3:
            yorum += "🔥 **Kısa Vade:** Bugün piyasadan pozitif ayrışıyor, alıcılar istekli. "
            
        if tam_kod.endswith(".IS"):
            yorum += "\n\n💡 **BIST Notu:** Tavan/Taban marjlarına dikkat edilerek işlem yapılmalı."
        else:
            yorum += "\n\n🌎 **Global Not:** Döviz kurlarındaki değişim de kazancınızı etkileyecektir."
            
        st.info(yorum if yorum else "Hisse standart bir seyir izliyor. Olağanüstü bir hareketlilik tespit edilmedi.")
        
    else:
        st.error("Veri alınamadı.")

# =========================================================
# SAYFALAR
# =========================================================

# EĞER BİR HİSSE SEÇİLDİYSE DİREKT DETAY SAYFASINI GÖSTER
if st.session_state.secilen_hisse_detay:
    hisse_detay_goster(st.session_state.secilen_hisse_detay)

# SEÇİLMEDİYSE NORMAL MENÜLERİ GÖSTER
else:
    # 1. CANLI PORTFÖY
    if secim == "📊 Canlı Portföy":
        st.header("📊 Canlı Portföy")
        if not df.empty:
            anlik, gerceklesen = portfoy_hesapla(df.copy())
            ozet, eldeki_deger, maliyet_toplam = [], 0, 0
            
            aktifler = [k for k, v in anlik.items() if v['Adet'] > 0]
            
            if aktifler:
                st.caption("Detaylı analiz için listeden hisse koduna tıklayın.")
                for s in aktifler:
                    v = anlik[s]
                    gf, _, kod = veri_getir_ozel(s)
                    gf = gf if gf else v['Ort_Maliyet']
                    
                    # LİSTELEME
                    c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
                    if c1.button(f"🔎 {s}", key=f"btn_{s}"):
                        st.session_state.secilen_hisse_detay = s
                        st.rerun()
                    
                    tutar = v['Adet'] * gf
                    kar = tutar - (v['Adet'] * v['Ort_Maliyet'])
                    c2.metric("Adet", f"{v['Adet']:.0f}")
                    c3.metric("Değer", f"{tutar:,.0f} ₺")
                    c4.metric("Kâr/Zarar", f"{kar:,.0f} ₺", delta=f"{kar:,.0f}")
                    
                    eldeki_deger += tutar
                    maliyet_toplam += (v['Adet'] * v['Ort_Maliyet'])
                
                st.divider()
                genel_net = gerceklesen + (eldeki_deger - maliyet_toplam)
                c1, c2 = st.columns(2)
                c1.metric("Toplam Portföy Değeri", f"{eldeki_deger:,.2f} ₺")
                c2.metric("GENEL NET DURUM", f"{genel_net:,.2f} ₺", delta=f"{genel_net:,.2f}")
            else:
                st.info("Portföy boş.")
        else: st.warning("Veri yok.")

    # 2. BORSA TAKİP (DETAYLI)
    elif secim == "📈 Borsa Takip":
        st.header("📈 Piyasa Ekranı")
        
        # Arama
        ara = st.text_input("Hisse Ara (Detay için kodu girip Enter'a bas)", placeholder="ASELS, THYAO...")
        if ara:
            if st.button(f"git -> {ara.upper()}"):
                st.session_state.secilen_hisse_detay = ara
                st.rerun()
        
        st.divider()
        st.subheader("🔥 Popüler Hisseler (Tıkla ve Git)")
        
        populerler = piyasa_verileri_getir()
        cols = st.columns(4)
        for i, s in enumerate(populerler):
            temiz_ad = s.replace(".IS", "")
            if cols[i%4].button(temiz_ad, key=f"pop_{s}"):
                st.session_state.secilen_hisse_detay = temiz_ad
                st.rerun()

    # DİĞER SAYFALAR (AYNI KALDI)
    elif secim == "🚀 Halka Arzlar":
        st.header("🚀 Halka Arzlar")
        if not df.empty and 'Halka Arz' in df.columns:
            arz = df[df['Halka Arz'].astype(str).str.upper() == 'TRUE']
            if not arz.empty: st.dataframe(arz, use_container_width=True)
            else: st.info("Yok.")

    elif secim == "🧠 Portföy Analizi":
        st.header("🧠 Analiz")
        st.info("Detaylı analiz için 'Borsa Takip' veya 'Portföy'den bir hisseye tıklayın.")

    elif secim == "➕ İşlem Ekle":
        st.header("İşlem Ekle")
        c1, c2 = st.columns(2)
        h = c1.text_input("Hisse Kodu").upper()
        i = c1.selectbox("İşlem", ["Alış", "Satış"])
        t = c1.date_input("Tarih")
        l = c2.number_input("Lot", min_value=1)
        f = c2.number_input("Fiyat", min_value=0.0, format="%.2f")
        ha = c2.checkbox("Halka Arz")
        if st.button("Kaydet"):
            try:
                ws_islemler.append_row([st.session_state.kullanici_adi, str(t), h.strip(), i, l, str(f).replace(',', '.'), str(ha).upper()])
                st.success("Kaydedildi")
            except: st.error("Hata")

    elif secim == "📝 İşlem Geçmişi":
        st.header("Geçmiş")
        if not df.empty: st.dataframe(df)
