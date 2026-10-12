#!/bin/bash

# Interrompre le script en cas d'erreur
set -e

echo "🚀 [1/5] Initialisation du projet Python et Git..."
# Initialisation Git si non présent
if [ ! -d ".git" ]; then
    git init
fi

# Initialisation du projet uv si pyproject.toml non présent
if [ ! -f "pyproject.toml" ]; then
    uv init --bare
fi

echo "📦 [2/5] Installation des dépendances avec uv..."
# Ajout des dépendances de production
uv add fastapi uvicorn sqlmodel streamlit

# Ajout des dépendances de développement et sécurité
uv add --dev ruff pre-commit pytest

echo "📁 [3/5] Création de l'arborescence du projet..."
mkdir -p backend/app
mkdir -p frontend/.streamlit
mkdir -p data
mkdir -p /home/louis/Documents/Cline/Rules

echo "🔒 [4/5] Configuration des verrous de sécurité..."

# 1. Configuration de la règle de concision globale
cat << 'EOF' > /home/louis/Documents/Cline/Rules/0-global.md
# 🛑 Style de Communication et Économie de Tokens (Strict)
* **Pas de blabla :** Supprime toutes les formules de politesse, phrases d'introduction ("Certainement !", "Voici le code...") ou de conclusion. Va directement au fait.
* **Pas de narration :** Ne décris pas tes actions étape par étape dans le chat pendant que tu modifies un fichier. Le code parle d'lui-même.
* **Modifications minimales :** Lorsque tu modifies un fichier existant, n'affiche pas ou ne réécris pas les blocs de code inchangés si tu peux l'éviter. Concentre-toi uniquement sur la zone d'impact.
* **Synthèse :** Si une explication est nécessaire, limite-toi à un résumé d'une phrase ou à un maximum de 3 puces courtes.
EOF

# 2. Configuration .gitignore étanche
cat << 'EOF' > .gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
.pytest_cache/
.ruff_cache/

# Base de données SQLite
data/*.db
data/*.db-journal
data/*.db-wal

# Environnement et Secrets
.env
.env.*
!.env.example

# IDE
.vscode/
.idea/
EOF

# 3. Configuration .env.example pour guider l'IA sans fuite
cat << 'EOF' > .env.example
# Configuration de l'application
DATABASE_URL=sqlite:///data/app.db
API_URL=http://localhost:8000
ENVIRONMENT=development
EOF

# 4. Sécurisation de Streamlit
cat << 'EOF' > frontend/.streamlit/config.toml
[server]
headless = true
port = 8501
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false
EOF

# 5. Configuration des Hooks Pre-commit (Ruff)
cat << 'EOF' > .pre-commit-config.yaml
repos:
  - repo: https://github.com
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [ --fix ]
      - id: ruff-format
  - repo: https://github.com
    rev: v4.5.0
    hooks:
      - id: check-yaml
      - id: end-of-file-fixer
      - id: check-added-large-files
EOF

# Activation des hooks git
uv run pre-commit install

echo "💻 [5/5] Génération du code de départ (FastAPI + SQLModel & Streamlit)..."

# 6. Code Backend (FastAPI + SQLModel avec configuration SQLite stricte)
cat << 'EOF' > backend/app/main.py
from typing import Annotated, Generator
from fastapi import FastAPI, Depends, status
from sqlmodel import SQLModel, Field, Session, create_engine, select
from sqlalchemy import event

# 1. Configuration de l'Engine SQLite Sécurisé (Anti-lock & WAL)
DATABASE_URL = "sqlite:///data/app.db"
connect_args = {"check_same_thread": False, "timeout": 30}
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()

# 2. Cycle de vie de la Session
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

# 3. Modèles SQLModel (Pattern d'héritage recommandé)
class ItemBase(SQLModel):
    title: str = Field(index=True)
    description: str | None = Field(default=None)

class ItemCreate(ItemBase):
    pass

class ItemRead(ItemBase):
    id: int

class Item (ItemBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

# Initialisation des tables au démarrage
def init_db():
    SQLModel.metadata.create_all(engine)

app = FastAPI(title="Harnais API Segura", on_startup=[init_db])

@app.post("/items/", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(item_in: ItemCreate, db: SessionDep) -> Item:
    db_item = Item.model_validate(item_in)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@app.get("/items/", response_model=list[ItemRead])
def read_items(db: SessionDep) -> list[Item]:
    return list(db.exec(select(Item)).all())
EOF

# 7. Code Frontend (Streamlit avec gestion du cache)
cat << 'EOF' > frontend/app.py
import streamlit as st
import requests

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
EOF

echo "✨ Configuration terminée avec succès !"
echo "💡 Pour lancer l'API :  uv run uvicorn backend.app.main:app --reload"
echo "💡 Pour lancer l'IHM :  uv run streamlit run frontend/app.py"

echo "📝 [Extra] Assemblage du fichier .clinerules global..."

# Commande d'assemblage automatique à partir de vos fichiers locaux :
cat /home/louis/Documents/Cline/Rules/*.md > .clinerules
