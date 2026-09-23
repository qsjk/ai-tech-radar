# ADR 0013 — Frontend React · TypeScript · Vite et CSP stricte

| | |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-15 ; VII §35, §37.3 · VIII §46.2 · VI §31 ; décision E20 ; `docs/architecture.md` §2, §4.3 |

## Contexte

Le dashboard est une application de lecture riche (Overview, Feed, vues Topic et Event) pour un utilisateur
(VI §31). Les sorties LLM et les contenus tiers sont affichés : le frontend doit résister à l'injection. Caddy sert le
statique et porte les en-têtes de sécurité (VII §37).

## Décision

Le frontend est une SPA **React · TypeScript · Vite**, buildée dans l'image Caddy et servie en statique. La CSP est
stricte (`default-src 'self'`) : aucun script ni style en ligne, aucune bibliothèque de CSS-in-JS à l'exécution
(VII §37.3). Le stylage se fait en **CSS Modules** compilés par Vite (E20), compatibles avec cette CSP.

## Alternatives écartées

- **Framework à rendu serveur (Next.js, Nuxt)** : un serveur Node permanent de plus ; la SPA statique suffit à un utilisateur.
- **Bibliothèque de composants à CSS-in-JS à l'exécution** : injecte des balises `<style>` : exigerait d'élargir `style-src` et affaiblirait la CSP (E20, option C écartée).
- **Framework utilitaire compilé (type Tailwind)** : compatible avec la CSP (E20, option B), mais non retenu : les CSS Modules suffisent et n'ajoutent pas d'outil.
- **Pages rendues par FastAPI (templates)** : l'API ne sert pas la SPA (II décision 7) ; la CSP et le cache du statique relèvent de Caddy.

## Conséquences

- **On gagne** : CSP stricte vérifiée par T-SEC-06 ; build statique immuable, cache maîtrisé (VII §37.3) ; typage de bout en bout.
- **On accepte** : pas de bibliothèque de composants à CSS-in-JS ; les styles dynamiques passent par des classes ou l'attribut `style` posé par React (CSSOM, VII §37.3).
- **Preuve de réexamen** : **une bibliothèque frontend exige des styles injectés** : déclencheur conditionnel du registre, ADR d'élargissement de `style-src` (IX §54.3) ; une vulnérabilité sans correctif dans la chaîne React ou Vite ; M9 hors critère imputé au frontend.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
