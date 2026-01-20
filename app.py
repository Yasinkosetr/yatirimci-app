import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import yfinance as yf
import time

# --- 1. AYARLAR ---
st.set_page_config(page_title="Yatırımcı Pro V5.3", layout="wide", initial_sidebar_state="expanded")

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

# --- 4. YARDIMCI FONKSİYONLAR ---

# BU FONKSİYON SAYILARI ZORLA DÜZELTİR
def zorla_sayi_yap(deger):
    # Eğer boşsa 0 döndür
    if deger is None or str(deger).strip() == "":
        return 0.0
    
    # Zaten sayıysa (int/float) elleme, döndür
    if isinstance(deger, (int, float)):
        return float(deger)
    
    # Metinse temizliğe başla
    metin = str(deger).strip()
    
    # TL, $, boşluk gibi şeyleri sil
    metin = metin.replace("TL", "").replace("$", "").replace(" ", "")
    
    # ÖNEMLİ: Türkiye formatı (1.000,50) mı yoksa ABD formatı (1,000.50) mı?
    # Eğer virgül varsa ve sonda ise (ondalık), noktaları sil, virgülü nokta yap.
    if "," in metin:
        metin = metin.replace(".", "") # Binlik noktasını sil (1.000 -> 1000)
        metin = metin.replace(",", ".") # Virgülü nokta yap (10,5 -> 10.5)
    else:
        # Virgül yoksa sadece noktaları temizle (bazen binlik nokta olur: 1.000)
        # Ama dikkat: 10.50 de olabilir. 
        # Basit kural: Eğer 1 tane nokta varsa elleme. Birden fazla nokta varsa sil.
        if metin.count(".") > 1:
            metin = metin.replace(".", "")

    try:
        return float(metin)
    except:
        return 0.0

@st.cache_data(ttl=60)
def veri_getir_ozel(hisse_kodu):
    sembol = str(hisse_kodu).strip().upper()
    
    # Kripto veya özel
    if "-" in sembol:
        try:
            tik = yf.Ticker(sembol)
            h = tik.history(period="1d")
            if not h.empty: return h['Close'].iloc[-1], tik.info.get('longName', sembol)
        except: pass

    # TR (Bist) Öncelikli
    if not sembol.endswith(".IS"):
        try:
            tik = yf.Ticker(f"{sembol}.IS")
            h = tik.history(period="1d")
            if not h.empty: return h['Close'].iloc[-1], tik.info.get('longName', sembol)
        except: pass
    
    # Global
    try:
        tik = yf.Ticker(sembol)
        h = tik.history(period="1d")
        if not h.empty: return h['Close'].iloc[-1], tik.info.get('longName', sembol)
    except: pass
    
    return None, sembol

# --- 5. VERİ YÜKLEME VE ZORBA TEMİZLİK ---
sheet, data = get_data()
df = pd.DataFrame(data)

# 🔥 PANDAS İLE ZORLA TİP DÖNÜŞÜMÜ (EN KRİTİK YER)
if not df.empty:
    # Sütun isimlerindeki boşlukları temizle (Bazen 'Fiyat ' yazar hata verir)
    df.columns = df.columns.str.strip()
    
    if 'Lot' in df.columns:
        df['Lot'] = df['Lot'].apply(zorla_sayi_yap)
    
    if 'Fiyat' in df.columns:
        df['Fiyat'] = df['Fiyat'].apply(zorla_sayi_yap)

# --- 6. OTURUM AÇMA ---
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
    st.title("Yatırımcı v5.3")
    secim = st.radio("Menü", ["📊 Canlı Portföy", "🚀 Halka Arzlar", "🧠 Portföy Analizi", "➕ İşlem Ekle", "📝 İşlem Geçmişi", "🛠️ Veri Kontrol (Debug)"])
    st.divider()
    if st.button("🔄 Yenile"):
        st.cache_data.clear()
        st.rerun()
    if st.button("🔒 Çıkış"):
        st.session_state.giris_yapildi = False
        st.query_params.clear()
        st.rerun()

# --- SAYFALAR ---

