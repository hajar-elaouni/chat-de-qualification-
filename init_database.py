#!/usr/bin/env python3
"""
Script d'initialisation de la base de données Dream Pastry
"""

from database_service import get_database_service

def main():
    print("🚀 Initialisation de la base de données Dream Pastry...")
    
    db_service = get_database_service()
    
    if not db_service.connect():
        print("❌ Impossible de se connecter à la base de données")
        return False
    
    print("✅ Connexion à MySQL réussie")
    
    if db_service.create_tables():
        print("✅ Tables créées avec succès")
    else:
        print("❌ Erreur lors de la création des tables")
        return False
    
    db_service.populate_sample_data()
    print("✅ Données d'exemple insérées")
    
    db_service.disconnect()
    print("🎉 Initialisation terminée avec succès !")
    return True

if __name__ == "__main__":
    main()