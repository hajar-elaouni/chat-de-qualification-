import os
from typing import Dict, Any

# Configuration MySQL
DATABASE_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "dreampastry"),
    "charset": "utf8mb4"
}

def get_database_config() -> Dict[str, Any]:
    """Retourne la configuration de la base de données"""
    return DATABASE_CONFIG