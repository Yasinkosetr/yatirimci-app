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
# Bu fonksiyon geçmiş işlemleri tarayıp hem eldeki maliyeti hem de satılanlardan edilen karı bulur.
def portfoy_hesapla(df):
    if df.empty: return {}, 0.0
    
    # Tarihe göre sırala (Eski işlemden yeniye doğru gitmek şart)
    if 'Tarih' in df.columns:
        df['Tarih'] = pd.to_datetime(df['Tarih'], errors='coerce')
        df = df.sort_values(by='Tarih')
    
    portfoy = {}  # {Hisse: {'Adet': 0, 'Ort_Maliyet': 0}}
    gerceklesen_kar_zarar = 0.0
    
    for index, row in df.iterrows():
        hisse = row['Hisse Adı']
        islem = row['İşlem']
        # Sayı formatlarını garantiye al
        adet = zorla_sayi_yap(row['Lot'])
        fiyat = zorla_sayi_yap(row['Fiyat'])
        
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
            # Satış Fiyatı - Alış Maliyeti = Hisse Başı Kar
            satis_kari = (fiyat - mevcut['Ort_Maliyet']) * adet
            gerceklesen_kar_zarar += satis_kari
            
            mevcut['Adet'] -= adet
            if mevcut['Adet'] < 0: mevcut['Adet'] = 0 # Eksiye düşerse sıfırla
            
            # Satış yapınca kalanların maliyeti değişmez.
            
    return portfoy, gerceklesen_kar_zarar

# --- 5. VERİ YÜKLEME ---
sheet, data = get_data()
df = pd.DataFrame(data)

