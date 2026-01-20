import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import yfinance as yf  # <--- YENİ KÜTÜPHANE

# --- 1. AYARLAR ---
st.set_page_config(page_title="Yatırımcı Pro Canlı", layout="wide", initial_sidebar_state="expanded")

# --- 2. TASARIM (CSS) ---
st.markdown(
    """
    <style>
    .stApp {background-color: #0E1117; background-image: linear-gradient(to right, #0f2027, #203a43, #2c5364);}
    [data-testid="stSidebar"] {background-color: #1c1c1e; border-right: 1px solid #333;}
    html, body, [class*="css"] {font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #E0E0E0;}
    .stButton>button {background-image: linear-gradient(19deg, #F4D03F 0%, #16A085 100%); color: white; border: none; border-radius: 10px;}
    /* Metrik kutularını güzelleştirme */
    [data-testid="stMetricValue"] {font-size: 2rem !important; color: #00ff00;}
    </style>
    """, unsafe_allow_html=True
)

# --- 3. GOOGLE SHEETS BAĞLANTISI ---
def get_data():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets ayarı (JSON) bulunamadı.")
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
        st.error(f"Bağlantı Hatası: {e}")
        st.info("İPUCU: Robot mailini dosyaya 'Editör' olarak ekledin mi?")
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

# --- 5. YAN MENÜ ---
with st.sidebar:
    st.title("Yatırımcı v4.0 (Canlı)")
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

# --- FONKSİYON: CANLI FİYAT ÇEKME ---
def fiyat_getir(hisse_kodu):
    try:
        # BIST hisseleri için sonuna .IS ekliyoruz (Örn: THYAO -> THYAO.IS)
        if not hisse_kodu.endswith(".IS"):
            sembol = f"{hisse_kodu}.IS"
        else:
            sembol = hisse_kodu
            
        ticker = yf.Ticker(sembol)
        # Hızlı veri çekme yöntemi
        fiyat = ticker.fast_info['last_price']
        return float(fiyat)
    except:
        return 0.0

# --- 6. SAYFALAR ---

# SAYFA: CANLI PORTFÖY
if secim == "📊 Canlı Portföy":
    st.header("📊 Canlı Portföy Durumu")
    
    if not df.empty:
        ozet_listesi = []
        genel_toplam_deger = 0
        genel_toplam_maliyet = 0
        
        # Yükleniyor animasyonu
        with st.spinner('Canlı borsa verileri çekiliyor...'):
            for sembol in df['Hisse Adı'].unique():
                temp_df = df[df['Hisse Adı'] == sembol]
                temp_df['Lot'] = pd.to_numeric(temp_df['Lot'], errors='coerce').fillna(0)
                temp_df['Fiyat'] = pd.to_numeric(temp_df['Fiyat'], errors='coerce').fillna(0)
                
                alis = temp_df[temp_df['İşlem'] == 'Alış']
                satis = temp_df[temp_df['İşlem'] == 'Satış']
                
                net_lot = alis['Lot'].sum() - satis['Lot'].sum()
                
                if net_lot > 0:
                    # Maliyet Hesabı
                    toplam_maliyet = (alis['Lot'] * alis['Fiyat']).sum()
                    ort_maliyet = toplam_maliyet / alis['Lot'].sum() if alis['Lot'].sum() > 0 else 0
                    
                    # CANLI FİYAT ÇEKİLİYOR
                    guncel_fiyat = fiyat_getir(sembol)
                    if guncel_fiyat == 0: guncel_fiyat = ort_maliyet # Veri çekemezse maliyeti göster
                    
                    guncel_tutar = net_lot * guncel_fiyat
                    maliyet_tutari = net_lot * ort_maliyet
                    kar_zarar = guncel_tutar - maliyet_tutari
                    kar_yuzde = (kar_zarar / maliyet_tutari) * 100 if maliyet_tutari > 0 else 0
                    
                    genel_toplam_deger += guncel_tutar
                    genel_toplam_maliyet += maliyet_tutari
                    
                    ozet_listesi.append({
                        "Hisse": sembol,
                        "Adet": net_lot,
                        "Ort. Maliyet": round(ort_maliyet, 2),
                        "Anlık Fiyat": round(guncel_fiyat, 2),
                        "Toplam Değer": round(guncel_tutar, 2),
                        "Kâr/Zarar (TL)": round(kar_zarar, 2),
                        "Kâr/Zarar (%)": f"%{round(kar_yuzde, 2)}"
                    })
        
        # EN ÜSTTE BÜYÜK BİLGİ KUTULARI (METRİKLER)
        col_m1, col_m2, col_m3 = st.columns(3)
        genel_kar = genel_toplam_deger - genel_toplam_maliyet
        genel_yuzde = (genel_kar / genel_toplam_maliyet * 100) if genel_toplam_maliyet > 0 else 0
        
        col_m1.metric("Toplam Portföy", f"{genel_toplam_deger:,.2f} ₺")
        col_m2.metric("Toplam Maliyet", f"{genel_toplam_maliyet:,.2f} ₺")
        col_m3.metric("Net Kâr/Zarar", f"{genel_kar:,.2f} ₺", f"%{genel_yuzde:.2f}")

        st.divider()
        
        if ozet_listesi:
            # Tabloyu göster (Renklendirme yapılabilir ama şimdilik sade olsun)
            st.dataframe(pd.DataFrame(ozet_listesi), use_container_width=True)
        else:
            st.info("Aktif hisseniz yok.")
            
    else:
        st.warning("Veritabanı boş.")

