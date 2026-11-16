# System patterns — immo-buzz

## Arborescence

```
immo-buzz/
├── pyproject.toml, uv.lock, ruff.toml, alembic.ini, .pre-commit-config.yaml
├── .env / .env.example          # configuration IMMO_* (git-ignorée : .env)
├── data/                        # app.db (SQLite, WAL) — git-ignorée
├── src/immo_buzz/
│   ├── __init__.py              # main() -> cli.main
│   ├── __main__.py              # python -m immo_buzz
│   ├── config.py                # Settings (frozen dataclass) + load_settings()
│   ├── cli.py                    # build_parser(), main(), main_with_settings()
│   ├── pipeline.py               # Pipeline, PipelineResult, build_bienici_source,
│   │                             #   build_listing_create, format_result
│   ├── scraper/
│   │   ├── base.py               # RawListing (Pydantic), protocoles ListingSource
│   │   │                         #   et ListingAvailabilityChecker
│   │   ├── bienici.py            # BieniciSource (fetch/iter_listings/is_available)
│   │   ├── geocoding.py          # GeoResolver (suggest + résolution commune)
│   │   └── areas.py              # SearchArea, resolve_zone_ids
│   ├── engine/
│   │   ├── grids.py              # grilles loyers/copro/taxe/works, Condition
│   │   ├── condition.py          # detect_condition (mots-clés + DPE)
│   │   ├── exclusion.py          # detect_exclusion (viager, démembrement…)
│   │   └── yield_calc.py         # Evaluation, evaluate(), is_high_potential()
│   └── db/
│       ├── models.py             # ListingBase/Create/Read, Listing(table=True)
│       ├── session.py            # make_engine(), init_db(), get_session()
│       └── repository.py         # upsert, mark_sold, list, count
├── migrations/                   # Alembic (env.py + versions/0001..0006)
├── backend/app/main.py           # starter FastAPI (modèle Item, non branché)
├── frontend/app.py               # starter Streamlit (+ dataviz.ipynb)
└── tests/                        # conftest.py, fixtures/*.json, test_*.py
```

## Découpage et sens des dépendances

```
cli.py ──> pipeline.py ──> scraper/  (fetch, availability)
                     ├──> engine/   (évaluation financière, pur)
                     └──> db/       (persistance)
engine/ ──> config.py + db.models (PropertyType) uniquement
db/     ──> config.py uniquement (URL par défaut)
```

- **`db/`** est la couche socle : elle ne dépend ni du scraper ni du moteur, ce qui permet à `backend/` et `frontend/` de la réutiliser sans dupliquer la config engine.
- **`engine/`** est pur : aucune I/O, aucun réseau, aucune écriture en base ⇒ tests déterministes.
- **`scraper/`** est branché par contrat (duck typing via `Protocol` `runtime_checkable`) : le pipeline teste `isinstance(source, ListingAvailabilityChecker)` pour savoir si le marquage « vendu » est possible. Ajouter une source ne modifie pas `pipeline.py`.
- **`pipeline.py`** ne contient que l'orchestration : comptage, filtrage, `upsert`, et la projection `RawListing + Evaluation → ListingCreate`.

## Patterns clés

### 1. Configuration typée et immuable

`Settings` est une `@dataclass(frozen=True)` ; la CLI la dérive avec `dataclasses.replace()` pour surcharger sans muter. La fonction `load_settings()` lit `IMMO_*` via un helper `_env()` et filtre les clés inconnues sur `fields(Settings)`.

### 2. Scraping par protocoles

```python
@runtime_checkable
class ListingSource(Protocol):
    name: str

    def fetch(self, *, page: int, page_size: int) -> list[RawListing]: ...
    def iter_listings(self, *, max_pages: int, page_size: int) -> list[RawListing]: ...
```

`RawListing` (Pydantic, `model_config = ConfigDict(extra="ignore")`) est la frontière entre le monde extérieur et le domaine : normalisé, il porte déjà les signaux texte extraits (loyer déclaré, taxe foncière, DPE, coordonnées).

### 3. Moteur financier pur

`Evaluation` est un `@dataclass(frozen=True)` qui expose **tous** les postes (loyers, notaire, travaux, copro, taxe, gestion, vacance, net, cash-flow, `is_high_potential`, `rejection_reason`). `evaluate()` est une fonction de liste de garde-fous : chaque rejet passe par `_rejected(...)` qui renvoie une `Evaluation` complète mais neutralisée (`is_high_potential=False`, `rejection_reason` renseignée).

Les hypothèses chiffrées vivent dans `config.py` (`DEFAULT_*`) ou `engine/grids.py` (grilles par commune, `Condition` en `StrEnum`) et sont surchargeables — jamais de constante magique dans la logique.

### 4. Persistance SQLModel

- Hiérarchie `ListingBase` → `ListingCreate` / `ListingRead` / `Listing(table=True)` : les schémas d'API réutilisent `ListingRead` au lieu d'être redéclarés.
- `UniqueConstraint("source", "source_id")` garantit l'idempotence des runs.
- `upsert_listing()` retourne `(entity, created: bool)` et réinitialise `sold = False` à la réapparition ; `mark_listing_sold()` retourne `True` seulement si l'état a changé (les compteurs du pipeline restent justes).
- Horodatage UTC via `datetime.now(UTC)` ; `discovered_at` posé à la création, `updated_at` à chaque écriture.
- Schéma guidé par Alembic ; `init_db()` (create_all) sert aux tests/`--dry-run` seulement.

### 5. Idempotence et sûreté d'exécution

- `--dry-run` court-circuite toute session et ne crée même pas le fichier de base.
- `is_available()` retourne `bool | None` : `None` (erreur réseau/rate limit) ne doit **jamais** marquer une annonce comme vendue.
- Nouvelles colonnes = migration Alembic + `models.py` + `pipeline.build_listing_create` (projection explicite, arrondis `round(x, 2)`).

### 6. Tests

`tests/conftest.py` charge les payloads JSON de `tests/fixtures/` ; les sources factices (`StubSource`, `AvailabilityStubSource`) implémentent les protocoles en mémoire ; les tests de persistance utilisent `tmp_path` comme URL SQLite.
