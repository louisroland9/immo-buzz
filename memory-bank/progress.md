# Progress — journal

Format d'entrée : `## AAAA-MM-JJ — <résumé>` (fichiers touchés, décisions, points ouverts).

## 2026-11-16 — Réintégration du fix de normalisation des loyers

- Constat : `fix/quarterly-rent-normalization` (`5709fb3`, base `c96630d`) n'a
  jamais été fusionnée ; `main` ne contenait ni `_RENT_PERIOD_PATTERN` ni
  `_detect_rent_period_months`. La branche était **en retard de 6 commits** sur
  `main` (merge PR #9 `feature/radius-search` inclus) : un merge naïf aurait
  supprimé `areas.py` / `geocoding.py`.
- `src/immo_buzz/scraper/bienici.py` :
  - `_RENT_PERIOD_PATTERN` + `_RENT_PERIOD_MONTHS` : détection de la période
    déclarée (trimestre, semestre, an/année, mois, **semaine**, formes
    qualifiantes trimestriel/semestriel/annuel/mensuel/hebdomadaire).
  - `_detect_rent_period_months(text, start, end) -> float` : nombre de mois
    couverts par la période, lue dans une fenêtre de ±20/+40 caractères autour du
    montant ; défaut `1.0` (loyer mensuel).
  - Loyer hebdomadaire : `12 / 52` mois (mois partiel, valeur flottante) — sans
    ce cas, « 300 €/semaine » était lu comme 300 €/mois (sous-évaluation ×4,3).
  - `_RENT_PATTERN` accepte désormais `hebdomadaire` dans les qualificatifs.
  - `_parse_monthly_rent` divise le montant par le nombre de mois avant le
    contrôle de plausibilité (`MIN/MAX_PLAUSIBLE_MONTHLY_RENT`).
- `tests/test_bienici.py` : 9 cas paramétrés ajoutés (trimestre, semestre, an,
  mois, semaine, `EUR/semaine`, forme qualifiante, HTML).
- Décision : rebase sur `main` (merge-tree à blanc validé sans conflit) puis PR
  vers `main` — pas de commit direct sur `main` (`02-architecture-conventions` §8).
- Vérifications : `uv run pytest` (164 tests), `uv run ruff check .`,
  `uv run ruff format --check .` — tous verts après rebase.

## 2026-11-16 — Initialisation du harnais Cline

- Création de `memory-bank/` (`projectbrief`, `techContext`, `systemPatterns`, `activeContext`, `progress`).
- Création de `.clinerules/01-agent-persona.md`, `02-architecture-conventions.md`, `03-memory-workflow.md`.
- Dispatch et suppression de `.clinerules/{git,python,sqlModel,tokenOptimisation,memory}.md` (contenu intégré dans `01`/`02`/`03`).
- Ajout de `memory-bank/activeContext.md` au `.gitignore`.
- Aucune modification du code source.
