# 02 — Architecture et conventions

## 1. Gestion du projet et dépendances (uv)

- **Interdits :** `pip`, `poetry`, `pipenv`. `uv` exclusivement.
- **Ajout de paquet :** `uv add <package>` (prod) / `uv add --dev <package>` (dev). Le lock `uv.lock` est committé.
- **Exécution :** toujours via `uv run <commande>` (`uv run pytest`, `uv run ruff …`, `uv run immo-buzz …`, `uv run alembic …`).
- **Packaging :** `uv_build` + `src/` layout. L'entrypoint console est `immo-buzz = "immo_buzz:main"` (`src/immo_buzz/__init__.py` → `cli.main`).
- **Python :** `>=3.12` (`.python-version` = 3.12).

## 2. Style, typage et qualité de code

- **Typage obligatoire** sur tous les arguments et retours. Python moderne : `dict[str, int] | None`, `StrEnum`, `match/case` si pertinent.
- **`from __future__ import annotations`** en tête des modules (convention du projet).
- **Docstrings en anglais**, à l'impératif descriptif (`"""Return the stored entity…"""`).
- **Ruff** : `line-length = 88`, `target-version = "py312"`, règles `E,F,I,N,UP,B,A,C4,SIM,ARG` (`ruff.toml`).
  Après chaque modification : `uv run ruff check --fix .` puis `uv run ruff format .`.
- **Tests :** `uv run pytest` (`testpaths = ["tests"]`, `pythonpath = ["src"]`, `addopts = "-q"`). Un fichier `tests/test_<module>.py` par module, fixtures partagées dans `tests/conftest.py`, données JSON dans `tests/fixtures/`.
- **Aucune modification ne doit casser** : lancer tests + ruff avant de considérer une tâche terminée.

## 3. Organisation du code

```
src/immo_buzz/
├── config.py        # Settings (frozen dataclass) + IMMO_* via .env
├── cli.py           # argparse, logging, Pipeline
├── pipeline.py      # fetch -> evaluate -> filter -> persist (orchestration)
├── scraper/         # sources d'annonces : base.py (contrats), bienici, geocoding, areas
├── engine/          # pur, sans I/O : grids, condition, exclusion, yield_calc
└── db/              # models (SQLModel), session (engine/WAL), repository
migrations/          # Alembic (env.py + versions/000N_*.py)
backend/ frontend/   # starters FastAPI / Streamlit (non branchés au domaine)
tests/               # pytest
```

Règles de dépendance entre couches :

- `db/` est **indépendant** du scraper et du moteur : les couches API/UI réutilisent `db/` directement, sans dupliquer la configuration engine.
- `engine/` est **pur** (aucun I/O, aucun réseau) : fonctions déterministes testables, hypothèses dans `config.py` ou `engine/grids.py`.
- `scraper/` expose des **contrats** (`Protocol` `runtime_checkable`) : `ListingSource` (`fetch`, `iter_listings`), `ListingAvailabilityChecker` (`is_available`), et le modèle `RawListing` (Pydantic, `extra="ignore"`). Une nouvelle source implémente ces protocoles, sans modifier le pipeline.
- `pipeline.py` orchestre uniquement : pas de logique métier (rendement → `engine`, persistance → `db/repository`).
- Fonctions d'aide préfixées `_` pour l'interne ; l'API publique est réexportée via les `__init__.py` avec `__all__` explicite.

## 4. Base de données (SQLite / SQLModel)

