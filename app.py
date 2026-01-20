import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import yfinance as yf
import time

# --- 1. AYARLAR ---
st.set_page_config(page_title="Yatırımcı Pro Max", layout="wide", initial_sidebar_state="expanded")

# --- 2. TASARIM (CSS) ---
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
        
        # =======================================================
        # 👇 LİNKİ BURAYA YAPIŞTIRMAYI UNUTMA 👇
        # =======================================================
        sheet_url = "https://docs.google.com/spreadsheets/d/1ijPoTKNsXZBMxdRdMa7cpEhbSYt9kMwoqf5nZFNi7S8/edit?gid=0#gid=0"
        # =======================================================
        
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
    st.title("Yatırımcı v4.5")
    secim = st.radio("Menü", ["📊 Canlı Portföy", "🚀 Halka Arzlar", "🧠 Portföy Analizi", "➕ İşlem Ekle", "📝 İşlem Geçmişi"])
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

# --- ÖZEL VERİ ÇEKME FONKSİYONU ---
@st.cache_data(ttl=60)
def veri_getir_ozel(hisse_kodu):
    # 1. Temizlik
    sembol = str(hisse_kodu).strip().upper()
    
    # 2. .IS Ekleme
    if not sembol.endswith(".IS"):
        arama_sembolu = f"{sembol}.IS"
    else:
        arama_sembolu = sembol
        
    try:
        ticker = yf.Ticker(arama_sembolu)
        # Günlük geçmişten al
        hist = ticker.history(period="1d")
        
        if not hist.empty:
            fiyat = hist['Close'].iloc[-1]
            isim = ticker.info.get('longName', sembol)
            return fiyat, isim
        else:
            return None, sembol
    except Exception:
        return None, sembol

# --- SAYFALAR ---

# SAYFA: CANLI PORTFÖY
if secim == "📊 Canlı Portföy":
    st.header("📊 Canlı Portföy Durumu")
    
    if not df.empty:
        ozet_listesi = []
        genel_toplam_deger = 0
        genel_toplam_maliyet = 0
        
        # İlerleme Çubuğu
        my_bar = st.progress(0, text="Veriler güncelleniyor...")
        toplam_hisse_sayisi = len(df['Hisse Adı'].unique())
        sayac = 0
        
        for sembol in df['Hisse Adı'].unique():
            sayac += 1
            my_bar.progress(int((sayac / toplam_hisse_sayisi) * 100), text=f"{sembol} verisi çekiliyor...")
            
            temp_df = df[df['Hisse Adı'] == sembol]
            temp_df['Lot'] = pd.to_numeric(temp_df['Lot'], errors='coerce').fillna(0)
            temp_df['Fiyat'] = pd.to_numeric(temp_df['Fiyat'], errors='coerce').fillna(0)
            
            alis = temp_df[temp_df['İşlem'] == 'Alış']
            satis = temp_df[temp_df['İşlem'] == 'Satış']
            net_lot = alis['Lot'].sum() - satis['Lot'].sum()
            
            if net_lot > 0:
                toplam_maliyet = (alis['Lot'] * alis['Fiyat']).sum()
                ort_maliyet = toplam_maliyet / alis['Lot'].sum() if alis['Lot'].sum() > 0 else 0
                
                # CANLI VERİ KULLANILIYOR
                guncel_fiyat, sirket_adi = veri_getir_ozel(sembol)
                
                veri_durumu = "✅ Canlı"
                if guncel_fiyat is None:
                    guncel_fiyat = ort_maliyet
                    veri_durumu = "⚠️ Veri Yok"
                
                guncel_tutar = net_lot * guncel_fiyat
                maliyet_tutari = net_lot * ort_maliyet
                kar_zarar = guncel_tutar - maliyet_tutari
                kar_yuzde = (kar_zarar / maliyet_tutari) * 100 if maliyet_tutari > 0 else 0
                
                genel_toplam_deger += guncel_tutar
                genel_toplam_maliyet += maliyet_tutari
                
                ozet_listesi.append({
                    "Kod": sembol,
                    "Şirket": sirket_adi if sirket_adi else sembol,
                    "Adet": net_lot,
                    "Ort. Maliyet": round(ort_maliyet, 2),
                    "Anlık Fiyat": round(guncel_fiyat, 2),
                    "Toplam Değer": round(guncel_tutar, 2),
                    "Kâr/Zarar": round(kar_zarar, 2),
                    "Durum": veri_durumu
                })
        
        my_bar.empty()

        col_m1, col_m2, col_m3 = st.columns(3)
        genel_kar = genel_toplam_deger - genel_toplam_maliyet
        genel_yuzde = (genel_kar / genel_toplam_maliyet * 100) if genel_toplam_maliyet > 0 else 0
        
        col_m1.metric("Toplam Portföy", f"{genel_toplam_deger:,.2f} ₺")
        col_m2.metric("Toplam Maliyet", f"{genel_toplam_maliyet:,.2f} ₺")
        col_m3.metric("Net Kâr/Zarar", f"{genel_kar:,.2f} ₺", f"%{genel_yuzde:.2f}")
        
        st.divider()
        if ozet_listesi:
            st.dataframe(pd.DataFrame(ozet_listesi), use_container_width=True)
        else:
            st.info("Portföy boş.")
    else:
        st.warning("Veri yok.")

# SAYFA: HALKA ARZLAR
elif secim == "🚀 Halka Arzlar":
    st.header("🚀 Halka Arzlar")
    if not df.empty and 'Halka Arz' in df.columns:
        # HATA DÜZELTİLDİ: Satırın sonuna == 'TRUE'] eklendi.
        arz_df = df[df['Halka Arz'].astype(str).str.upper() == 'TRUE']
        if not arz_df.empty: st.dataframe(arz_df, use_container_width=True)
        else: st.info("Kayıt yok.")
    else: st.info("Veri yok.")

# SAYFA: ANALİZ
elif secim == "🧠 Port
