import streamlit as st
import pandas as pd
from datetime import datetime

# --- AYARLAR ---
st.set_page_config(page_title="Yatırımcı", layout="wide")
st.title("📈 Yatırımcı: Kişisel Portföy Yöneticisi")

# --- 1️⃣ KAYIT BÖLÜMÜ (Input) ---
# Verileri geçici hafızada tutmak için (Daha sonra veritabanına bağlanacak)
if 'islemler' not in st.session_state:
    st.session_state.islemler = pd.DataFrame(columns=[
        "Tarih", "Hisse Adı", "İşlem", "Lot", "Fiyat", "Halka Arz"
    ])

with st.expander("➕ Yeni İşlem Ekle", expanded=True):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        hisse = st.text_input("Hisse Adı (Örn: THYAO)").upper()
        islem_tipi = st.selectbox("İşlem", ["Alış", "Satış"])
    
    with col2:
        lot = st.number_input("Lot", min_value=1, step=1)
        fiyat = st.number_input("Fiyat (TL)", min_value=0.0, format="%.2f")
    
    with col3:
        tarih = st.date_input("Tarih", datetime.now())
        halka_arz = st.checkbox("Bu bir Halka Arz mı?")

    if st.button("Kaydet"):
        if hisse and lot > 0 and fiyat > 0:
            yeni_satir = {
                "Tarih": tarih, "Hisse Adı": hisse, "İşlem": islem_tipi,
                "Lot": lot, "Fiyat": fiyat, "Halka Arz": halka_arz
            }
            # Pandas concat ile veri ekleme
            st.session_state.islemler = pd.concat([st.session_state.islemler, pd.DataFrame([yeni_satir])], ignore_index=True)
            st.success(f"{hisse} işlemi başarıyla kaydedildi!")
        else:
            st.error("Lütfen hisse adı, lot ve fiyat bilgilerini eksiksiz girin.")

# --- 2️⃣ HESAPLAMA MOTORU (Logic) ---
if not st.session_state.islemler.empty:
    df = st.session_state.islemler
    
    # Portföy Özeti Hesaplama Mantığı
    ozet_listesi = []
    
    for sembol in df['Hisse Adı'].unique():
        temp_df = df[df['Hisse Adı'] == sembol]
        
        alislar = temp_df[temp_df['İşlem'] == 'Alış']
        satislar = temp_df[temp_df['İşlem'] == 'Satış']
        
        toplam_alinan_lot = alislar['Lot'].sum()
        toplam_satilan_lot = satislar['Lot'].sum()
        net_lot = toplam_alinan_lot - toplam_satilan_lot
        
        # Ortalama Maliyet Hesabı (Ağırlıklı Ortalama)
        if toplam_alinan_lot > 0:
            toplam_harcama = (alislar['Lot'] * alislar['Fiyat']).sum()
            ortalama_maliyet = toplam_harcama / toplam_alinan_lot
        else:
            ortalama_maliyet = 0
            
        durum = "Açık" if net_lot > 0 else "Kapalı"
        
        # Not: Kar/Zarar için güncel fiyat lazım (Sonraki etapta API ile gelecek)
        # Şimdilik maliyet üzerinden gösteriyoruz.
        
        ozet_listesi.append({
            "Hisse": sembol,
            "Net Lot": net_lot,
            "Ort. Maliyet": round(ortalama_maliyet, 2),
            "Durum": durum
        })
    
    ozet_df = pd.DataFrame(ozet_listesi)

    # --- 3️⃣ GÖRÜNTÜLEME (Visualization) ---
    st.divider()
    col_ozet, col_detay = st.columns([1, 1])
    
    with col_ozet:
        st.subheader("📊 Portföy Özeti")
        st.dataframe(ozet_df, use_container_width=True)
        
    with col_detay:
        st.subheader("📝 İşlem Geçmişi")
        st.dataframe(df.sort_values(by="Tarih", ascending=False), use_container_width=True)

    # --- 4️⃣ AI ANALİZ (Behavior Engine) ---
    st.divider()
    st.subheader("🤖 AI Davranış Analizi")
    st.caption("AI, 'Al/Sat' tavsiyesi vermez. Sadece yatırım alışkanlıklarını analiz eder.")
    
    if st.button("Davranışlarımı Analiz Et"):
        st.spinner("AI geçmiş işlemlerini inceliyor...")
        
        # --- SİMÜLASYON ANALİZİ ---
        # Gerçek AI bağlayana kadar mantığı burada kuruyoruz
        halka_arz_sayisi = len(df[df['Halka Arz'] == True])
        toplam_islem = len(df)
        
        analiz_metni = ""
        
        # Kural 1: Halka Arz Bağımlılığı Kontrolü
        if halka_arz_sayisi > 0 and (halka_arz_sayisi / toplam_islem) > 0.5:
            analiz_metni += "⚠️ **Uyarı:** Portföy hareketlerinin %50'sinden fazlası Halka Arz odaklı. Bu, kısa vadeli işlem yoğunluğunu artırabilir. Uzun vadeli temettü veya büyüme hisselerine odaklanmayı değerlendirebilirsin.\n\n"
        
        # Kural 2: Tek Hisse Yoğunlaşması
        if len(ozet_df) == 1 and toplam_islem > 3:
             analiz_metni += "⚠️ **Dikkat:** Tüm sermayeni tek bir hisseye yatırmış görünüyorsun. 'Yumurta sepeti' kuralını hatırla, çeşitlendirme riskini düşürebilir.\n\n"
             
        if analiz_metni == "":
            analiz_metni = "✅ **Analiz:** İşlemlerin dengeli görünüyor. Belirgin bir riskli davranış kalıbı (FOMO, aşırı işlem vb.) tespit edilmedi."
            
        st.markdown(analiz_metni)

else:
    st.info("Henüz bir işlem girmediniz. Yukarıdan ilk hissenizi ekleyin.")
