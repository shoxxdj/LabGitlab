# Lab GitLab (Vagrant + Ansible)

Lab local pour s'entraîner sur GitLab CI/CD : pipelines, GitLab Pages, runners
multi-executors, et **tests de sécurité offensifs/défensifs sur les pipelines
eux-mêmes**.

## Topologie

| VM       | IP (par défaut)  | Rôle                                                         |
|----------|-------------------|---------------------------------------------------------------|
| `gitlab` | 192.168.56.10     | GitLab CE (omnibus) + GitLab Pages                             |
| `runner` | 192.168.56.11     | 3 runners enregistrés : `docker`, `docker-priv` (⚠️), `shell` (⚠️) |

Accès via DNS wildcard public **nip.io** (aucune config DNS nécessaire) :
- GitLab : `http://gitlab.192.168.56.10.nip.io`
- Pages : `http://<group>.pages.192.168.56.10.nip.io/<projet>/`

## Prérequis hôte

- VirtualBox + Vagrant
- Ansible ≥ 2.14 (`pip install ansible` ou paquet système)
- ~8 Go de RAM libres, 20 Go disque
- Accès Internet sortant (paquets GitLab, images Docker) depuis les VMs

## Profils de risque

Le lab démarre par défaut dans un état **sain** : un seul runner Docker non
privilégié, pipeline `vuln-pipeline` sans secret exposé. Les scénarios à
risque (runner privilégié, shell executor, fuite de secrets...) s'activent à
la demande via `lab_profile` :

| Profil | Runners actifs | Ce que ça active |
|---|---|---|
| `default` *(par défaut)* | `docker` | Pipeline propre, aucune faiblesse exposée |
| `secrets-leak` | `docker` | Secret en clair, artefact `.env`, variable CI non protégée affichée dans les logs |
| `docker-priv` | `docker`, `docker-priv` | Runner `privileged: true` + `docker.sock` monté (évasion de conteneur) |
| `shell-exec` | `docker`, `shell` | Runner shell executor (accès direct à la VM runner) |
| `full-vulnerable` | `docker`, `docker-priv`, `shell` | Tous les scénarios cumulés |

Détail de chaque scénario, exploitation et remédiation : `docs/SECURITY-LAB.md`.

```bash
# Premier démarrage dans un profil donné
LAB_PROFILE=docker-priv vagrant up

# Changer de profil sur un lab déjà démarré (idempotent : ajuste les
# runners enregistrés, le .gitlab-ci.yml de vuln-pipeline et ses variables CI)
LAB_PROFILE=shell-exec vagrant provision runner
```

Le profil peut aussi être fixé une bonne fois dans
`ansible/group_vars/all.yml` (`lab_profile: default`) si vous préférez ne pas
passer la variable d'environnement à chaque commande.

## Démarrage

```bash
vagrant up
# ~15-20 min la première fois (installation GitLab CE), profil "default"
```

Identifiants créés automatiquement (LAB UNIQUEMENT, voir `ansible/group_vars/all.yml`) :

| Compte | Login | Mot de passe       | Rôle              |
|--------|-------|--------------------|-------------------|
| root   | root  | `LabSecret#2026x`   | Admin instance     |
| dev    | dev   | `DevLabSecret#2026x`| Developer du groupe `lab` |

Un Personal Access Token root (`glpat-LabBootstrapToken0001`) est créé pour l'API/les scripts.

## Projets de démo (groupe `lab`)

- **`demo-pages`** : site statique + job `pages`, démontre GitLab Pages et le
  template `Secret-Detection` officiel.
- **`vuln-pipeline`** : pipeline et application **volontairement vulnérables**
  (secrets en clair, `curl | sh`, artefacts sensibles, runner privilégié,
  shell executor, IaC non sécurisée...) + jobs de scan open source
  (Gitleaks, Semgrep, Trivy, Hadolint, Checkov). C'est le terrain de jeu
  principal pour la sécurité CI/CD — voir `docs/SECURITY-LAB.md`.

## Commandes utiles

```bash
vagrant status                 # état des VMs
vagrant provision runner       # ré-exécuter Ansible (idempotent)
vagrant ssh gitlab             # entrer dans la VM GitLab
vagrant ssh runner             # entrer dans la VM runner
vagrant halt / vagrant destroy # arrêter / détruire le lab
```

Reconfigurer manuellement GitLab si besoin :
```bash
vagrant ssh gitlab -c "sudo gitlab-ctl reconfigure"
```

## Hors-ligne / sans nip.io

Si les VMs n'ont pas accès à Internet pour résoudre `nip.io`, définissez un
domaine local dans `ansible/group_vars/all.yml` :
```yaml
base_domain: "lab.test"
```
puis ajoutez sur votre **hôte** (`/etc/hosts`, un wildcard nécessite dnsmasq) :
```
192.168.56.10  gitlab.lab.test
192.168.56.10  lab.pages.lab.test demo-pages.lab.pages.lab.test vuln-pipeline.lab.pages.lab.test
```

## Personnalisation

Tout se règle dans `ansible/group_vars/all.yml` : IPs, domaine, mots de passe,
liste des runners (executor, tags, `privileged`, `docker_sock`), image Docker
par défaut des runners, projets à seed.

## Sécurité / avertissement

Ce lab contient **intentionnellement** des secrets en clair, des runners mal
configurés et une application vulnérable. Ne l'exposez jamais au-delà du
réseau privé Vagrant (`192.168.56.0/24`), ne réutilisez aucun mot de passe
d'ici ailleurs, et ne le laissez pas tourner en libre accès sur un réseau
partagé/d'entreprise.
