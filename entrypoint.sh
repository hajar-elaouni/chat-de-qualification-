#!/bin/bash
set -e

echo "⏳ Attente de la base de données..."
until nc -z db 3306; do
  sleep 2
done
echo "✅ Base de données disponible !"

echo "🛠️ Création des tables dans la base de données..."
python3 /app/database_service.py || echo "⚠️ Impossible d’exécuter le script de création de tables."

echo "🚀 Lancement de l'application Streamlit..."
exec streamlit run ui.py --server.port=8501 --server.address=0.0.0.0
