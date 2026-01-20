import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import yfinance as yf
import time

# --- 1. AYARLAR ---
st.set_page_config(page_title="Yatırımcı Pro Max", layout="wide", initial_sidebar_state="expanded")

# --- 2. TASARIM ---
st.markdown(
    """
    <style>
    .stApp {background-color: #0E1117; background-image: linear-gradient(to right, #0f2027, #203a43, #2c5364);}
    [data-testid="stSidebar"] {background-color: #1c1c1e; border-right: 1px solid #333;}
    html, body, [class*="css"] {font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #E0E0E0;}
    .stButton>button {background-image: linear-gradient(19deg, #F4D03F 0%, #16A085 100%); color: white; border: none; border-radius: 10px;}
    [data-testid="stMetricValue"] {font-size: 1.8rem !important; color: #00ff00;}
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

sheet, data = get_data()
df = pd.DataFrame(data)

# --- 4. OTURUM AÇMA ---
if "giris" in st.query_params and st.query_params["giris"] == "ok":
    st.session_state.giris_yapildi = True
elif 'giris_yapildi' not in st.session_state:
    st.session_state.giris_yapildi = False

if not st.session_state.giris_yapildi:
    st.markdown("<h1 style='text-align: center;'>🔐 Yatırımcı Girişi</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.info("Kullanıcı: admin | Şifre: 1234") 
        kullanici = st.text_input("Kullanıcı Adı")
        sifre = st.text_input("Şifre", type="password")
        if st.button("Giriş Yap", use_container_width=True):
            if kullanici == "admin" and sifre == "1234":
                st.session_state.giris_yapildi = True
                st.query_params["giris"] = "ok"
                st.rerun()
            else:
                st.error("Hatalı giriş!")
    st.stop()

# --- MENÜ ---
with st.sidebar:
    st.title("Yatırımcı v4.5")
    secim = st.radio("Menü", ["📊 Canlı Portföy", "🚀 Halka Arzlar", "🧠 Portföy Analizi", "➕ İşlem Ekle", "📝 İşlem Geçmişi"])
    st.divider()
    if st.button("🔄 Yenile"):
        st.cache_data.clear()
        st.rerun()
    if st.button("🔒 Çıkış"):
        st.session_state.giris_yapildi = False
        st.query_params.clear()
        st.rerun()

# --- ÖZEL VERİ ÇEKME FONKSİYONU ---
@st.cache_data(ttl=60)
def veri_getir_ozel(hisse_kodu):
    sembol = str(hisse_kodu).strip().
