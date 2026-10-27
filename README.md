# IR Watch — flux RSS des publications financières

Surveille les pages « résultats » listées dans `sites.yaml`, deux fois par jour en semaine,
et publie un flux RSS dès qu'un nouveau document (communiqué, présentation, comptes) apparaît.

## Mise en place (≈ 15 min, une seule fois)

1. **Compte GitHub** : crée un compte neutre (sans ton nom) si tu ne veux pas que la liste
   d'entreprises suivies te soit rattachée — le dépôt sera public.
2. **Nouveau dépôt** : `New repository` → nom au choix (ex. `ir-watch`) → *Public* → Create.
3. **Envoyer les fichiers** : `Add file` → `Upload files` → glisse **tout le contenu** du dossier
   (y compris le dossier caché `.github`) → `Commit changes`.
   *Astuce : sur Mac/Windows, le dossier `.github` est caché ; si l'upload ne le prend pas,
   crée le fichier à la main : `Add file` → `Create new file` → nom `.github/workflows/watch.yml`
   → colle le contenu.*
4. **Autoriser l'écriture** : `Settings` → `Actions` → `General` → *Workflow permissions* →
   **Read and write permissions** → Save.
5. **Activer Pages** : `Settings` → `Pages` → Source *Deploy from a branch* → Branch `main`,
   dossier `/docs` → Save.
6. **Premier passage** : onglet `Actions` → `IR Watch` → `Run workflow`. Ce passage enregistre
   l'état de référence (aucune alerte). Ouvre les logs : chaque entreprise doit afficher
   « référence enregistrée : N documents » avec N > 0.
7. **Lecteur RSS** : abonne-toi à `https://<compte>.github.io/<depot>/feed.xml`
   (ou aux flux par entreprise listés sur la page d'accueil du site).

## Fonctionnement

- Tout lien document jamais vu = nouvelle publication. Les documents publiés ensemble
  sont regroupés en une seule entrée.
- Si une page devient illisible (blocage, refonte, contenu en JavaScript), une entrée
  « ⚠️ page à vérifier » est publiée **une seule fois**, l'historique est conservé, et une
  entrée « ✅ suivi rétabli » suit quand la page redevient lisible.
- Délai de détection : au pire ~10 h (passages ~8h10 et ~18h40, heure de Paris, en semaine).
  Modifiable dans `.github/workflows/watch.yml` (heures en UTC).

## Ajouter une entreprise

Copier un bloc dans `sites.yaml` :
```yaml
  - slug: nexans
    name: Nexans
    url: https://...page-resultats...
```
Le premier passage pose la référence. Si les logs affichent 0 document, la page charge
ses documents en JavaScript ou utilise des URL sans `.pdf` : ajouter un `include:` adapté
(voir l'exemple Schneider).

## Tester en local (optionnel)

```
pip install -r requirements.txt
python watch.py --only rexel
```
