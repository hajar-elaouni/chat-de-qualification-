## 📋 Étapes pour utiliser le projet Dream Pastry (Version corrigée)

### 1. **Prérequis**
- Python 3.10 installé
- Ollama installé et configuré
- MySQL installé 
- **Clé API Google Gemini** (obligatoire)

### 2. **Cloner le projet**
```bash
git clone https://github.com/hajar-elaouni/chat-de-qualification-
cd [nom-du-repo]
```

### 3. **Installation des dépendances**
```bash
pip install -r requirements.txt
```

### 4. **Configuration d'Ollama**
```bash
# Installer les modèles nécessaires
ollama pull gemma3:4b
ollama pull nomic-embed-text
```

### 5. **Configuration de l'API Gemini** ⚠️ **OBLIGATOIRE**
1. Aller sur [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Créer une clé API Gemini
3. Modifier le fichier `llm.py` ligne 305 :
```python
API_KEY = "VOTRE_CLE_API_GEMINI_ICI"
```

**OU** (recommandé) utiliser une variable d'environnement :
```python
import os
API_KEY = os.getenv("GEMINI_API_KEY", "votre_cle_par_defaut")
```

Puis créer un fichier `.env` :
```env
GEMINI_API_KEY=votre_cle_api_gemini
```

### 6. **Configuration des variables d'environnement** (optionnel)
Créer un fichier `.env` avec :
```env
# Configuration Gemini (OBLIGATOIRE)
GEMINI_API_KEY=votre_cle_api_gemini

# Configuration MySQL (optionnel)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=votre_mot_de_passe
MYSQL_DATABASE=dreampastry

# Configuration Email (optionnel)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER=votre_email@gmail.com
EMAIL_PASSWORD=votre_mot_de_passe_app
TEAM_EMAIL=team@example.com
```

### 7. **Initialisation de la base de données** (optionnel)
```bash
python init_database.py
python init_analytics.py
```

### 8. **Lancement de l'application**

#### Option A : Interface Web (Recommandée)
```bash
streamlit run ui.py
```
L'application sera accessible sur `http://localhost:8501`

#### Option B : Interface en ligne de commande
```bash
python app.py
```

### 9. **Utilisation**

#### Interface Web :
- Ouvrir le navigateur sur `http://localhost:8501`
- L'interface propose un assistant de formation en pâtisserie
- Possibilité de poser des questions sur les formations
- Système de qualification des prospects (utilise Gemini)
- Envoi d'emails automatiques

#### Interface CLI :
- Poser des questions directement dans le terminal
- Taper `exit` pour quitter

### 10. **Fonctionnalités disponibles**
- 🤖 Assistant IA spécialisé en pâtisserie (Ollama + Gemini)
- 📚 Base de connaissances avec documents PDF
- 📧 Système d'envoi d'emails
- 📊 Analytics et suivi des prospects
- 🎯 Qualification automatique des leads (via Gemini)

### 📝 Note importante
Le projet utilise **deux modèles IA** :
- **Ollama** (local) pour l'assistant principal
- **Google Gemini** pour la qualification des prospects et certaines analyses avancées

**⚠️ Attention** : Une clé API Gemini valide est **obligatoire** pour que l'application fonctionne correctement, notamment pour les fonctionnalités de qualification des leads.