- **Pattern d'héritage :** `ListingBase(SQLModel)` (champs communs) → `ListingCreate(Base)` (payload d'écriture) → `ListingRead(Base)` (+ `id`, `sold`, timestamps) → `Listing(Base, table=True)` (table physique, `id: int | None = Field(default=None, primary_key=True)`).
- **Nommage :** classes simples et singulières ; contraintes via `__table_args__` avec `UniqueConstraint` explicite.
- **Engine :** `connect_args = {"check_same_thread": False, "timeout": 30}`, `echo=False`, plus un listener `connect` qui exécute `PRAGMA journal_mode=WAL;` et `PRAGMA foreign_keys=ON;` (`db/session.py::make_engine`).
- **Sessions :** `get_session(engine)` en générateur (`yield`) pour garantir la fermeture ; en FastAPI, dépendance `SessionDep = Annotated[Session, Depends(get_session)]`.
- **Requêtes :** `session.exec(select(...))` de `sqlmodel` (pas de `session.query`). Tri/exclusion via `col(...)` pour les colonnes typées.
- **Mise à jour :** `obj.sqlmodel_update(payload.model_dump(exclude={...}))`, puis `commit` et `refresh`.
- **Schéma :** `SQLModel.metadata.create_all()` reste pour `--dry-run`/tests ; **toute évolution du schéma passe par une migration Alembic** (`migrations/versions/000N_*.py`, `uv run alembic upgrade head`). Jamais d'ALTER manuel. Une nouvelle colonne ⇒ migration + mise à jour de `models.py` + `pipeline.build_listing_create` si elle est alimentée par le scraper.
- La base vit dans `data/` (`sqlite:///data/app.db`), ignorée par Git.

## 5. Backend (FastAPI)

- Injection par `Annotated[Session, Depends(get_session)]`.
- **Séparer** les modèles de table des schémas d'API (réutiliser `ListingRead` du domaine, ne pas redéclarer un modèle parallèle).
- `async def` **uniquement** pour de l'I/O asynchrone ; les opérations SQLModel synchrones restent en `def` (ne pas bloquer la boucle d'événements).
- Le starter `backend/app/main.py` (modèle `Item`) est générique : le brancher sur `immo_buzz.db` sur demande explicite uniquement.

## 6. Interface (Streamlit)

- `@st.cache_data` pour les lectures (requêtes, appels API), `@st.cache_resource` pour les ressources (engine, client HTTP).
- `st.session_state` centralisé, clés initialisées au démarrage de page.
- **Aucune logique métier** dans les vues : appeler la couche `db/` ou l'API FastAPI.
- Le starter `frontend/app.py` est générique (endpoint `/items/`) : adapter à `immo_buzz` sur demande explicite.

## 7. Configuration et secrets

- Variables `IMMO_*` lues par `load_settings()` ; `.env` chargé automatiquement (`load_dotenv(..., override=False)`), l'environnement réel a priorité. `.env` est ignoré par Git, `.env.example` documente les variables.
- Toute nouvelle hypothèse financière devient une constante nommée dans `config.py` (préfixe `DEFAULT_`) **et** une entrée dans `Settings` + `_env(...)` + `.env.example` + README.

## 8. Workflow Git

- **Conventional Commits**, messages **en anglais** : `feat(scope): …`, `fix(scope): …`, `test(scope): …`, `docs: …`.
- **Un commit par unité logique terminée** ; jamais de gros commit fourre-tout.
- **Jamais de commit/push direct sur `main`/`master`.** Branche dédiée par tâche : `feature/nom-de-la-tache` ou `fix/nom-du-bug`.
- Avant commit : `git status` + `git diff` pour vérifier le contenu réel ; **jamais de `git add .` aveugle** ; ne jamais forcer l'ajout d'un fichier ignoré.
- Éviter de committer `memory-bank/activeContext.md` (contexte local, cf. `.gitignore`).
- Avant push : `git pull --rebase`. **En cas de conflit : s'arrêter et demander l'aide de l'utilisateur.**

## 9. Commandes de référence

| But | Commande |
| --- | --- |
| Analyse complète sans écriture | `uv run immo-buzz --dry-run` |
| Recherche ciblée | `uv run immo-buzz --city Lyon --radius 20 --min-yield 7 --max-pages 1` |
| Tests | `uv run pytest` |
| Lint / format | `uv run ruff check --fix .` · `uv run ruff format .` |
| Migration | `uv run alembic upgrade head` |
| Hooks Git | `uv run pre-commit install` |
| API / UI (starters) | `uv run uvicorn backend.app.main:app --reload` · `uv run streamlit run frontend/app.py` |
