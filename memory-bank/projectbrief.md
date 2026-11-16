# Project brief — immo-buzz

## Objectif

Détecter des **projets immobiliers à haut potentiel** partout en France : scraper les annonces de vente via l'API JSON de **Bien'ici**, estimer leur **rendement locatif**, ne conserver que celles qui dépassent un seuil, et les historiser en base.

## Périmètre fonctionnel

1. **Recherche géographique** : ville centre géocodée + rayon en km (défaut : Lille, 10 km). Les communes du rayon sont résolues en zones Bien'ici ; les annonces hors rayon sont écartées (coordonnées WGS84 stockées).
2. **Pagination** : `--max-pages` s'applique **par zone de recherche** (une commune = une zone), pas globalement.
3. **Évaluation financière** (par annonce) :
   - `prix_total = prix + 8 % frais de notaire + travaux`
   - `travaux = coût_fixe(état) + coût_m²(état) × surface + prime DPE F/G`, borné (plafond €/m² et ratio max du prix)
   - `loyer_brut = loyer déclaré × 12`, sinon loyer estimé (grille €/m²/mois par commune, typologie, tranche de surface — ANIL/DGALN 2023 × OLL MEL)
   - `charges = copro (1,8 €/m²/mois, appartements/immeubles) + taxe foncière + gestion (7 %) + vacance (4 %)`
   - `rendement_brut = loyer_brut / prix_total`, `rendement_net = (loyer_brut - charges) / prix_total`, cash-flow mensuel indicatif (taux 3,5 %).
4. **Détection d'état** du bien par mots-clés (titre + description), DPE en signal secondaire (F/G ⇒ rénovation + prime).
5. **Filtrage** : conservation si rendement brut `>= 8 %` (`--min-yield` / `IMMO_MIN_YIELD_PCT`) ; rejet des rendements invraisemblables (> 40 %), des prix aberrants (< 5 000 € ou < 150 €/m² hors parkings), des viagers/ventes en démembrement.
6. **Cycle de vie des annonces** : une annonce déjà connue est mise à jour (ses estimations sont recalculées, `discovered_at` conservé) ; une annonce dont l'URL n'existe plus est marquée `sold = true` ; réapparue ⇒ `sold = false`.
7. **Mode `--dry-run`** : analyse et scoring sans aucune écriture en base.

## Hors périmètre (état actuel)

- **API FastAPI** (`backend/app/main.py`) et **UI Streamlit** (`frontend/app.py`) : présents mais encore au stade de starters génériques (`Item`), non branchés sur la couche `db` du domaine.
- Pas d'authentification, pas de déploiement, pas d'ordonnancement automatique (cron) : exécution manuelle via la CLI.
- Une seule source d'annonces active (Bien'ici) ; l'architecture en `Protocol` permet d'en ajouter.

## Critères de succès

- Une exécution `uv run immo-buzz` produit une liste d'annonces au rendement brut ≥ seuil, persistées et dédupliquées par `(source, source_id)`.
- Les hypothèses financières restent **éditables** (`config.py`, `engine/grids.py`) et surchargeables par variables d'environnement, sans toucher au code.
- Le calcul et le filtrage sont couverts par des tests unitaires (`tests/`).
