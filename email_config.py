import os
from typing import Dict, Any

# Configuration email
EMAIL_CONFIG = {
    "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
    "email_user": os.getenv("EMAIL_USER", "votre email"),
    "email_password": os.getenv("EMAIL_PASSWORD", "mot de passe"),
    "team_email": os.getenv("TEAM_EMAIL", "equipe email"),
    "use_tls": True
}

def get_email_config() -> Dict[str, Any]:
    """Retourne la configuration email"""
    return EMAIL_CONFIG
