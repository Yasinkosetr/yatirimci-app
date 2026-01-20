import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import yfinance as yf
import time
import hashlib

# --- 1. AYARLAR ---
st.set_page_config(page_title="Yatırımcı Pro V7.1", layout="wide", initial_sidebar_state="expanded")

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

# --- 3. GÜVENLİK ---
def sifrele(sifre):
    return hashlib.sha256(str.encode(sifre)).hexdigest()

def sifre_kontrol(girilen, veritabani_sifresi):
    return sifrele(girilen) == veritabani_sifresi

# --- 4. GOOGLE SHEETS BAĞLANTISI ---
def get_sheets():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets ayarı bulunamadı.")
            st.stop()
        creds_dict = st.secrets["gcp_service_account"]
        scope = ['https://www.googleapis.com/auth/spreadsheets']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # 👇 LİNKİ BURAYA YAPIŞTIRMAYI UNUTMA 👇
        sheet_url = "https://docs.google.com/spreadsheets/d/1ijPoTKNsXZBMxdRdMa7cpEhbSYt9kMwoqf5nZFNi7S8/edit?gid=499369690#gid=499369690"
        
        spreadsheet = client.open_by_url(sheet_url)
        worksheet_islemler = spreadsheet.worksheet("Islemler")
        worksheet_uyeler = spreadsheet.worksheet("Uyeler")
        
        return worksheet_islemler, worksheet_uyeler
    except Exception as e:
        st.error(f"Veri tabanı hatası: {e}")
        st.stop()

ws_islemler, ws_uyeler = get_sheets()

# --- 5. YARDIMCI FONKSİYONLAR ---
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

def portfoy_hesapla(df):
    if df.empty: return {}, 0.0
    if 'Tarih' in df.columns:
        df['Tarih'] = pd.to_datetime(df['Tarih'], errors='coerce')
        df = df.sort_values(by='Tarih')
    
    portfoy = {} 
    gerceklesen_kar_zarar = 0.0
    
    for index, row in df.iterrows():
        hisse = row['Hisse Adı']
        islem = row['İşlem']
        adet = zorla_sayi_yap(row['Lot'])
        fiyat = zorla_sayi_yap(row['Fiyat'])
        
        if hisse not in portfoy: portfoy[hisse] = {'Adet': 0.0, 'Ort_Maliyet': 0.0}
        mevcut = portfoy[hisse]
        
        if islem == "Alış":
            eski_tutar = mevcut['Adet'] * mevcut['Ort_Maliyet']
            yeni_tutar = adet * fiyat
            toplam_adet = mevcut['Adet'] + adet
            mevcut['Ort_Maliyet'] = (eski_tutar + yeni_tutar) / toplam_adet if toplam_adet > 0 else 0
            mevcut['Adet'] = toplam_adet
        elif islem == "Satış":
            satis_kari = (fiyat - mevcut['Ort_Maliyet']) * adet
            gerceklesen_kar_zarar += satis_kari
            mevcut['Adet'] -= adet
            if mevcut['Adet'] < 0: mevcut['Adet'] = 0 
            
    return portfoy, gerceklesen_kar_zarar

# --- 6. GİRİŞ VE KAYIT SİSTEMİ ---
if 'giris_yapildi' not in st.session_state: st.session_state.giris_yapildi = False
if 'kullanici_adi' not in st.session_state: st.session_state.kullanici_adi = ""

