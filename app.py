import streamlit as st
import pandas as pd
from datetime import datetime

# --- AYARLAR ---
st.set_page_config(page_title="Yatırımcı Pro", layout="wide", initial_sidebar_state="expanded")
# --- TASARIM VE GÖRSELLEŞTİRME (CSS) ---
st.markdown(
    """
    <style>
    /* 1. Ana Arka Plan Rengi (Koyu Lacivert - Finans Teması) */
    .stApp {
        background-color: #0E1117;
        background-image: linear-gradient(to right, #0f2027, #203a43, #2c5364);
    }

    /* 2. Yan Menü (Sidebar) Tasarımı */
    [data-testid="stSidebar"] {
        background-color: #1c1c1e;
        border-right: 1px solid #333;
    }

    /* 3. Yazı Tipleri (Font) - Google Font benzeri */
    html, body, [class*="css"] {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #E0E0E0; /* Yazı rengi: Açık Gri */
    }

    /* 4. Butonları Güzelleştirme */
    .stButton>button {
        background-color: #F4D03F; /* Altın Sarısı */
        background-image: linear-gradient(19deg, #F4D03F 0%, #16A085 100%);
        color: white;
        border-radius: 10px;
        border: none;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton>button:hover {
        transform: scale(1.05); /* Üzerine gelince büyür */
    }

    /* 5. Tablo Başlıkları */
    thead tr th:first-child {display:none}
    tbody th {display:none}
    </style>
    """,
    unsafe_allow_html=True
)

# --- 0️⃣ GÜVENLİK VE OTURUM AÇMA (Login Sistemi) ---
if 'giris_yapildi' not in st.session_state:
    st.session_state.giris_yapildi = False

def giris_ekrani():
    st.markdown("<h1 style='text-align: center;'>🔐 Yatırımcı Girişi</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        kullanici = st.text_input("Kullanıcı Adı")
        sifre = st.text_input("Şifre", type="password")
        
        if st.button("Giriş Yap", use_container_width=True):
            # ŞİMDİLİK BASİT ŞİFRE: admin / 1234
            if kullanici == "admin" and sifre == "1234":
                st.session_state.giris_yapildi = True
                st.rerun() # Sayfayı yenile ve içeri al
            else:
                st.error("Hatalı kullanıcı adı veya şifre!")

if not st.session_state.giris_yapildi:
    giris_ekrani()
    st.stop() # Giriş yapılmadıysa aşağıdaki kodları çalıştırma

# ==========================================
# GİRİŞ YAPILDIKTAN SONRA ÇALIŞACAK KISIM
# ==========================================

# --- VERİTABANI (Geçici Hafıza) ---
if 'islemler' not in st.session_state:
    st.session_state.islemler = pd.DataFrame(columns=[
        "Tarih", "Hisse Adı", "İşlem", "Lot", "Fiyat", "Halka Arz"
    ])

# --- MENÜ TASARIMI (Sidebar) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3310/3310624.png", width=100) # Logo
    st.title(f"Hoşgeldin, Admin")
    secim = st.radio("Menü", ["📊 Güncel Portföy", "🚀 Halka Arzlar", "➕ İşlem Ekle", "📝 İşlem Geçmişi"])
    
    st.divider()
    if st.button("Çıkış Yap"):
        st.session_state.giris_yapildi = False
        st.rerun()

# --- SAYFA 1: GÜNCEL PORTFÖY ---
if secim == "📊 Güncel Portföy":
    st.header("📊 Güncel Portföy Durumu")
    
    if not st.session_state.islemler.empty:
        df = st.session_state.islemler
        ozet_listesi = []
        
        for sembol in df['Hisse Adı'].unique():
            temp_df = df[df['Hisse Adı'] == sembol]
            alis = temp_df[temp_df['İşlem'] == 'Alış']
            satis = temp_df[temp_df['İşlem'] == 'Satış']
            
            net_lot = alis['Lot'].sum() - satis['Lot'].sum()
            
            if net_lot > 0: # Sadece elimizde olanları göster
                maliyet = (alis['Lot'] * alis['Fiyat']).sum() / alis['Lot'].sum()
                ozet_listesi.append({
                    "Hisse": sembol,
                    "Adet (Lot)": net_lot,
                    "Ort. Maliyet": round(maliyet, 2),
                    "Toplam Değer (Maliyet)": round(net_lot * maliyet, 2)
                })
        
        if ozet_listesi:
            st.dataframe(pd.DataFrame(ozet_listesi), use_container_width=True)
            # Buraya ilerde pasta grafik gelecek
        else:
            st.info("Elinizde açık pozisyon (hisse) bulunmuyor.")
    else:
        st.warning("Henüz hiç işlem yapmadınız.")

# --- SAYFA 2: HALKA ARZLAR ---
elif secim == "🚀 Halka Arzlar":
    st.header("🚀 Halka Arz Takip Merkezi")
    st.caption("Sadece 'Halka Arz' olarak işaretlediğin hisseler burada görünür.")
    
    if not st.session_state.islemler.empty:
        df = st.session_state.islemler
        # Sadece Halka Arz olanları filtrele
        arz_df = df[df['Halka Arz'] == True]
        
        if not arz_df.empty:
            # Özet Tablo
            st.dataframe(arz_df, use_container_width=True)
            
            toplam_arz_kar = len(arz_df) * 500 # Simülasyon kar
            st.metric("Tahmini Halka Arz Kazancı", f"{toplam_arz_kar} TL", "+%10")
        else:
            st.info("Kaydettiğin hiç Halka Arz hissesi yok.")
    else:
        st.info("Veri yok.")

# --- SAYFA 3: İŞLEM EKLE ---
elif secim == "➕ İşlem Ekle":
    st.header("Yeni Yatırım Ekle")
    
    col1, col2 = st.columns(2)
    with col1:
        hisse = st.text_input("Hisse Kodu").upper()
        islem = st.selectbox("İşlem", ["Alış", "Satış"])
        tarih = st.date_input("Tarih", datetime.now())
    with col2:
        lot = st.number_input("Lot", min_value=1)
        fiyat = st.number_input("Fiyat", min_value=0.0, format="%.2f")
        halka_arz = st.checkbox("Halka Arz İşlemi")
        
    if st.button("Kaydet", use_container_width=True):
        yeni_veri = {
            "Tarih": tarih, "Hisse Adı": hisse, "İşlem": islem,
            "Lot": lot, "Fiyat": fiyat, "Halka Arz": halka_arz
        }
        st.session_state.islemler = pd.concat([st.session_state.islemler, pd.DataFrame([yeni_veri])], ignore_index=True)
        st.success("İşlem başarıyla eklendi! Menüden portföyüne bakabilirsin.")

# --- SAYFA 4: İŞLEM GEÇMİŞİ ---
elif secim == "📝 İşlem Geçmişi":
    st.header("📝 Tüm İşlem Defteri")
    if not st.session_state.islemler.empty:
        st.dataframe(st.session_state.islemler.sort_values(by="Tarih", ascending=False), use_container_width=True)
    else:
        st.info("Kayıtlı işlem yok.")
