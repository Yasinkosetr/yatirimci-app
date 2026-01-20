import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- AYARLAR ---
st.set_page_config(page_title="Yatırımcı Pro", layout="wide", initial_sidebar_state="expanded")

# --- TASARIM ---
st.markdown(
    """
    <style>
    .stApp {background-color: #0E1117; background-image: linear-gradient(to right, #0f2027, #203a43, #2c5364);}
    [data-testid="stSidebar"] {background-color: #1c1c1e; border-right: 1px solid #333;}
    html, body, [class*="css"] {font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #E0E0E0;}
    .stButton>button {background-image: linear-gradient(19deg, #F4D03F 0%, #16A085 100%); color: white; border: none; border-radius: 10px;}
    </style>
    """, unsafe_allow_html=True
)

# --- GOOGLE SHEETS BAĞLANTISI (ESKİ USÜL - İSİMLE BULMA) ---
def get_data():
    try:
        # Secrets kontrolü
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets ayarı yapılmamış.")
            st.stop()
            
        creds_dict = st.secrets["gcp_service_account"]
        
        # En geniş yetkiyi veriyoruz (Hem Drive hem Sheets görsün)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Dosyayı İSMİNDEN buluyoruz (Yatirimci_DB)
        sheet = client.open("Yatirimci_DB").sheet1
        data = sheet.get_all_records()
        return sheet, data

    except Exception as e:
        # Eğer yine "Enable Drive API" derse linki göstermek için:
        st.error(f"HATA: {e}")
        st.stop()

# Veriyi çek
sheet, data = get_data()
df = pd.DataFrame(data)

# --- OTURUM AÇMA (Sayfa Yenilenince Atmaz) ---
if "giris" in st.query_params and st.query_params["giris"] == "ok":
    st.session_state.giris_yapildi = True
elif 'giris_yapildi' not in st.session_state:
    st.session_state.giris_yapildi = False

def giris_ekrani():
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

if not st.session_state.giris_yapildi:
    giris_ekrani()
    st.stop()

# --- MENÜ ---
with st.sidebar:
    st.title("Yatırımcı v2.3")
    secim = st.radio("Menü", ["📊 Güncel Portföy", "🚀 Halka Arzlar", "➕ İşlem Ekle", "📝 İşlem Geçmişi"])
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Yenile"):
            st.cache_data.clear()
            st.rerun()
    with col2:
        if st.button("🔒 Çıkış"):
            st.session_state.giris_yapildi = False
            st.query_params.clear()
            st.rerun()

# --- SAYFALAR ---

# 1. GÜNCEL PORTFÖY
if secim == "📊 Güncel Portföy":
    st.header("📊 Portföy Durumu")
    if not df.empty:
        ozet_listesi = []
        for sembol in df['Hisse Adı'].unique():
            temp_df = df[df['Hisse Adı'] == sembol]
            
            # Sayıya çevir (Hata önle)
            temp_df['Lot'] = pd.to_numeric(temp_df['Lot'], errors='coerce').fillna(0)
            temp_df['Fiyat'] = pd.to_numeric(temp_df['Fiyat'], errors='coerce').fillna(0)
            
            alis = temp_df[temp_df['İşlem'] == 'Alış']
            satis = temp_df[temp_df['İşlem'] == 'Satış']
            
            net_lot = alis['Lot'].sum() - satis['Lot'].sum()
            
            if net_lot > 0:
                toplam_maliyet = (alis['Lot'] * alis['Fiyat']).sum()
                ort_maliyet = toplam_maliyet / alis['Lot'].sum() if alis['Lot'].sum() > 0 else 0
                
                ozet_listesi.append({
                    "Hisse": sembol,
                    "Adet": net_lot,
                    "Ort. Maliyet": round(ort_maliyet, 2),
                    "Toplam Değer": round(net_lot * ort_maliyet, 2)
                })
        if ozet_listesi:
            st.dataframe(pd.DataFrame(ozet_list
