import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. AYARLAR ---
st.set_page_config(page_title="Yatırımcı Pro", layout="wide", initial_sidebar_state="expanded")

# --- 2. TASARIM (CSS) ---
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

# --- 3. GOOGLE SHEETS BAĞLANTISI ---
def get_data():
    try:
        # Secrets kontrolü
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets ayarı (JSON) bulunamadı.")
            st.stop()
            
        creds_dict = st.secrets["gcp_service_account"]
        
        # Sadece Sheets yetkisi (Drive hatası vermesin diye)
        scope = ['https://www.googleapis.com/auth/spreadsheets']
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # -------------------------------------------------------
        # DİKKAT: AŞAĞIDAKİ TIRNAKLARIN İÇİNE KENDİ SHEET ID'Nİ YAPIŞTIR
        # -------------------------------------------------------
        sheet_id = "BURAYA_SHEET_ID_YAPISTIR" 
        
        # ID ile dosyayı bul
        sheet = client.open_by_key(sheet_id).sheet1
        data = sheet.get_all_records()
        return sheet, data

    except Exception as e:
        st.error(f"Bağlantı Hatası: {e}")
        st.stop()

# Veriyi çek
sheet, data = get_data()
df = pd.DataFrame(data)

# --- 4. OTURUM AÇMA (KALICI) ---
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

# --- 5. YAN MENÜ ---
with st.sidebar:
    st.title("Yatırımcı v3.0")
    secim = st.radio("Menü", ["📊 Güncel Portföy", "🚀 Halka Arzlar", "🧠 Portföy Analizi", "➕ İşlem Ekle", "📝 İşlem Geçmişi"])
    
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

# --- 6. SAYFALAR ---

# SAYFA: GÜNCEL PORTFÖY
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
            st.dataframe(pd.DataFrame(ozet_listesi), use_container_width=True)
        else:
            st.info("Portföy boş (veya tüm pozisyonlar kapalı).")
    else:
        st.warning("Veri yok.")

# SAYFA: HALKA ARZLAR
elif secim == "🚀 Halka Arzlar":
    st.header("🚀 Halka Arzlar")
    if not df.empty:
        # Sütun ismi kontrolü (Hata vermemesi için)
        if 'Halka Arz' in df.columns:
            try:
                arz_df = df[df['Halka Arz'].astype(str).str.upper() == 'TRUE']
                if not arz_df.empty:
                    st.dataframe(arz_df, use_container_width=True)
                else:
                    st.info("Halka arz kaydı yok.")
            except:
                st.error("Halka arz filtresi çalışırken hata oluştu.")
        else:
            st.error("Google Sheet dosyanızda 'Halka Arz' sütunu bulunamadı.")
    else:
        st.info("Veri yok.")

# SAYFA: ANALİZ (YENİ)
elif secim == "🧠 Portföy Analizi":
    st.header("🧠 Yapay Zeka Portföy Analizi")
    st.caption("Yatırım alışkanlıklarınızın risk raporu.")
    
    if not df.empty:
        if st.button("Analizi Başlat", use_container_width=True):
            st.spinner("Hesaplanıyor...")
            
            # Veri Hazırlığı
            ozet = []
            toplam_portfoy_degeri = 0
            halka_arz_sayisi = 0
            toplam_islem = len(df)
            
            # Halka Arz Sayımı
            if 'Halka Arz' in df.columns:
                 halka_arz_sayisi = len(df[df['Halka Arz'].astype(str).str.upper() == 'TRUE'])

            # Portföy Değerini Hesapla
            for sembol in df['Hisse Adı'].unique():
                temp = df[df['Hisse Adı'] == sembol]
                temp['Lot'] = pd.to_numeric(temp['Lot'], errors='coerce').fillna(0)
                temp['Fiyat'] = pd.to_numeric(temp['Fiyat'], errors='coerce').fillna(0)
                
                alis = temp[temp['İşlem'] == 'Alış']
                satis = temp[temp['İşlem'] == 'Satış']
                net_lot = alis['Lot'].sum() - satis['Lot'].sum()
                
                if net_lot > 0:
                    # Basitlik için şu anki değeri maliyetten hesaplıyoruz
                    maliyet = (alis['Lot'] * alis['Fiyat']).sum() / alis['Lot'].sum() if alis['Lot'].sum() > 0 else 0
                    tutar = net_lot * maliyet
                    toplam_portfoy_degeri += tutar
                    ozet.append({"Hisse": sembol, "Değer": tutar})
            
            # --- Raporlama ---
            st.divider()
            col1, col2 = st.columns(2)
            
            uyarilar = []
            
            # 1. Çeşitlilik Kontrolü
            en_buyuk = max(ozet, key=lambda x:x['Değer']) if ozet else None
            if en_buyuk and toplam_portfoy_degeri > 0:
                oran = (en_buyuk['Değer'] / toplam_portfoy_degeri) * 100
                if oran > 50:
                    uyarilar.append(f"⚠️ **Yüksek Risk:** Portföyünün **%{int(oran)}** kadarı tek bir hissede ({en_buyuk['Hisse']}).")
            
            # 2. Halka Arz Kontrolü
            if toplam_islem > 0:
                arz_orani = (halka_arz_sayisi / toplam_islem) * 100
                if arz_orani > 60:
                    uyarilar.append(f"⚠️ **Davranış Uyarısı:** İşlemlerinin **%{int(arz_orani)}** kadarı Halka Arz. Uzun vadeye odaklan.")

            with col1:
                st.subheader("🚨 Risk Raporu")
                if uyarilar:
                    for u in uyarilar: st.write(u)
                else:
                    st.success("✅ Büyük bir risk (çeşitlilik veya davranışsal) tespit edilmedi.")
            
            with col2:
                st.subheader("📊 Dağılım Grafiği")
                if ozet:
                    st.bar_chart(pd.DataFrame(ozet), x="Hisse", y="Değer")
                else:
                    st.info("Grafik için yeterli veri yok.")
    else:
        st.warning("Analiz için önce işlem eklemelisiniz.")

# SAYFA: İŞLEM EKLE
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
        halka_arz = st.checkbox("Halka Arz")

    if st.button("Kaydet", use_container_width=True):
        if hisse:
            try:
                yeni_veri = [str(tarih), hisse, islem, lot, fiyat, str(halka_arz).upper()]
                sheet.append_row(yeni_veri)
                st.success("✅ Kaydedildi! 'Yenile' butonuna bas.")
            except Exception as e:
                st.error(f"Hata: {e}")
        else:
            st.warning("Hisse adı giriniz.")

# SAYFA: GEÇMİŞ
elif secim == "📝 İşlem Geçmişi":
    st.header("📝 Tüm Kayıtlar")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
