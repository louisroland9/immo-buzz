# Tech context — immo-buzz

## Langage et outillage

| Élément | Valeur |
| --- | --- |
| Python | `>=3.12` (`.python-version` → `3.12`) |
| Gestionnaire | `uv` (lock `uv.lock`, build backend `uv_build>=0.12.21,<0.13.0`) |
| Layout | `src/` layout, package `immo_buzz` |
| Entrypoint | `immo-buzz = "immo_buzz:main"` |
| Lint/format | `ruff` (line-length 88, target py312, règles `E,F,I,N,UP,B,A,C4,SIM,ARG`) |
| Tests | `pytest` (`testpaths=["tests"]`, `pythonpath=["src"]`, `addopts="-q"`) |
| Hooks | `pre-commit` (ruff-check, ruff-format, check-yaml, end-of-file-fixer, check-added-large-files) |
| Migrations | `alembic` (script_location `migrations/`, URL résolue depuis `IMMO_DATABASE_URL` dans `migrations/env.py`) |
| CI | GitHub Actions (`.github/workflows/ci.yml`) : job `lint` (`ruff check .` + `ruff format --check .`) et job `test` (`pytest`) |

## Dépendances runtime (`pyproject.toml`)

| Paquet | Contrainte |
| --- | --- |
| `duckdb` | `>=1.5.6` |
| `fastapi` | `>=0.143.0` |
| `httpx` | `>=0.28.1` |
| `python-dotenv` | `>=1.2.4` |
| `sqlmodel` | `>=0.0.48` |
| `streamlit` | `>=1.65.0` |
| `uvicorn` | `>=0.54.0` |

## Dépendances de développement (`[dependency-groups].dev`)

| Paquet | Contrainte |
| --- | --- |
| `alembic` | `>=1.20.1` |
| `pre-commit` | `>=4.6.2` |
| `pytest` | `>=9.1.1` |
| `ruff` | `>=0.16.10` |

## Base de données

- SQLite, fichier `data/app.db` (ignoré par Git, `.db*`).
- Engine : `check_same_thread=False`, `timeout=30`, `echo=False`, `PRAGMA journal_mode=WAL` + `PRAGMA foreign_keys=ON` sur chaque connexion.
- Migrations : `migrations/versions/` — `0001_add_sold_column`, `0002_add_net_yield_and_costs`, `0003_add_listing_text_signals`, `0004_add_declared_property_tax`, `0005_add_declared_rent`, `0006_add_coordinates`.

## Configuration (variables `IMMO_*`)

Chargées par `config.load_settings()` depuis l'environnement et `.env` (copie de `.env.example`) ; l'environnement réel a priorité sur `.env`.

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `IMMO_DATABASE_URL` | `sqlite:///data/app.db` | base cible |
| `IMMO_MIN_YIELD_PCT` | `8.0` | seuil de rendement brut |
| `IMMO_MAX_YIELD_PCT` | `40.0` | plafond de vraisemblance |
| `IMMO_MIN_PLAUSIBLE_PRICE` | `5000.0` | prix plancher |
| `IMMO_MIN_PRICE_PER_M2` | `150.0` | prix plancher au m² (hors parkings) |
| `IMMO_NOTARY_FEE_RATE` | `0.08` | frais de notaire |
| `IMMO_MANAGEMENT_FEE_RATE` | `0.07` | frais de gestion locative |
| `IMMO_VACANCY_RATE` | `0.04` | provision vacance |
| `IMMO_MORTGAGE_ANNUAL_RATE` | `0.035` | taux annuel (cash-flow) |
| `IMMO_REQUEST_DELAY_S` | `1.0` | délai entre requêtes HTTP |
| `IMMO_MAX_PAGES` | `5` (README : 24) | pages par commune |
| `IMMO_PAGE_SIZE` | `100` | annonces par page (max 100) |
| `IMMO_CITY` | `Lille` | ville centre |
| `IMMO_RADIUS_KM` | `10.0` | rayon de recherche (km) |

## Commandes

```bash
uv sync --locked --all-extras --dev   # installation
uv run pytest                          # tests
uv run ruff check --fix .              # lint
uv run ruff format .                   # format
uv run alembic upgrade head            # migrations
uv run pre-commit install              # hooks
uv run immo-buzz --dry-run             # pipeline sans écriture
uv run uvicorn backend.app.main:app --reload   # API (starter)
uv run streamlit run frontend/app.py           # UI (starter)
```
