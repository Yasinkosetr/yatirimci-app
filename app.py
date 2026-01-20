import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import yfinance as yf
import time
import hashlib

# --- 1. AYARLAR ---
st.set_page_config(page_title="Yatırımcı Pro V9.4", layout="wide", initial_sidebar_state="expanded")

# --- 2. TASARIM ---
st.markdown(
    """
    <style>
    .stApp {background-color: #0E1117; background-image: linear-gradient(to right, #0f2027, #203a43, #2c5364);}
    [data-testid="stSidebar"] {background-color: #1c1c1e; border-right: 1px solid #333;}
    html, body, [class*="css"] {font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #E0E0E0;}
    .stButton>button {background-image: linear-gradient(19deg, #F4D03F 0%, #16A085 100%); color: white; border: none; border-radius: 10px; width: 100%;}
    [data-testid="stMetricValue"] {font-size: 1.4rem !important;}
    div[data-testid="stMetric"] {background-color: rgba(255,255,255,0.05); padding: 10px; border-radius: 10px; text-align: center; border: 1px solid rgba(255,255,255,0.1);}
    
    /* Özel Buton Renkleri */
    .stButton button[kind="primary"] {background-image: linear-gradient(to right, #11998e, #38ef7d) !important; color: white !important;}
    .stButton button[kind="secondary"] {background-image: linear-gradient(to right, #cb2d3e, #ef473a) !important; color: white !important;}
    </style>
    """, unsafe_allow_html=True
)

# --- 3. GÜVENLİK ---
def sifrele(sifre): return hashlib.sha256(str.encode(sifre)).hexdigest()
def sifre_kontrol(girilen, db_sifre): return sifrele(girilen) == db_sifre