# SAYFA: HALKA ARZLAR
elif secim == "🚀 Halka Arzlar":
    st.header("🚀 Halka Arzlar")
    if not df.empty and 'Halka Arz' in df.columns:
        try:
            arz_df = df[df['Halka Arz'].astype(str).str.upper() == 'TRUE']
            if not arz_df.empty: st.dataframe(arz_df, use_container_width=True)
            else: st.info("Kayıt yok.")
        except: st.error("Hata oluştu.")
    else: st.info("Veri yok.")

# --- SAYFA: İŞLEM EKLE (OTOMATİK FİYATLI) ---
elif secim == "➕ İşlem Ekle":
    st.header("Yeni Yatırım Ekle")
    
    # Session state (hafıza) temizliği - Sayfa değişince fiyatı unutmasın diye
    if 'otomatik_fiyat' not in st.session_state:
        st.session_state.otomatik_fiyat = 0.0

    col1, col2 = st.columns(2)
    with col1:
        hisse = st.text_input("Hisse Kodu (Örn: ASELS)").upper()
        
        # SİHİRLİ BUTON BURADA 👇
        if st.button("⚡ Anlık Fiyatı Getir"):
            if hisse:
                with st.spinner("Fiyat çekiliyor..."):
                    gelen_fiyat, gelen_isim = veri_getir_ozel(hisse)
                    if gelen_fiyat:
                        st.session_state.otomatik_fiyat = float(gelen_fiyat)
                        st.success(f"✅ {gelen_isim}: {gelen_fiyat} TL")
                    else:
                        st.error("Fiyat bulunamadı, kodu kontrol et.")
            else:
                st.warning("Önce hisse kodu yazmalısın.")

        islem = st.selectbox("İşlem", ["Alış", "Satış"])
        tarih = st.date_input("Tarih", datetime.now()).strftime("%Y-%m-%d")

    with col2:
        lot = st.number_input("Lot", min_value=1)
        
        # Fiyat kutusu artık otomatik dolabiliyor
        # value=st.session_state.otomatik_fiyat kısmı bu işi yapıyor
        fiyat = st.number_input("Fiyat", min_value=0.0, format="%.2f", value=st.session_state.otomatik_fiyat)
        
        halka_arz = st.checkbox("Halka Arz")

    # Kaydet Butonu
    if st.button("Kaydet", use_container_width=True):
        if hisse and fiyat > 0:
            try:
                temiz_hisse = hisse.strip().upper()
                yeni_veri = [str(tarih), temiz_hisse, islem, lot, fiyat, str(halka_arz).upper()]
                sheet.append_row(yeni_veri)
                st.success(f"✅ {temiz_hisse} ({lot} Adet) başarıyla kaydedildi!")
                # Kayıttan sonra hafızadaki fiyatı sıfırla
                st.session_state.otomatik_fiyat = 0.0
            except Exception as e: st.error(f"Hata: {e}")
        else:
            st.warning("Lütfen hisse kodu ve fiyat giriniz.")

# SAYFA: GEÇMİŞ
elif secim == "📝 İşlem Geçmişi":
    st.header("📝 Tüm Kayıtlar")
    if not df.empty: st.dataframe(df, use_container_width=True)
