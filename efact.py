import streamlit as st
import os
from dotenv import load_dotenv

# Încărcăm variabilele de mediu (ex: ANAF_ACCESS_TOKEN)
load_dotenv()

# Setarea configurației paginii se face aici, pentru a fi aplicată global
# și trebuie să fie prima comandă Streamlit executată.
st.set_page_config(
    page_title="eFact Dashboard",
    layout="wide",
    initial_sidebar_state="expanded", # Asigură că bara de navigare este vizibilă
)

# Titlul principal al aplicației, vizibil deasupra barei de navigare
st.sidebar.image("siglaabc.gif", width=75)
st.sidebar.title("Navigare e-Factura")

# Putem adăuga un mesaj de bun venit sau instrucțiuni pe pagina principală (opțional)
st.title("Bine ați venit la aplicația e-Factura version 1.1!")
st.info("Utilizați meniul din stânga pentru a naviga între secțiuni.")

# Serviciul de fundal este acum pornit de `launcher.py`.
# Afișăm doar un mesaj informativ în interfața grafică.
st.success("✅ Serviciul de verificare automată a statusului facturilor rulează în fundal.")