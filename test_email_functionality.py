#!/usr/bin/env python3
"""
Script de test pour la fonctionnalité d'envoi d'email
"""

import os
import sys
from email_service import EmailService
from llm import detect_inscription_intent, process_inscription_request

def test_detection_intent():
    """Test de la détection d'intention d'inscription"""
    print("🧪 Test de détection d'intention d'inscription...")
    
    test_cases = [
        ("Je veux m'inscrire à une formation", True),
        ("Comment puis-je participer à une formation ?", True),
        ("Je suis intéressé par une formation", True),
        ("Quels sont vos tarifs ?", False),
        ("Quelle est votre adresse ?", False),
        ("Je souhaite suivre une formation de pâtisserie", True),
        ("Comment s'inscrire ?", True),
        ("Bonjour, je voudrais une formation", True),
    ]
    
    for question, expected in test_cases:
        result = detect_inscription_intent(question)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{question}' -> {result} (attendu: {expected})")
    
    print()

def test_email_config():
    """Test de la configuration email"""
    print("🧪 Test de la configuration email...")
    
   
    required_vars = ["EMAIL_USER", "EMAIL_PASSWORD", "TEAM_EMAIL"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Variables d'environnement manquantes: {', '.join(missing_vars)}")
        print("📝 Configurez ces variables dans votre environnement ou fichier .env")
        return False
    else:
        print("✅ Toutes les variables d'environnement sont configurées")
        return True

def test_email_service():
    """Test du service email avec des données fictives"""
    print("🧪 Test du service email...")
    
    if not test_email_config():
        print("⚠️ Impossible de tester le service email sans configuration")
        return False
    
    
    client_info = {
        "nom": "Dupont",
        "prenom": "Jean",
        "age": 25,
        "statut": "Salarié",
        "cpf": "Oui",
        "ville": "Paris",
        "preference": "Présentiel",
        "budget": 1500
    }
    
    formation_details = "Test de formation de pâtisserie française"
    
    try:
        email_service = EmailService()
        result = email_service.send_inscription_email(client_info, formation_details)
        
        if result:
            print("✅ Email de test envoyé avec succès")
        else:
            print("❌ Échec de l'envoi de l'email de test")
        
        return result
    except Exception as e:
        print(f"❌ Erreur lors du test email: {str(e)}")
        return False

def main():
    """Fonction principale de test"""
    print("🚀 Test de la fonctionnalité d'envoi d'email - Dream Pastry\n")
    
  
    test_detection_intent()
    

    config_ok = test_email_config()
    
 
    if config_ok:
        test_email_service()
    else:
        print("⚠️ Tests email ignorés - configuration manquante")
    
    print("\n📋 Instructions pour la configuration:")
    print("1. Configurez les variables d'environnement:")
    print("   - EMAIL_USER: votre email")
    print("   - EMAIL_PASSWORD: votre mot de passe d'application")
    print("   - TEAM_EMAIL: email de l'équipe")
    print("2. Pour Gmail, utilisez un mot de passe d'application")
    print("3. Relancez ce script pour tester l'envoi d'email")

if __name__ == "__main__":
    main()
