import requests
import streamlit as st

st.set_page_config(page_title="Harnais UI", layout="centered")

# Initialisation obligatoire de l'état (Session State)
if "items_count" not in st.session_state:
    st.session_state.items_count = 0

st.title("🛡️ Tableau de Bord Sécurisé")


# Fonction avec mise en cache obligatoire pour la lecture
@st.cache_data(ttl=60)
def fetch_items_from_api(api_url: str):
    try:
        response = requests.get(f"{api_url}/items/", timeout=5)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        st.error("Impossible de se connecter à l'API FastAPI Backend.")
    return []


API_URL = "http://localhost:8000"

st.subheader("Données récupérées via l'API")
items = fetch_items_from_api(API_URL)

if items:
    st.session_state.items_count = len(items)
    for item in items:
        st.write(f"**{item['title']}** : {item['description'] or 'Pas de description'}")
else:
    st.info("Aucun élément trouvé en base de données.")

st.sidebar.metric("Total Éléments", st.session_state.items_count)