def giris_sayfasi():
    st.markdown("<h1 style='text-align: center;'>🔐 Yatırımcı Pro Giriş</h1>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Giriş Yap", "Hızlı Kayıt Ol"])
    
    # --- GİRİŞ YAP ---
    with tab1:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            kullanici = st.text_input("Kullanıcı Adı")
            sifre = st.text_input("Şifre", type="password")
            if st.button("Giriş Yap", use_container_width=True):
                uyeler = ws_uyeler.get_all_records()
                uye_df = pd.DataFrame(uyeler)
                
                if not uye_df.empty and kullanici in uye_df['Kullanıcı Adı'].values:
                    kayitli_sifre = uye_df[uye_df['Kullanıcı Adı'] == kullanici]['Şifre'].values[0]
                    if sifre_kontrol(sifre, kayitli_sifre):
                        st.session_state.giris_yapildi = True
                        st.session_state.kullanici_adi = kullanici
                        st.success(f"Hoş geldin {kullanici}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Hatalı şifre!")
                else:
                    st.error("Kullanıcı bulunamadı.")

    # --- KAYIT OL (SADELEŞTİRİLMİŞ) ---
    with tab2:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.info("Kayıt olmak için sadece Kullanıcı Adı ve Şifre yeterlidir.")
            yeni_kullanici = st.text_input("Belirleyeceğiniz Kullanıcı Adı")
            # Email/Telefon kısmı kaldırıldı
            yeni_sifre = st.text_input("Belirleyeceğiniz Şifre", type="password")
            yeni_sifre_tekrar = st.text_input("Şifre Tekrar", type="password")
            
            if st.button("Kayıt Ol", use_container_width=True):
                if yeni_sifre != yeni_sifre_tekrar:
                    st.error("Şifreler uyuşmuyor!")
                elif not yeni_kullanici or not yeni_sifre:
                    st.error("Bilgiler boş olamaz.")
                else:
                    uyeler = ws_uyeler.get_all_records()
                    uye_df = pd.DataFrame(uyeler)
                    if not uye_df.empty and yeni_kullanici in uye_df['Kullanıcı Adı'].values:
                        st.error("Bu kullanıcı adı zaten alınmış.")
                    else:
                        try:
                            tarih = datetime.now().strftime("%Y-%m-%d")
                            sifreli = sifrele(yeni_sifre)
                            # Kayıt: Kullanıcı Adı, Şifre, Tarih (Email yok)
                            ws_uyeler.append_row([yeni_kullanici, sifreli, tarih])
                            st.success("Kayıt başarılı! Şimdi giriş yapabilirsiniz.")
                        except Exception as e:
                            st.error(f"Kayıt hatası: {e}")

if not st.session_state.giris_yapildi:
    giris_sayfasi()
    st.stop()

# ==========================================
# İÇERİK (GİRİŞ YAPAN KULLANICI)
# ==========================================

tum_veriler = ws_islemler.get_all_records()
df_tum = pd.DataFrame(tum_veriler)

if not df_tum.empty:
    df_tum.columns = df_tum.columns.str.strip()
    df = df_tum[df_tum['Kullanıcı'] == st.session_state.kullanici_adi].copy()
    if 'Lot' in df.columns: df['Lot'] = df['Lot'].apply(zorla_sayi_yap)
    if 'Fiyat' in df.columns: df['Fiyat'] = df['Fiyat'].apply(zorla_sayi_yap)
else:
    df = pd.DataFrame(columns=["Kullanıcı", "Tarih", "Hisse Adı", "İşlem", "Lot", "Fiyat", "Halka Arz"])

# --- MENÜ ---
with st.sidebar:
    st.write(f"👤 **Aktif Üye:** {st.session_state.kullanici_adi}")
    st.title("Yatırımcı v7.1")
    secim = st.radio("Menü", ["📊 Canlı Portföy", "🚀 Halka Arzlar", "🧠 Portföy Analizi", "➕ İşlem Ekle", "📝 İşlem Geçmişi"])
    st.divider()
    if st.button("🔄 Yenile"):
        st.cache_data.clear()
        st.rerun()
    if st.button("🔒 Çıkış"):
        st.session_state.giris_yapildi = False
        st.session_state.kullanici_adi = ""
        st.rerun()

# --- SAYFALAR ---

