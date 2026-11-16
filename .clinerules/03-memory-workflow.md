# 03 — Protocole de mémoire (memory-bank/)

## Début de tâche (obligatoire)

Lis `memory-bank/` **avant** toute nouvelle tâche, dans cet ordre :

1. `projectbrief.md` — objectifs et périmètre fonctionnel.
2. `techContext.md` — stack, versions, dépendances, commandes.
3. `systemPatterns.md` — arborescence et choix techniques.
4. `activeContext.md` — état courant du dépôt et prochaines étapes.
5. `progress.md` — journal des changements.

Ne redemande pas ce qui y est déjà documenté : vérifie d'abord la mémoire, puis le code.

## Après chaque changement majeur (obligatoire)

Mets à jour la mémoire dans le même mouvement que le code :

- `activeContext.md` : branche courante, état du travail, prochaines étapes.
- `progress.md` : entrée datée `## AAAA-MM-JJ — <résumé>` avec fichiers touchés et décisions.
- `systemPatterns.md` / `techContext.md` : uniquement si l'architecture, les dépendances ou les commandes changent.
- `projectbrief.md` : uniquement si le périmètre fonctionnel évolue.

Un « changement majeur » = nouvelle fonctionnalité, nouveau module, changement de schéma DB (migration), modification des hypothèses financières, ajout/suppression de dépendance, changement d'interface (CLI, API, UI).

## Cohérence

- La mémoire décrit l'état **réel** du dépôt : jamais de supposition ni de TODO inventé.
- Pas de duplication : une information vit dans un seul fichier de mémoire, les autres y renvoient.
- `memory-bank/activeContext.md` est ignoré par Git (contexte de travail local).
