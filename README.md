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
prix_total   = prix + 8% de frais de notaire + travaux
               travaux = coût_fixe(état) + coût_m²(état) × surface + prime DPE F/G
loyer_brut   = loyer_mensuel_estimé * 12
charges      = copro (€/m²/mois) + taxe_foncière (% du prix) + gestion (7% loyer) + vacance (4% loyer)
loyer_net    = loyer_brut - charges
rendement_brut = loyer_brut / prix_total * 100
rendement_net  = loyer_net  / prix_total * 100
```

- Le loyer théorique vient d'une grille de `€/m²/mois` **par commune** (métropole
  lilloise), par typologie et par tranche de surface. Source : carte des loyers
  ANIL/DGALN 2023 croisée avec l'OLL de la MEL (constantes éditables dans
  `src/immo_buzz/engine/grids.py`, fallback métropole si la commune est inconnue).
- L'**état du bien** est déduit des mots-clés du titre et de la description, avec
  le DPE en signal secondaire (un DPE F/G déclenche un état « rénovation » et
  majore le budget travaux d'une prime de rénovation énergétique).
- Le **budget travaux** combine un **coût fixe par logement** (cuisine, salle
  d'eau, électricité) et un **coût variable au m²** selon l'intensité de
  rénovation, puis est borné (plafond au m² et ratio maximal du prix). Les
  ordres de grandeur s'inspirent des guides FNAIM/ANIL (constantes éditables
  dans `src/immo_buzz/engine/grids.py`).
- La **taxe foncière** est estimée comme un taux effectif appliqué au prix
  d'acquisition, par commune (DGFiP, simplification de la valeur locative
  cadastrale).
- Les **charges de copropriété** non récupérables (`1,8 €/m²/mois`) ne
  s'appliquent qu'aux appartements et immeubles.
- Un bien est conservé si **rendement brut** `>= 8%` (réglable via `--min-yield`
  ou `IMMO_MIN_YIELD_PCT`). Les rendements invraisemblables (> 40%) sont écartés.
  Le rendement **net** est calculé et stocké en complément.

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
| `IMMO_MANAGEMENT_FEE_RATE` | `0.07` | frais de gestion locative (part du loyer) |
| `IMMO_VACANCY_RATE` | `0.04` | provision vacance locative (part du loyer) |
| `IMMO_MORTGAGE_ANNUAL_RATE` | `0.035` | taux annuel pour l'estimation de cash-flow |
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
