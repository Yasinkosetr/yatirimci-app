import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import yfinance as yf
import time

# --- 1. AYARLAR ---
st.set_page_config(page_title="Yatırımcı Pro V6.0", layout="wide", initial_sidebar_state="expanded")

# --- 2. TASARIM ---
st.markdown(
    """
    <style>
    .stApp {background-color: #0E1117; background-image: linear-gradient(to right, #0f2027, #203a43, #2c5364);}
    [data-testid="stSidebar"] {background-color: #1c1c1e; border-right: 1px solid #333;}
    html, body, [class*="css"] {font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #E0E0E0;}
    .stButton>button {background-image: linear-gradient(19deg, #F4D03F 0%, #16A085 100%); color: white; border: none; border-radius: 10px;}
    [data-testid="stMetricValue"] {font-size: 1.6rem !important; color: #00ff00;}
    div[data-testid="column"] button {border: 1px solid #ff4b4b;}
    </style>
    """, unsafe_allow_html=True
)

# --- 3. GOOGLE SHEETS BAĞLANTISI ---
def get_data():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets ayarı bulunamadı.")
            st.stop()
        creds_dict = st.secrets["gcp_service_account"]
        scope = ['https://www.googleapis.com/auth/spreadsheets']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # 👇 LİNKİ BURAYA YAPIŞTIRMAYI UNUTMA 👇
        sheet_url = "https://docs.google.com/spreadsheets/d/1ijPoTKNsXZBMxdRdMa7cpEhbSYt9kMwoqf5nZFNi7S8/edit?gid=0#gid=0"
        
        sheet = client.open_by_url(sheet_url).sheet1
        data = sheet.get_all_records()
        return sheet, data
    except Exception as e:
        st.error(f"Veri tabanı hatası: {e}")
        st.stop()

# --- 4. YARDIMCI FONKSİYONLAR ---

def zorla_sayi_yap(deger):
    if deger is None or str(deger).strip() == "": return 0.0
    if isinstance(deger, (int, float)): return float(deger)
    metin = str(deger).strip().replace("TL", "").replace("$", "").replace(" ", "")
    if "," in metin:
        metin = metin.replace(".", "").replace(",", ".")
    else:
        if metin.count(".") > 1: metin = metin.replace(".", "")
    try: return float(metin)
    except: return 0.0

@st.cache_data(ttl=60)
def veri_getir_ozel(hisse_kodu):
    sembol = str(hisse_kodu).strip().upper()
    if "-" in sembol:
        try:
            tik = yf.Ticker(sembol)
            h = tik.history(period="1d")
            if not h.empty: return h['Close'].iloc[-1], tik.info.get('longName', sembol)
        except: pass
    if not sembol.endswith(".IS"):
        try:
            tik = yf.Ticker(f"{sembol}.IS")
            h = tik.history(period="1d")
            if not h.empty: return h['Close'].iloc[-1], tik.info.get('longName', sembol)
        except: pass
    try:
        tik = yf.Ticker(sembol)
        h = tik.history(period="1d")
        if not h.empty: return h['Close'].iloc[-1], tik.info.get('longName', sembol)
    except: pass
    return None, sembol

# 🔥 GİZLİ KAHRAMAN: GEÇMİŞ MUHASEBE HESAPLAYICI 🔥
def portfoy_hesapla(df):
    if df.empty: return {}, 0.0
    
    # Tarihe göre sırala ki işlemler doğru sırayla hesaplansın
    df['Tarih'] = pd.to_datetime(df['Tarih'])
    df = df.sort_values(by='Tarih')
    
    portfoy = {}  # {Hisse: {'Adet': 0, 'Maliyet': 0}}
    gerceklesen_kar_zarar = 0.0
    
    for index, row in df.iterrows():
        hisse = row['Hisse Adı']
        islem = row['İşlem']
        adet = float(row['Lot'])
        fiyat = float(row['Fiyat'])
        
        if hisse not in portfoy:
            portfoy[hisse] = {'Adet': 0.0, 'Ort_Maliyet': 0.0}
            
        mevcut = portfoy[hisse]
        
        if islem == "Alış":
            # Ağırlıklı Ortalama Maliyet Hesabı
            eski_tutar = mevcut['Adet'] * mevcut['Ort_Maliyet']
            yeni_tutar = adet * fiyat
            toplam_adet = mevcut['Adet'] + adet
            
            mevcut['Ort_Maliyet'] = (eski_tutar + yeni_tutar) / toplam_adet if toplam_adet > 0 else 0
            mevcut['Adet'] = toplam_adet
            
        elif islem == "Satış":
            # Satıştan Doğan Kâr/Zarar (Realized P/L)
            satis_kari = (fiyat - mevcut['Ort_Maliyet']) * adet
            gerceklesen_kar_zarar += satis_kari
            
            mevcut['Adet'] -= adet
            if mevcut['Adet'] < 0: mevcut['Adet'] = 0 # Eksiye düşerse sıfırla
            
            # Satış yapınca maliyet değişmez, sadece adet düşer.
            
    return portfoy, gerceklesen_kar_zarar

# --- 5. VERİ YÜKLEME ---
sheet, data = get_data()
df = pd.DataFrame(data)

if not df.empty:
    df.columns = df.columns.str.strip()
    if 'Lot' in df.columns: df['Lot'] = df['Lot'].apply(zorla_sayi_yap)
    if 'Fiyat' in df.columns: df['Fiyat'] = df['Fiyat'].apply(zorla_sayi_yap)

# --- 6. OTURUM AÇMA ---
if "giris" in st.query_params and st.query_params["giris"] == "ok":
    st.session_state.giris_yapildi = True
elif 'giris_yapildi' not in st.session_state:
    st.session_state.giris_yapildi = False

if not st.session_state.giris_yapildi:
    st.markdown("<h1 style='text-align: center;'>🔐 Yatırımcı Girişi</h1>", unsafe_allow_html=True)
    col1, col2,
