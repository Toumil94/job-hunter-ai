# 🤖 Job Hunter AI

> **Automatise ta recherche d'emploi 24/7 — gratuitement.**

Un système IA complet qui scrape les offres d'emploi, les analyse avec Claude, génère des lettres de motivation personnalisées, et t'envoie un rapport quotidien. Le tout tourne automatiquement sur GitHub Actions.

## ⚡ Ce que ça fait

| Fonctionnalité | Description |
|---|---|
| 🔍 **Scraping multi-plateforme** | Adzuna, Indeed, JobUp.ch |
| 🧠 **Matching IA** | Claude analyse et score chaque offre vs ton profil (0-100%) |
| ✍️ **Lettres de motivation** | Générées automatiquement et personnalisées par offre |
| 📧 **Rapports email** | Rapport HTML quotidien avec les meilleures offres |
| 🔔 **Relances auto** | Rappels de relance à J+7, J+14, J+21 |
| 📊 **Tracking** | Suivi complet de toutes tes candidatures |
| 🆓 **100% gratuit** | Tourne sur GitHub Actions (2000 min/mois gratuit) |

## 🚀 Installation (10 minutes)

### 1. Clone et configure

```bash
git clone https://github.com/ton-user/job-hunter-ai.git
cd job-hunter-ai
pip install -r requirements.txt
cp .env.example .env
```

### 2. Obtiens tes clés API (gratuites)

| Service | Lien | Coût |
|---|---|---|
| **Anthropic (Claude)** | [console.anthropic.com](https://console.anthropic.com/) | ~3-5€/mois |
| **Adzuna** | [developer.adzuna.com](https://developer.adzuna.com/) | Gratuit |
| **Gmail App Password** | [Guide Google](https://support.google.com/accounts/answer/185833) | Gratuit |

### 3. Remplis le fichier `.env`

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxx
ADZUNA_APP_ID=ton_id
ADZUNA_APP_KEY=ta_key
EMAIL_SENDER=ton.email@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_RECIPIENT=ton.email@gmail.com
```

### 4. Personnalise ton profil

Édite `config/profile.yaml` avec tes infos, compétences, et critères de recherche.

### 5. Premier test

```bash
# Mode simulation (ne postule pas vraiment)
python -m src.main scan
```

### 6. Déploie sur GitHub Actions (24/7 gratuit)

```bash
git init
git add .
git commit -m "🚀 Initial setup"
git remote add origin https://github.com/ton-user/job-hunter-ai.git
git push -u origin main
```

Puis dans **GitHub → Settings → Secrets → Actions**, ajoute tes clés API.

## 📋 Commandes

```bash
python -m src.main hunt       # 🎯 Cycle complet (scrape → match → apply → report)
python -m src.main scan       # 📡 Scan seul (pas de candidature)
python -m src.main followup   # 🔔 Vérifie les relances à faire
python -m src.main stats      # 📊 Affiche les statistiques
python -m src.main export     # 📥 Exporte en CSV
python -m src.main daemon     # 👹 Mode continu local
```

## 📁 Structure

```
job-hunter-ai/
├── config/
│   ├── profile.yaml          # Ton profil et critères
│   └── settings.yaml         # Config technique
├── src/
│   ├── scrapers/             # Scrapers multi-plateforme
│   ├── matcher/              # Matching IA avec Claude
│   ├── tracker/              # Suivi des candidatures
│   ├── notifier/             # Rapports email HTML
│   └── main.py               # Orchestrateur principal
├── data/
│   └── applications.json     # Base de données locale
├── .github/workflows/
│   └── daily_hunt.yml        # GitHub Actions (24/7)
└── .env                      # Tes clés API (ne pas commiter!)
```

## ⚙️ Configuration

### Score de matching

Dans `config/profile.yaml` :
- `min_match_score: 70` → Score minimum pour postuler automatiquement
- `min_report_score: 50` → Score minimum pour apparaître dans le rapport

### Planning (GitHub Actions)

Dans `.github/workflows/daily_hunt.yml` :
- Scan matin : 7h CET
- Scan soir : 18h CET
- Relances : 9h CET

### Mode simulation

Dans `config/settings.yaml`, `safety.dry_run: true` permet de tout tester sans envoyer de vraies candidatures.

## 💰 Coût réel

| Service | Coût mensuel |
|---|---|
| GitHub Actions | **Gratuit** |
| Adzuna API | **Gratuit** |
| Gmail SMTP | **Gratuit** |
| Claude API | **~3-5€** |
| **Total** | **~3-5€/mois** |

## 🔒 Sécurité

- Mode `dry_run` activé par défaut
- Limite de candidatures par jour configurable
- Délai entre les candidatures
- Clés API dans les secrets GitHub (jamais commitées)

## 📈 Roadmap

- [ ] Scraper LinkedIn (via cookies)
- [ ] Auto-apply sur les sites qui le permettent
- [ ] Dashboard web local
- [ ] Intégration calendrier pour les entretiens
- [ ] Préparation automatique d'entretien

---

*Built with 🤖 Claude + Python + GitHub Actions*
