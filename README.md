# immo-buzz

Scrapper de projets immobiliers à haut potentiel sur la métropole lilloise.

## Workflow

`uv run immo-buzz` (ou `uv run python -m immo_buzz`) récupère les annonces de
vente de la métropole lilloise via l'API JSON de Bien'ici, calcule un rendement
locatif brut estimé pour chacune, puis stocke en SQLite celles qui atteignent le
seuil de rendement. Les annonces dont l'URL n'existe plus sont marquées
`sold = true` (vendues).

Pour mettre à niveau une base existante :

```bash
uv run alembic upgrade head
```

```
# Analyse complète, sans écriture en base
uv run immo-buzz --dry-run

# 1 page par zone, seuil abaissé à 7%
uv run immo-buzz --max-pages 1 --min-yield 7

# Limiter la recherche à deux communes
uv run immo-buzz --commune Lille --commune Roubaix
```

## Calcul du rendement

```
prix_total   = prix + 8% de frais de notaire + travaux (€/m² selon l'état déduit)
rendement    = loyer_mensuel_estimé * 12 / prix_total * 100
```

- Le loyer théorique vient d'une grille de `€/m²/mois` par typologie et par
  tranche de surface (constantes éditables dans `src/immo_buzz/engine/grids.py`).
- L'état du bien est déduit des mots-clés du titre et de la description, avec le
  DPE en signal secondaire.
- Un bien est conservé si `rendement >= 8%` (réglable via `--min-yield` ou
  `IMMO_MIN_YIELD_PCT`). Les rendements invraisemblables (> 20%) sont écartés.

## Structure

```
src/immo_buzz/
├── config.py           # hypothèses financières et réglages (env IMMO_*)
├── cli.py              # interface en ligne de commande
├── pipeline.py         # orchestration fetch -> calcul -> filtrage -> stockage
├── scraper/            # sources d'annonces (Bien'ici, zones de recherche)
├── engine/             # grilles de loyers, détection d'état, calcul de rendement
└── db/                 # modèles SQLModel, session SQLite (WAL), repository
```

La couche `db/` est indépendante du scraper et du moteur : les futures couches
FastAPI et Streamlit peuvent la réutiliser directement.

## Configuration

Variables d'environnement (préfixe `IMMO_`) :

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `IMMO_DATABASE_URL` | `sqlite:///data/app.db` | base SQLite cible |
| `IMMO_MIN_YIELD_PCT` | `8.0` | seuil de rendement brut |
| `IMMO_MAX_YIELD_PCT` | `20.0` | plafond de vraisemblance |
| `IMMO_NOTARY_FEE_RATE` | `0.08` | frais de notaire |
| `IMMO_REQUEST_DELAY_S` | `1.0` | délai entre deux requêtes |
| `IMMO_MAX_PAGES` | `5` | pages par source |
| `IMMO_PAGE_SIZE` | `100` | annonces par page (max 100) |

## Développement

```
uv run pytest
uv run ruff check --fix
uv run ruff format
uv run pre-commit install
```
