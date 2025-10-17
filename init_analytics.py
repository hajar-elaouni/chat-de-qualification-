#!/usr/bin/env python3
"""
Script pour initialiser les tables analytics dans la base de données
"""

from database_service import get_database_service

def main():
    """Initialise les tables analytics"""
    print("🚀 Initialisation des tables analytics...")
    
    db = get_database_service()
    
    if not db.connect():
        print("❌ Impossible de se connecter à la base de données")
        return False
    
    try:
       
        if db.create_tables():
            print("✅ Tables analytics créées avec succès !")
            
         
            print("📊 Insertion de données d'exemple...")
         
            
            print("🎉 Initialisation terminée !")
            print("\n📋 Tables créées :")
            print("  - analytics_sessions")
            print("  - analytics_events") 
            print("  - unanswered_questions")
            print("  - formation_sessions")
            print("\n💡 Vous pouvez maintenant utiliser le dashboard analytics dans l'onglet '📊 Analytics'")
            
            return True
        else:
            print("❌ Erreur lors de la création des tables")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False
    finally:
        db.disconnect()

if __name__ == "__main__":
    main()