# --- 4. GOOGLE SHEETS ---
def get_sheets():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets ayarı bulunamadı.")
            st.stop()
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], ['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        # 👇 LİNKİ BURAYA YAPIŞTIR 👇
        sheet_url = "https://docs.google.com/spreadsheets/d/1ijPoTKNsXZBMxdRdMa7cpEhbSYt9kMwoqf5nZFNi7S8/edit?gid=499369690#gid=499369690"
        spreadsheet = client.open_by_url(sheet_url)
        return spreadsheet.worksheet("Islemler"), spreadsheet.worksheet("Uyeler")
    except Exception as e:
        st.error(f"Veri tabanı hatası: {e}")
        st.stop()

ws_islemler, ws_uyeler = get_sheets()

# --- 5. YARDIMCI FONKSİYONLAR ---
def zorla_sayi_yap(deger):
    try:
        metin = str(deger).strip().replace("TL", "").replace("$", "").replace(" ", "")
        if "," in metin: metin = metin.replace(".", "").replace(",", ".")
        elif metin.count(".") > 1: metin = metin.replace(".", "")
        return float(metin)
    except: return 0.0

@st.cache_data(ttl=60)
def veri_getir_ozel(hisse_kodu):
    sembol = str(hisse_kodu).strip().upper()
    if not sembol.endswith(".IS") and "-" not in sembol:
        try:
            tik = yf.Ticker(f"{sembol}.IS")
            h = tik.history(period="5d")
            if not h.empty:
                fiyat = h['Close'].iloc[-1]
                degisim = ((fiyat - h['Close'].iloc[-2]) / h['Close'].iloc[-2] * 100) if len(h) >= 2 else 0.0
                return fiyat, tik.info.get('longName', sembol), f"{sembol}.IS", degisim
        except: pass
    try:
        tik = yf.Ticker(sembol)
        h = tik.history(period="5d")
        if not h.empty:
            fiyat = h['Close'].iloc[-1]
            degisim = ((fiyat - h['Close'].iloc[-2]) / h['Close'].iloc[-2] * 100) if len(h) >= 2 else 0.0
            return fiyat, tik.info.get('longName', sembol), sembol, degisim
    except: pass
    return None, sembol, sembol, 0.0

@st.cache_data(ttl=300)
def piyasa_verileri_getir():
    return ['THYAO.IS', 'GARAN.IS', 'ASELS.IS', 'SASA.IS', 'EREGL.IS', 'TUPRS.IS', 'FROTO.IS', 'KCHOL.IS', 'SISE.IS', 'BIMAS.IS', 'AKBNK.IS', 'HEKTS.IS', 'PETKM.IS', 'KONTR.IS', 'ASTOR.IS']

def portfoy_hesapla(df):
    if df.empty: return {}, 0.0
    if 'Tarih' in df.columns: df['Tarih'] = pd.to_datetime(df['Tarih'], errors='coerce')
    df = df.sort_values(by='Tarih')
    portfoy, gerceklesen = {}, 0.0
    for _, row in df.iterrows():
        h, i, a, f = row['Hisse Adı'], row['İşlem'], zorla_sayi_yap(row['Lot']), zorla_sayi_yap(row['Fiyat'])
        if h not in portfoy: portfoy[h] = {'Adet': 0.0, 'Ort_Maliyet': 0.0}
        mevcut = portfoy[h]
        if i == "Alış":
            toplam_adet = mevcut['Adet'] + a
            mevcut['Ort_Maliyet'] = ((mevcut['Adet'] * mevcut['Ort_Maliyet']) + (a * f)) / toplam_adet if toplam_adet > 0 else 0
            mevcut['Adet'] = toplam_adet
        elif i == "Satış":
            satis_kari = (f - mevcut['Ort_Maliyet']) * a
            gerceklesen += satis_kari
            mevcut['Adet'] = max(0, mevcut['Adet'] - a)
    return portfoy, gerceklesen

def hisse_performans_analizi(sembol):
    ticker = yf.Ticker(sembol)
    hist = ticker.history(period="5y")
    if hist.empty: return None
    suan = hist['Close'].iloc[-1]
    def degisim(gun): return ((suan - hist['Close'].iloc[-gun-1]) / hist['Close'].iloc[-gun-1] * 100) if len(hist) > gun else 0.0
    return {"Fiyat": suan, "1 Gün": degisim(1), "1 Hafta": degisim(5), "3 Ay": degisim(63), "1 Yıl": degisim(252), "5 Yıl": degisim(1260)}

# --- 6. GİRİŞ SİSTEMİ ---
if 'giris_yapildi' not in st.session_state: st.session_state.giris_yapildi = False
if 'kullanici_adi' not in st.session_state: st.session_state.kullanici_adi = ""
if 'secilen_hisse_detay' not in st.session_state: st.session_state.secilen_hisse_detay = None

def giris_sayfasi():
    st.markdown("<h1 style='text-align: center;'>🔐 Yatırımcı Pro Giriş</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Giriş", "Kayıt"])
    with t1:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            u = st.text_input("Kullanıcı")
            p = st.text_input("Şifre", type="password")
            if st.button("Giriş"):
                udf = pd.DataFrame(ws_uyeler.get_all_records())
                if not udf.empty and u in udf['Kullanıcı Adı'].values:
                    if sifre_kontrol(p, udf[udf['Kullanıcı Adı']==u]['Şifre'].values[0]):
                        st.session_state.giris_yapildi = True
                        st.session_state.kullanici_adi = u
                        st.rerun()
                    else: st.error("Hatalı Şifre")
                else: st.error("Kullanıcı Yok")
    with t2:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            nu = st.text_input("Yeni Kullanıcı")
            np = st.text_input("Yeni Şifre", type="password")
            if st.button("Kayıt Ol"):
                try:
                    ws_uyeler.append_row([nu, sifrele(np), datetime.now().strftime("%Y-%m-%d")])
                    st.success("Kayıt Başarılı")
                except: st.error("Hata")

if not st.session_state.giris_yapildi:
    giris_sayfasi()
    st.stop()