# 1. CANLI PORTFÖY
if secim == "📊 Canlı Portföy":
    st.header(f"📊 {st.session_state.kullanici_adi} - Portföy Durumu")
    if not df.empty:
        anlik_portfoy, gerceklesen_kar_zarar = portfoy_hesapla(df.copy())
        
        ozet_listesi = []
        eldekilerin_degeri = 0
        eldekilerin_maliyeti = 0
        
        my_bar = st.progress(0, text="Verileriniz çekiliyor...")
        aktif_hisseler = [k for k, v in anlik_portfoy.items() if v['Adet'] > 0]
        toplam_sayi = len(aktif_hisseler)
        
        if toplam_sayi > 0:
            for i, sembol in enumerate(aktif_hisseler):
                my_bar.progress(int(((i+1) / toplam_sayi) * 100), text=f"{sembol}...")
                veri = anlik_portfoy[sembol]
                adet = veri['Adet']
                ort_maliyet = veri['Ort_Maliyet']
                guncel_fiyat, sirket_adi = veri_getir_ozel(sembol)
                
                veri_durumu = "✅ Canlı"
                if guncel_fiyat is None:
                    guncel_fiyat = ort_maliyet
                    veri_durumu = "⚠️ Veri Yok"
                
                guncel_tutar = adet * guncel_fiyat
                maliyet_tutari = adet * ort_maliyet
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
                    "Anlık K/Z": round(potansiyel_kar, 2),
                    "Durum": veri_durumu
                })
        my_bar.empty()

        col1, col2, col3, col4 = st.columns(4)
        potansiyel_toplam_kz = eldekilerin_degeri - eldekilerin_maliyeti
        net_genel_durum = gerceklesen_kar_zarar + potansiyel_toplam_kz
        
        col1.metric("Portföy Değeri", f"{eldekilerin_degeri:,.2f} ₺")
        col2.metric("Kesinleşmiş K/Z", f"{gerceklesen_kar_zarar:,.2f} ₺")
        col3.metric("Anlık K/Z", f"{potansiyel_toplam_kz:,.2f} ₺")
        col4.metric("GENEL NET DURUM", f"{net_genel_durum:,.2f} ₺", delta=f"{net_genel_durum:,.2f} ₺")
        
        st.divider()
        if ozet_listesi:
            st.dataframe(pd.DataFrame(ozet_listesi), use_container_width=True)
            
            st.divider()
            st.subheader("⚡ Hızlı Satış")
            eldekiler = [item['Kod'] for item in ozet_listesi]
            c1, c2, c3, c4 = st.columns(4)
            with c1: satilacak_hisse = st.selectbox("Hisse Seç", eldekiler)
            secilen_veri = next((item for item in ozet_listesi if item['Kod'] == satilacak_hisse), None)
            if secilen_veri:
                max_lot = secilen_veri['Adet']
                anlik_fiyat = secilen_veri['Anlık Fiyat']
                with c2: sat_lot = st.number_input("Adet", min_value=0.0, max_value=max_lot, value=max_lot)
                with c3: sat_fiyat = st.number_input("Satış Fiyatı", value=anlik_fiyat)
                with c4:
                    st.write("")
                    st.write("")
                    if st.button("🔴 SATIŞI ONAYLA", use_container_width=True, type="primary"):
                        if sat_lot > 0:
                            try:
                                tarih_bugun = datetime.now().strftime("%Y-%m-%d")
                                temiz_fiyat = str(sat_fiyat).replace(',', '.')
                                yeni_veri = [st.session_state.kullanici_adi, tarih_bugun, satilacak_hisse, "Satış", sat_lot, temiz_fiyat, "FALSE"]
                                ws_islemler.append_row(yeni_veri)
                                st.success("Satıldı!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e: st.error(f"Hata: {e}")
        else:
            st.info("Portföyünüz boş.")
            
        st.divider()
        with st.expander("🚨 Hesabımı Sıfırla"):
            st.write("Sadece SİZE AİT olan tüm veriler silinecektir.")
            if st.button("⚠️ VERİLERİMİ SİL"):
                st.session_state.sifirlama_onay = True
        
        if st.session_state.get('sifirlama_onay'):
            st.error("EMİN MİSİNİZ? Geri alınamaz.")
            if st.button("✅ EVET, SİL", type="primary"):
                try:
                    all_rows = ws_islemler.get_all_values()
                    header = all_rows[0]
                    rows = all_rows[1:]
                    new_rows = [row for row in rows if row[0] != st.session_state.kullanici_adi]
                    
                    ws_islemler.clear()
                    ws_islemler.append_row(header)
                    if new_rows: ws_islemler.append_rows(new_rows)
                    
                    st.success("Hesabınız sıfırlandı.")
                    st.session_state.sifirlama_onay = False
                    time.sleep(2)
                    st.rerun()
                except Exception as e: st.error(f"Hata: {e}")

    else:
        st.info("Henüz işlem yapmadınız.")

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
        else: st.warning("Veri yok.")

# 4. İŞLEM EKLE
elif secim == "➕ İşlem Ekle":
    st.header("Yeni Yatırım Ekle")
    if 'otomatik_fiyat' not in st.session_state: st.session_state.otomatik_fiyat = 0.0
    col1, col2 = st.columns(2)
    with col1:
        hisse = st.text_input("Hisse Kodu").upper()
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
                yeni_veri = [st.session_state.kullanici_adi, str(tarih), temiz_hisse, islem, lot, temiz_fiyat, str(halka_arz).upper()]
                ws_islemler.append_row(yeni_veri)
                st.success("✅ Kaydedildi!")
                st.session_state.otomatik_fiyat = 0.0
            except Exception as e: st.error(f"Hata: {e}")
        else: st.warning("Eksik bilgi.")

# 5. GEÇMİŞ
elif secim == "📝 İşlem Geçmişi":
    st.header("📝 Tüm Kayıtlar")
    if not df.empty: st.dataframe(df, use_container_width=True)
