import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. AYARLAR VE TASARIM ---
st.set_page_config(page_title="Yatırımcı Pro", layout="wide", initial_sidebar_state="expanded")

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

# --- 2. GOOGLE SHEETS BAĞLANTISI ---
def get_data():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets ayarı bulunamadı.")
            st.stop()
            
        creds_dict = st.secrets["gcp_service_account"]
        
        # Drive API hatası almamak için sadece Sheets yetkisi
        scope = ['https://www.googleapis.com/auth/spreadsheets']
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Dosya ismiyle açmayı dener (Hata verirse ID ile açma yöntemine geçeriz)
        sheet = client.open("Yatirimci_DB").sheet1
        data = sheet.get_all_records()
        return sheet, data

    except Exception as e:
        st.error(f"Veri Çekme Hatası: {e}")
        st.stop()

# Veriyi çek (Giriş yapmadan önce veritabanı hazır olsun)
sheet, data = get_data()
df = pd.DataFrame(data)

# --- 3. GELİŞMİŞ OTURUM AÇMA (Sayfa Yenilense de Atmaz) ---

# Önce URL kontrolü: Adres çubuğunda anahtar var mı?
if "giris" in st.query_params and st.query_params["giris"] == "ok":
    st.session_state.giris_yapildi = True
elif 'giris_yapildi' not in st.session_state:
    st.session_state.giris_yapildi = False

def giris_ekrani():
    st.markdown("<h1 style='text-align: center;'>🔐 Yatırımcı Girişi</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.info("Kullanıcı: admin | Şifre: 1234") # Şifreyi unutma diye
        kullanici = st.text_input("Kullanıcı Adı")
        sifre = st.text_input("Şifre", type="password")
        
        if st.button("Giriş Yap", use_container_width=True):
            if kullanici == "admin" and sifre == "1234":
                st.session_state.giris_yapildi = True
                # URL'e 'giris=ok' yazar, böylece F5 atınca sistem seni tanır
                st.query_params["giris"] = "ok"
                st.rerun()
            else:
                st.error("Hatalı kullanıcı adı veya şifre!")

# Giriş yapılmamışsa kod burada durur ve sadece giriş ekranını gösterir
if not st.session_state.giris_yapildi:
    giris_ekrani()
    st.stop()

# ==========================================
# BURADAN AŞAĞISI SADECE GİRİŞ YAPILINCA ÇALIŞIR
# ==========================================

# --- 4. YAN MENÜ ---
with st.sidebar:
    st.title("Yatırımcı v2.2")
    secim = st.radio("Menü", ["📊 Güncel Portföy", "🚀 Halka Arzlar", "➕ İşlem Ekle", "📝 İşlem Geçmişi"])
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 Yenile"):
            st.cache_data.clear()
            st.rerun()
    with col_btn2:
        if st.button("🔒 Çıkış"):
            st.session_state.giris_yapildi = False
            st.query_params.clear() # URL temizle
            st.rerun()

# --- 5. SAYFALAR ---

# SAYFA: GÜNCEL PORTFÖY
if secim == "📊 Güncel Portföy":
    st.header("📊 Portföy Durumu")
    if not df.empty:
        ozet_listesi = []
        for sembol in df['Hisse Adı'].unique():
            temp_df = df[df['Hisse Adı'] == sembol]
            
            # Sayıya çevirme (Hata önleyici)
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
            st.dataframe(pd.DataFrame(ozet_listesi), use_container_width=True)
        else:
            st.info("Elinizde açık pozisyon (hisse) bulunmuyor.")
    else:
        st.warning("Veritabanı boş.")

# SAYFA: HALKA ARZLAR
elif secim == "🚀 Halka Arzlar":
    st.header("🚀 Halka Arz Takip")
    if not df.empty:
        # Halka Arz sütununu string yapıp kontrol ediyoruz (True/TRUE/true karışıklığı olmasın diye)
        arz_df = df[df['Halka Arz'].astype(str).str.upper() == 'TRUE']
        if not arz_df.empty:
            st.dataframe(arz_df, use_container_width=True)
        else:
            st.info("Halka arz kaydı bulunamadı.")

# SAYFA: İŞLEM EKLE
elif secim == "➕ İşlem Ekle":
    st.header("Yeni Yatırım Ekle")
    col1, col2 = st.columns(2)