if not df.empty:
    df.columns = df.columns.str.strip()
    # Verileri yüklerken sayıya çeviriyoruz (Garanti olsun)
    if 'Lot' in df.columns: df['Lot'] = df['Lot'].apply(zorla_sayi_yap)
    if 'Fiyat' in df.columns: df['Fiyat'] = df['Fiyat'].apply(zorla_sayi_yap)

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
    st.title("Yatırımcı v6.0")
    secim = st.radio("Menü", ["📊 Canlı Portföy", "🚀 Halka Arzlar", "🧠 Portföy Analizi", "➕ İşlem Ekle", "📝 İşlem Geçmişi", "🛠️ Veri Kontrol"])
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
        # 🔥 ÖNCE GEÇMİŞİ HESAPLA 🔥
        # Bu fonksiyon bize şu an elimizde ne kaldığını ve geçmişten ne kadar kar/zarar ettiğimizi (cebe giren) verir.
        anlik_portfoy, gerceklesen_kar_zarar = portfoy_hesapla(df.copy())
        
        ozet_listesi = []
        eldekilerin_degeri = 0
        eldekilerin_maliyeti = 0
        
        my_bar = st.progress(0, text="Analiz ediliyor...")
        
        # Sadece elinde lot kalan hisseleri listele
        aktif_hisseler = [k for k, v in anlik_portfoy.items() if v['Adet'] > 0]
        toplam_sayi = len(aktif_hisseler)
        
        # Eğer elde hiç hisse yoksa bile hesaplamalar çalışsın
        if toplam_sayi > 0:
            for i, sembol in enumerate(aktif_hisseler):
                my_bar.progress(int(((i+1) / toplam_sayi) * 100), text=f"{sembol}...")
                
                veri = anlik_portfoy[sembol]
                adet = veri['Adet']
                ort_maliyet = veri['Ort_Maliyet']
                
                # Canlı Fiyat
                guncel_fiyat, sirket_adi = veri_getir_ozel(sembol)
                
                veri_durumu = "✅ Canlı"
                if guncel_fiyat is None:
                    guncel_fiyat = ort_maliyet
                    veri_durumu = "⚠️ Veri Yok"
                
                guncel_tutar = adet * guncel_fiyat
                maliyet_tutari = adet * ort_maliyet
                
                # Kağıt Üzerindeki (Potansiyel) Kar/Zarar
                potansiyel_kar = guncel_tutar - maliyet_tutari
                
                eldekilerin_degeri += guncel_tutar
                eldekilerin_maliyeti += maliyet_tutari
                
                ozet_listesi.append({
                    "Kod": sembol,
                    "Şirket": sirket_adi if sirket_adi else sembol,
                    "Adet": float(adet),
                    "Ort. Maliyet": round(ort_maliyet, 2),
                    "Anlık Fiyat": round(guncel_fiyat, 2),
                    "Toplam Değer": round(guncel_tutar, 2),
                    "Anlık K/Z": round(potansiyel_kar, 2), # Sadece bu pozisyonun karı
                    "Durum": veri_durumu
                })
        
        my_bar.empty()

        # --- METRİKLER (EN ÖNEMLİ KISIM) ---
        col1, col2, col3, col4 = st.columns(4)
        
        # 1. Kağıt üzerindeki (Henüz satılmamış) Kar/Zarar
        potansiyel_toplam_kz = eldekilerin_degeri - eldekilerin_maliyeti
        
        # 2. Toplam Net Durum (Cebine giren + Elindeki potansiyel)
        net_genel_durum = gerceklesen_kar_zarar + potansiyel_toplam_kz
        
        col1.metric("Portföy Değeri", f"{eldekilerin_degeri:,.2f} ₺")
        col2.metric("Kesinleşmiş K/Z", f"{gerceklesen_kar_zarar:,.2f} ₺", help="Geçmişte satıp cebine koyduğun net para.")
        col3.metric("Anlık (Açık) K/Z", f"{potansiyel_toplam_kz:,.2f} ₺", help="Şu an elindeki hisselerin kar/zarar durumu.")
        
        # RENKLENDİRME İÇİN DELTA
        col4.metric("GENEL NET DURUM", f"{net_genel_durum:,.2f} ₺", delta=f"{net_genel_durum:,.2f} ₺")
        
        st.info(f"💡 **Bilgi:** Geçmişte satıp zarar ettiğiniz veya kâr ettiğiniz tüm işlemler **'Kesinleşmiş K/Z'** kutusunda toplanmıştır. Şu an elinizdeki hisselerin durumu ise **'Anlık K/Z'** kutusundadır. İkisinin toplamı **'GENEL NET DURUM'**dur.")
        
        st.divider()
        if ozet_listesi:
            st.dataframe(pd.DataFrame(ozet_listesi), use_container_width=True)
            
            # --- HIZLI SATIŞ PANELİ ---
            st.divider()
            st.subheader("⚡ Hızlı Satış Paneli")
            
            eldekiler = [item['Kod'] for item in ozet_listesi]
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                satilacak_hisse = st.selectbox("Satılacak Hisse", eldekiler)
            
            secilen_veri = next((item for item in ozet_listesi if item['Kod'] == satilacak_hisse), None)
            
            if secilen_veri:
                max_lot = secilen_veri['Adet']
                anlik_fiyat = secilen_veri['Anlık Fiyat']
                
                with c2:
                    sat_lot = st.number_input("Adet", min_value=0.0, max_value=max_lot, value=max_lot)
                with c3:
                    sat_fiyat = st.number_input("Satış Fiyatı", value=anlik_fiyat)
                with c4:
                    st.write("")
                    st.write("")
                    if st.button("🔴 SATIŞI ONAYLA", use_container_width=True, type="primary"):
                        if sat_lot > 0:
                            try:
                                tarih_bugun = datetime.now().strftime("%Y-%m-%d")
                                temiz_fiyat = str(sat_fiyat).replace(',', '.')
                                yeni_veri = [tarih_bugun, satilacak_hisse, "Satış", sat_lot, temiz_fiyat, "FALSE"]
                                sheet.append_row(yeni_veri)
                                st.success(f"{sat_lot} lot {satilacak_hisse} satıldı!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Hata: {e}")
                        else:
                            st.warning("Adet seçiniz.")
        else:
            st.info("Elinizde açık pozisyon (hisse) yok. Ancak geçmiş işlemlerden kaynaklı Kâr/Zarar yukarıda görünebilir.")
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
                temiz_fiyat = str(fiyat).replace(',', '.') 
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

# 6. DEBUG
elif secim == "🛠️ Veri Kontrol":
    st.header("🛠️ Veri Mühendisi Ekranı")
    if not df.empty:
        st.write(df.dtypes)
        st.dataframe(df.head())
        st.write(df['Fiyat'].describe())
    else:
        st.warning("Veri yok.")
