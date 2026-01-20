import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- AYARLAR ---
st.set_page_config(page_title="Yatırımcı Pro", layout="wide", initial_sidebar_state="expanded")

# --- TASARIM (CSS) ---
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

# --- GOOGLE SHEETS BAĞLANTISI ---
def get_data():
    # Streamlit Secrets'tan bilgileri alıp bağlanıyoruz
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open("Yatirimci_DB").sheet1 # Dosya Adı BURADA ÖNEMLİ
    data = sheet.get_all_records()
    return sheet, data

try:
    sheet, data = get_data()
    df = pd.DataFrame(data)
except Exception as e:
    st.error(f"Google Sheets Bağlantı Hatası: {e}")
    st.stop()

# --- OTURUM AÇMA ---
if 'giris_yapildi' not in st.session_state:
    st.session_state.giris_yapildi = False

def giris_ekrani():
    st.markdown("<h1 style='text-align: center;'>🔐 Yatırımcı Girişi</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        kullanici = st.text_input("Kullanıcı Adı")
        sifre = st.text_input("Şifre", type="password")
        if st.button("Giriş Yap", use_container_width=True):
            if kullanici == "admin" and sifre == "1234":
                st.session_state.giris_yapildi = True
                st.rerun()
            else:
                st.error("Hatalı giriş!")

if not st.session_state.giris_yapildi:
    giris_ekrani()
    st.stop()

# --- MENÜ ---
with st.sidebar:
    st.title("Yatırımcı v2.1")
    secim = st.radio("Menü", ["📊 Güncel Portföy", "🚀 Halka Arzlar", "➕ İşlem Ekle", "📝 İşlem Geçmişi"])
    if st.button("Yenile (Verileri Çek)"):
        st.cache_data.clear()
        st.rerun()

# --- SAYFA 1: PORTFÖY ---
if secim == "📊 Güncel Portföy":
    st.header("📊 Portföy Durumu")
    if not df.empty:
        ozet_listesi = []
        for sembol in df['Hisse Adı'].unique():
            temp_df = df[df['Hisse Adı'] == sembol]
            
            # Lot ve Fiyat sütunlarını sayıya çevirelim (Hata önlemek için)
            temp_df['Lot'] = pd.to_numeric(temp_df['Lot'])
            temp_df['Fiyat'] = pd.to_numeric(temp_df['Fiyat'])
            
            alis = temp_df[temp_df['İşlem'] == 'Alış']
            satis = temp_df[temp_df['İşlem'] == 'Satış']
            
            net_lot = alis['Lot'].sum() - satis['Lot'].sum()
            
            if net_lot > 0:
                # Ağırlıklı ortalama maliyet
                toplam_maliyet = (alis['Lot'] * alis['Fiyat']).sum()
                toplam_alis_lot = alis['Lot'].sum()
                ort_maliyet = toplam_maliyet / toplam_alis_lot if toplam_alis_lot > 0 else 0
                
                ozet_listesi.append({
                    "Hisse": sembol,
                    "Adet": net_lot,
                    "Ort. Maliyet": round(ort_maliyet, 2),
                    "Toplam Değer": round(net_lot * ort_maliyet, 2)
                })
        
        if ozet_listesi:
            st.dataframe(pd.DataFrame(ozet_listesi), use_container_width=True)
        else:
            st.info("Elinizde hisse yok.")
    else:
        st.warning("Veritabanı boş.")

# --- SAYFA 2: HALKA ARZLAR ---
elif secim == "🚀 Halka Arzlar":
    st.header("🚀 Halka Arzlar")
    if not df.empty:
        # Sheet'ten gelen TRUE/FALSE bazen yazı (string) olabilir, kontrol ediyoruz
        arz_df = df[df['Halka Arz'].astype(str).str.upper() == 'TRUE']
        if not arz_df.empty:
            st.dataframe(arz_df, use_container_width=True)
        else:
            st.info("Halka arz kaydı yok.")

# --- SAYFA 3: İŞLEM EKLE ---
elif secim == "➕ İşlem Ekle":
    st.header("Yeni Yatırım Ekle")
    col1, col2 = st.columns(2)
    with col1:
        hisse = st.text_input("Hisse Kodu").upper()
        islem = st.selectbox("İşlem", ["Alış", "Satış"])
        tarih = st.date_input("Tarih", datetime.now()).strftime("%Y-%m-%d")
    with col2:
        lot = st.number_input("Lot", min_value=1)
        fiyat = st.number_input("Fiyat", min_value=0.0, format="%.2f")
        halka_arz = st.checkbox("Halka Arz İşlemi")

    if st.button("Kaydet", use_container_width=True):
        if hisse:
            st.info("Google Sheets'e kaydediliyor...")
            try:
                # Yeni satırı sheet'e ekle
                yeni_veri = [str(tarih), hisse, islem, lot, fiyat, str(halka_arz).upper()]
                sheet.append_row(yeni_veri)
                st.success("Kaydedildi! Listeyi görmek için sayfayı yenileyin.")
                st.cache_data.clear() # Önbelleği temizle ki yeni veri görünsün
            except Exception as e:
                st.error(f"Kayıt hatası: {e}")
        else:
            st.warning("Hisse adı giriniz.")

# --- SAYFA 4: GEÇMİŞ ---
elif secim == "📝 İşlem Geçmişi":
    st.header("📝 Tüm Kayıtlar")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