# --- VERİ YÜKLEME ---
try:
    df_tum = pd.DataFrame(ws_islemler.get_all_records())
    if not df_tum.empty:
        df_tum.columns = df_tum.columns.str.strip()
        df = df_tum[df_tum['Kullanıcı'] == st.session_state.kullanici_adi].copy()
        if 'Lot' in df.columns: df['Lot'] = df['Lot'].apply(zorla_sayi_yap)
        if 'Fiyat' in df.columns: df['Fiyat'] = df['Fiyat'].apply(zorla_sayi_yap)
    else: df = pd.DataFrame()
except: df = pd.DataFrame()

# --- MENÜ ---
with st.sidebar:
    st.write(f"👤 **{st.session_state.kullanici_adi}**")
    secim = st.radio("Menü", ["📊 Canlı Portföy", "📈 Borsa Takip", "🚀 Halka Arzlar", "🧠 Portföy Analizi", "➕ İşlem Ekle", "📝 İşlem Geçmişi"])
    st.divider()
    if st.button("🔄 Yenile"): st.cache_data.clear(); st.rerun()
    if st.button("🔒 Çıkış"): 
        st.session_state.giris_yapildi = False
        st.session_state.secilen_hisse_detay = None
        st.rerun()

# --- HİSSE DETAY SAYFASI ---
def hisse_detay_goster(sembol):
    st.button("⬅️ Geri Dön", on_click=lambda: st.session_state.update(secilen_hisse_detay=None))
    with st.spinner(f"{sembol} analiz ediliyor..."):
        fiyat, isim, tam_kod, degisim = veri_getir_ozel(sembol)
        analiz = hisse_performans_analizi(tam_kod)
        
    if analiz:
        st.header(f"📈 {isim} ({tam_kod})")
        st.metric("Anlık Fiyat", f"{analiz['Fiyat']:.2f} ₺", delta=f"%{degisim:.2f}")
        
        st.divider()
        st.subheader("📊 Performans Karnesi")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("1 Gün", f"%{analiz['1 Gün']:.2f}", delta=f"{analiz['1 Gün']:.2f}")
        c2.metric("1 Hafta", f"%{analiz['1 Hafta']:.2f}", delta=f"{analiz['1 Hafta']:.2f}")
        c3.metric("3 Ay", f"%{analiz['3 Ay']:.2f}", delta=f"{analiz['3 Ay']:.2f}")
        c4.metric("1 Yıl", f"%{analiz['1 Yıl']:.2f}", delta=f"{analiz['1 Yıl']:.2f}")
        c5.metric("5 Yıl", f"%{analiz['5 Yıl']:.2f}", delta=f"{analiz['5 Yıl']:.2f}")
        
        st.divider()
        col_al, col_sat = st.columns(2)
        with col_al:
            al_lot = st.number_input("Alınacak Lot", min_value=1, key="detay_al_lot")
            if st.button("AL (Ekle)", key="detay_btn_al", type="primary"):
                try:
                    tarih = datetime.now().strftime("%Y-%m-%d")
                    fiyat_str = str(analiz['Fiyat']).replace(',', '.')
                    ws_islemler.append_row([st.session_state.kullanici_adi, tarih, tam_kod, "Alış", al_lot, fiyat_str, "FALSE"])
                    st.success("Alındı!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error(f"Hata: {e}")
        with col_sat:
            sat_lot = st.number_input("Satılacak Lot", min_value=1, key="detay_sat_lot")
            if st.button("SAT (Düş)", key="detay_btn_sat", type="secondary"):
                try:
                    tarih = datetime.now().strftime("%Y-%m-%d")
                    fiyat_str = str(analiz['Fiyat']).replace(',', '.')
                    ws_islemler.append_row([st.session_state.kullanici_adi, tarih, tam_kod, "Satış", sat_lot, fiyat_str, "FALSE"])
                    st.success("Satıldı!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error(f"Hata: {e}")
    else: st.error("Veri yok.")

# --- SAYFALAR ---
if st.session_state.secilen_hisse_detay:
    hisse_detay_goster(st.session_state.secilen_hisse_detay)
else:
    if secim == "📊 Canlı Portföy":
        st.header("📊 Canlı Portföy")
        if not df.empty:
            anlik, gerceklesen = portfoy_hesapla(df.copy())
            aktifler = [k for k, v in anlik.items() if v['Adet'] > 0]
            eldekilerin_degeri, eldekilerin_maliyeti = 0, 0
            
            if aktifler:
                for s in aktifler:
                    v = anlik[s]
                    gf, _, kod, degisim = veri_getir_ozel(s)
                    gf = gf if gf else v['Ort_Maliyet']
                    c1, c2, c3, c4 = st.columns([1.5, 2, 2, 2])
                    if c1.button(f"🔎 {s}", key=f"btn_{s}"):
                        st.session_state.secilen_hisse_detay = s
                        st.rerun()
                    tutar = v['Adet'] * gf
                    kar = tutar - (v['Adet'] * v['Ort_Maliyet'])
                    c2.metric("Adet", f"{v['Adet']:.0f}")
                    c3.metric("Fiyat", f"{gf:.2f} ₺", delta=f"%{degisim:.2f}")
                    c4.metric("K/Z", f"{kar:,.0f} ₺", delta=f"{kar:,.0f}")
                    eldekilerin_degeri += tutar
                    eldekilerin_maliyeti += (v['Adet'] * v['Ort_Maliyet'])
                st.divider()
                genel_net = gerceklesen + (eldekilerin_degeri - eldekilerin_maliyeti)
                c1, c2 = st.columns(2)
                c1.metric("Portföy Değeri", f"{eldekilerin_degeri:,.2f} ₺")
                c2.metric("GENEL NET DURUM", f"{genel_net:,.2f} ₺", delta=f"{genel_net:,.2f}")

                # Portföy İçi Hızlı Al/Sat
                st.divider()
                with st.expander("⚡ Hızlı Al/Sat Paneli", expanded=True):
                    secilen_hisse = st.selectbox("Hisse", aktifler, key="hzl_select")
                    hzl_fiyat, _, hzl_kod, _ = veri_getir_ozel(secilen_hisse)
                    if not hzl_fiyat: hzl_fiyat = 0.0
                    col_hzl1, col_hzl2 = st.columns(2)
                    hzl_lot = st.number_input("Lot", min_value=1, key="hzl_lot")
                    hzl_islem_fiyati = st.number_input("Fiyat", value=float(hzl_fiyat), format="%.2f", key="hzl_fiyat_inp")
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.button("🟢 AL", key="hzl_btn_al", type="primary", use_container_width=True):
                            try:
                                tarih = datetime.now().strftime("%Y-%m-%d")
                                f_str = str(hzl_islem_fiyati).replace(',', '.')
                                ws_islemler.append_row([st.session_state.kullanici_adi, tarih, hzl_kod, "Alış", hzl_lot, f_str, "FALSE"])
                                st.success("Eklendi!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e: st.error(f"Hata: {e}")
                    with col_b2:
                        if st.button("🔴 SAT", key="hzl_btn_sat", type="secondary", use_container_width=True):
                            try:
                                tarih = datetime.now().strftime("%Y-%m-%d")
                                f_str = str(hzl_islem_fiyati).replace(',', '.')
                                ws_islemler.append_row([st.session_state.kullanici_adi, tarih, hzl_kod, "Satış", hzl_lot, f_str, "FALSE"])
                                st.success("Satıldı!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e: st.error(f"Hata: {e}")

                # 🔥🔥🔥 SIFIRLAMA BUTONU BURADA 🔥🔥🔥
                st.divider()
                with st.expander("🚨 Hesabımı Sıfırla (Geri Dönüş Yok)"):
                    st.write("Bu işlem SADECE SENİN tüm alım satım geçmişini siler. Bakiye sıfırlanır.")
                    if st.button("⚠️ TÜM VERİLERİMİ SİL"):
                        st.session_state.sifirlama_onay = True
                
                if st.session_state.get('sifirlama_onay'):
                    st.error("🛑 EMİN MİSİN? Tüm geçmişin silinecek.")
                    k1, k2 = st.columns(2)
                    with k1:
                        if st.button("✅ EVET, SİL", type="primary"):
                            try:
                                # Tüm veriyi çek
                                all_rows = ws_islemler.get_all_values()
                                header = all_rows[0]
                                data_rows = all_rows[1:]
                                
                                # Sadece bu kullanıcının OLMADIĞI satırları tut (Başkalarını silme)
                                keep_rows = [row for row in data_rows if row[0] != st.session_state.kullanici_adi]
                                
                                # Temizle ve geri yükle
                                ws_islemler.clear()
                                ws_islemler.append_row(header)
                                if keep_rows: ws_islemler.append_rows(keep_rows)
                                
                                st.success("Hesabınız tertemiz oldu.")
                                st.session_state.sifirlama_onay = False
                                time.sleep(2)
                                st.rerun()
                            except Exception as e: st.error(f"Hata: {e}")
                    with k2:
                        if st.button("❌ VAZGEÇ"):
                            st.session_state.sifirlama_onay = False
                            st.rerun()

            else: st.info("Portföy boş.")
        else: st.warning("Veri yok.")

    elif secim == "📈 Borsa Takip":
        st.header("📈 Piyasa Ekranı")
        ara = st.text_input("Hisse Ara")
        if ara:
            if st.button(f"Git -> {ara.upper()}"):
                st.session_state.secilen_hisse_detay = ara
                st.rerun()
        st.divider()
        st.subheader("🔥 Popüler Hisseler")
        populerler = piyasa_verileri_getir()
        cols = st.columns(4)
        for i, s in enumerate(populerler):
            f, _, k, d = veri_getir_ozel(s)
            with cols[i%4]:
                if f:
                    st.metric(label=s.replace(".IS", ""), value=f"{f:.2f} ₺", delta=f"%{d:.2f}")
                    if st.button("Detay", key=f"pop_{s}"):
                        st.session_state.secilen_hisse_detay = s.replace(".IS", "")
                        st.rerun()
                else: st.write(f"{s}: --")

    elif secim == "🚀 Halka Arzlar":
        st.header("🚀 Halka Arzlar")
        if not df.empty and 'Halka Arz' in df.columns:
            arz = df[df['Halka Arz'].astype(str).str.upper() == 'TRUE']
            if not arz.empty: st.dataframe(arz, use_container_width=True)
            else: st.info("Yok.")

    elif secim == "🧠 Portföy Analizi":
        st.header("🧠 Analiz")
        if not df.empty:
            df['Tutar'] = df['Fiyat'] * df['Lot']
            st.bar_chart(df, x="Hisse Adı", y="Tutar")
        else: st.warning("Veri yok.")

    elif secim == "➕ İşlem Ekle":
        st.header("İşlem Ekle")
        c1, c2 = st.columns(2)
        h = c1.text_input("Hisse Kodu").upper()
        if c1.button("⚡ Fiyat Getir"):
            f, _, _, _ = veri_getir_ozel(h)
            if f:
                st.session_state.otomatik_fiyat = float(f)
                st.success(f"{f} TL")
            else: st.error("Yok")
        i = c1.selectbox("İşlem", ["Alış", "Satış"])
        t = c1.date_input("Tarih")
        l = c2.number_input("Lot", min_value=1)
        f = c2.number_input("Fiyat", min_value=0.0, format="%.2f", value=st.session_state.get('otomatik_fiyat', 0.0))
        ha = c2.checkbox("Halka Arz")
        if st.button("Kaydet"):
            try:
                ws_islemler.append_row([st.session_state.kullanici_adi, str(t), h.strip(), i, l, str(f).replace(',', '.'), str(ha).upper()])
                st.success("Kaydedildi")
            except: st.error("Hata")

    elif secim == "📝 İşlem Geçmişi":
        st.header("Geçmiş")
        if not df.empty: st.dataframe(df)