# 1. CANLI PORTFÖY
if secim == "📊 Canlı Portföy":
    st.header("📊 Canlı Portföy Durumu")
    if not df.empty:
        ozet_listesi = []
        genel_toplam_deger = 0
        genel_toplam_maliyet = 0
        
        my_bar = st.progress(0, text="Analiz ediliyor...")
        hisseler = df['Hisse Adı'].unique()
        toplam_sayi = len(hisseler)
        
        for i, sembol in enumerate(hisseler):
            my_bar.progress(int(((i+1) / toplam_sayi) * 100), text=f"{sembol}...")
            
            temp_df = df[df['Hisse Adı'] == sembol]
            
            alis = temp_df[temp_df['İşlem'] == 'Alış']
            satis = temp_df[temp_df['İşlem'] == 'Satış']
            
            # Artık bunlar kesinlikle sayı
            net_lot = alis['Lot'].sum() - satis['Lot'].sum()
            
            if net_lot > 0:
                toplam_maliyet = (alis['Lot'] * alis['Fiyat']).sum()
                toplam_alis_lot = alis['Lot'].sum()
                ort_maliyet = toplam_maliyet / toplam_alis_lot if toplam_alis_lot > 0 else 0
                
                # Canlı Veri
                guncel_fiyat, sirket_adi = veri_getir_ozel(sembol)
                veri_durumu = "✅ Canlı"
                if guncel_fiyat is None:
                    guncel_fiyat = ort_maliyet
                    veri_durumu = "⚠️ Veri Yok"
                
                guncel_tutar = net_lot * guncel_fiyat
                maliyet_tutari = net_lot * ort_maliyet
                kar_zarar = guncel_tutar - maliyet_tutari
                
                genel_toplam_deger += guncel_tutar
                genel_toplam_maliyet += maliyet_tutari
                
                ozet_listesi.append({
                    "Kod": sembol,
                    "Şirket": sirket_adi if sirket_adi else sembol,
                    "Adet": float(net_lot),
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

# 2. HALKA ARZLAR
elif secim == "🚀 Halka Arzlar":
    st.header("🚀 Halka Arzlar")
    if not df.empty and 'Halka Arz' in df.columns:
        arz_df = df[df['Halka Arz'].astype(str).str.upper() == 'TRUE']
        if not arz_df.empty: st.dataframe(arz_df, use_container_width=True)
        else: st.info("Kayıt yok.")

# 3. ANALİZ
elif secim == "🧠 Portföy Analizi":
    st.header("🧠 Yapay Zeka Risk Analizi")
    if st.button("Analizi Başlat", use_container_width=True):
        if not df.empty:
            df['Tutar'] = df['Fiyat'] * df['Lot']
            st.bar_chart(df, x="Hisse Adı", y="Tutar")
        else:
            st.warning("Veri yok.")

# 4. İŞLEM EKLE
elif secim == "➕ İşlem Ekle":
    st.header("Yeni Yatırım Ekle")
    if 'otomatik_fiyat' not in st.session_state: st.session_state.otomatik_fiyat = 0.0

    col1, col2 = st.columns(2)
    with col1:
        hisse = st.text_input("Hisse Kodu (Örn: ASELS, AAPL)").upper()
        if st.button("⚡ Fiyat Getir"):
            if hisse:
                with st.spinner("Aranıyor..."):
                    gf, gi = veri_getir_ozel(hisse)
                    if gf:
                        st.session_state.otomatik_fiyat = float(gf)
                        st.success(f"✅ {gi}: {gf}")
                    else: st.error("Bulunamadı.")
        islem = st.selectbox("İşlem", ["Alış", "Satış"])
        tarih = st.date_input("Tarih", datetime.now()).strftime("%Y-%m-%d")

    with col2:
        lot = st.number_input("Lot", min_value=1)
        fiyat = st.number_input("Fiyat", min_value=0.0, format="%.2f", value=st.session_state.otomatik_fiyat)
        halka_arz = st.checkbox("Halka Arz")

    if st.button("Kaydet", use_container_width=True):
        if hisse and lot>0 and fiyat>0:
            try:
                temiz_hisse = hisse.strip().upper()
                temiz_fiyat = str(fiyat).replace(',', '.') # Nokta garantisi
                yeni_veri = [str(tarih), temiz_hisse, islem, lot, temiz_fiyat, str(halka_arz).upper()]
                sheet.append_row(yeni_veri)
                st.success("✅ Kaydedildi!")
                st.session_state.otomatik_fiyat = 0.0
            except Exception as e: st.error(f"Hata: {e}")
        else: st.warning("Eksik bilgi.")

# 5. GEÇMİŞ
elif secim == "📝 İşlem Geçmişi":
    st.header("📝 Tüm Kayıtlar")
    if not df.empty: st.dataframe(df, use_container_width=True)

# 6. DEBUG (HATA AYIKLAMA) - SADECE BURAYA BAKARAK SORUNU ÇÖZEBİLİRSİN
elif secim == "🛠️ Veri Kontrol (Debug)":
    st.header("🛠️ Veri Mühendisi Ekranı")
    st.write("Burada verilerin Python tarafından nasıl görüldüğünü analiz ediyoruz.")
    
    if not df.empty:
        st.write("### 1. Ham Veri Tipleri")
        st.write(df.dtypes)
        
        st.write("### 2. İlk 5 Satır")
        st.dataframe(df.head())
        
        st.write("### 3. Fiyat Sütunu Analizi")
        st.write("Eğer burada 'object' yazıyorsa metindir, 'float' yazıyorsa sayıdır.")
        st.write(df['Fiyat'].describe())
    else:
        st.warning("Veri yok.")
