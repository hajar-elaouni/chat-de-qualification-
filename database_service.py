import mysql.connector
from mysql.connector import Error
from typing import List, Dict, Any, Optional
from database_config import get_database_config
import logging
import json

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        self.config = get_database_config()
        self.connection = None
    
    def connect(self) -> bool:
        """Établit une connexion à la base de données"""
        try:
            self.connection = mysql.connector.connect(**self.config)
            if self.connection.is_connected():
                logger.info("Connexion à MySQL réussie")
                return True
        except Error as e:
            logger.error(f"Erreur de connexion à MySQL: {e}")
            return False
        return False
    
    def disconnect(self):
        """Ferme la connexion à la base de données"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("Connexion MySQL fermée")
    
    def create_tables(self) -> bool:
        """Crée les tables nécessaires"""
        try:
            cursor = self.connection.cursor()
            
            # Table des formations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS formations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nom VARCHAR(255) NOT NULL,
                    description TEXT,
                    places_max INT NOT NULL DEFAULT 6,
                    places_reservees INT NOT NULL DEFAULT 0,
                    prix DECIMAL(10,2),
                    duree_jours INT,
                    statut ENUM('active', 'inactive', 'complet') DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            
            # Table des sessions de formation
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions_formation (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    formation_id INT NOT NULL,
                    date_debut DATE NOT NULL,
                    date_fin DATE NOT NULL,
                    places_max INT NOT NULL,
                    places_reservees INT NOT NULL DEFAULT 0,
                    statut ENUM('ouverte', 'complet', 'annulee') DEFAULT 'ouverte',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (formation_id) REFERENCES formations(id) ON DELETE CASCADE
                )
            """)
            
            # Table des inscriptions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inscriptions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    client_nom VARCHAR(255) NOT NULL,
                    client_prenom VARCHAR(255) NOT NULL,
                    client_email VARCHAR(255),
                    client_telephone VARCHAR(20),
                    formation_id INT NOT NULL,
                    session_id INT,
                    statut_qualification ENUM('QUALIFIÉ', 'LISTE_D_ATTENTE', 'REFUSÉ') NOT NULL,
                    score_qualification INT,
                    date_inscription TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    statut_inscription ENUM('en_attente', 'confirmee', 'annulee') DEFAULT 'en_attente',
                    FOREIGN KEY (formation_id) REFERENCES formations(id),
                    FOREIGN KEY (session_id) REFERENCES sessions_formation(id)
                )
            """)
            
                        # Table des créneaux précis (date/heure) - nouvelle table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS formation_sessions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    formation_id INT NOT NULL,
                    start_datetime DATETIME NOT NULL,
                    end_datetime DATETIME NOT NULL,
                    label VARCHAR(100) NULL,        -- ex: 'Demi-journée matin'
                    location VARCHAR(100) NULL,     -- ex: 'Paris'
                    capacity INT NULL,              -- optionnel si différent de la formation
                    statut ENUM('ouverte', 'complet', 'annulee') DEFAULT 'ouverte',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (formation_id) REFERENCES formations(id) ON DELETE CASCADE,
                    INDEX (formation_id),
                    INDEX (start_datetime)
                )
            """)

            # Tables pour les Analytics & boucle d'amélioration
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analytics_sessions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL UNIQUE,
                    client_info JSON,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP NULL,
                    completion_status ENUM('completed', 'abandoned', 'in_progress') DEFAULT 'in_progress',
                    qualification_status ENUM('QUALIFIÉ', 'LISTE_D_ATTENTE', 'REFUSÉ', 'pending') DEFAULT 'pending',
                    duration_seconds INT NULL,
                    questions_asked INT DEFAULT 0,
                    formation_interest VARCHAR(255) NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX (start_time),
                    INDEX (completion_status),
                    INDEX (qualification_status)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL,
                    event_type ENUM('question_asked', 'question_answered', 'abandonment', 'completion', 'qualification') NOT NULL,
                    event_data JSON,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES analytics_sessions(session_id) ON DELETE CASCADE,
                    INDEX (session_id),
                    INDEX (event_type),
                    INDEX (timestamp)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS unanswered_questions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    question_text TEXT NOT NULL,
                    frequency INT DEFAULT 1,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    status ENUM('new', 'reviewed', 'added_to_faq', 'ignored') DEFAULT 'new',
                    suggested_answer TEXT NULL,
                    INDEX (frequency),
                    INDEX (status),
                    INDEX (last_seen)
                )
            """)

            self.connection.commit()
            logger.info("Tables créées avec succès")
            return True
            
        except Error as e:
            logger.error(f"Erreur lors de la création des tables: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
    
    def get_formation_availability(self, formation_name: str) -> Dict[str, Any]:
        """Vérifie la disponibilité d'une formation"""
        try:
            cursor = self.connection.cursor(dictionary=True, buffered=True)

            cursor.execute("""
                SELECT f.*,
                       (f.places_max - f.places_reservees) AS places_disponibles,
                       COUNT(s.id) AS nb_sessions_ouvertes
                FROM formations f
                LEFT JOIN sessions_formation s
                  ON f.id = s.formation_id AND s.statut = 'ouverte'
                WHERE f.nom LIKE %s AND f.statut = 'active'
                GROUP BY f.id
                LIMIT 1
            """, (f"%{formation_name}%",))

            result = cursor.fetchone()

            if result:
                return {
                    "formation_id": result["id"],
                    "nom": result["nom"],
                    "places_max": result["places_max"],
                    "places_reservees": result["places_reservees"],
                    "places_disponibles": result["places_disponibles"],
                    "nb_sessions_ouvertes": result["nb_sessions_ouvertes"],
                    "disponible": result["places_disponibles"] > 0,
                    "prix": result["prix"],
                    "duree_jours": result["duree_jours"]
                }
            else:
                return {"disponible": False, "message": "Formation non trouvée"}

        except Error as e:
            logger.error(f"Erreur lors de la vérification de disponibilité: {e}")
            return {"disponible": False, "message": "Erreur de base de données"}
        finally:
            if cursor:
                cursor.close()

    


    
    def get_alternative_formations(self, formation_name: str) -> List[Dict[str, Any]]:
        """Retourne des formations alternatives disponibles"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT f.*, 
                       (f.places_max - f.places_reservees) as places_disponibles
                FROM formations f
                WHERE f.statut = 'active' 
                AND f.nom != %s
                AND (f.places_max - f.places_reservees) > 0
                ORDER BY f.nom
                LIMIT 5
            """, (formation_name,))
            
            return cursor.fetchall()
            
        except Error as e:
            logger.error(f"Erreur lors de la recherche d'alternatives: {e}")
            return []
        finally:
            if cursor:
                cursor.close()

    def list_sessions_by_formation_name(self, formation_name: str) -> List[Dict[str, Any]]:
        """Retourne les créneaux (date/heure) d'une formation, triés par début."""
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT fs.id,
                       fs.start_datetime,
                       fs.end_datetime,
                       fs.label,
                       fs.location,
                       fs.capacity,
                       fs.statut
                FROM formation_sessions fs
                JOIN formations f ON f.id = fs.formation_id
                WHERE f.nom LIKE %s
                ORDER BY fs.start_datetime
            """, (f"%{formation_name}%",))
            return cursor.fetchall()
        except Error as e:
            logger.error(f"Erreur lors de la récupération des sessions: {e}")
            return []
        finally:
            if cursor:
                cursor.close()

    def get_formation_by_name(self, formation_name: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations d'une formation par son nom."""
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM formations WHERE nom LIKE %s LIMIT 1", (f"%{formation_name}%",))
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la formation: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def reserve_place(self, formation_id: int, client_info: Dict[str, Any], 
                     statut_qualification: str, score: int) -> bool:
        """Réserve une place pour un client"""
        try:
            cursor = self.connection.cursor()
            
            # Vérifier qu'il reste des places
            cursor.execute("""
                SELECT places_max, places_reservees 
                FROM formations 
                WHERE id = %s AND statut = 'active'
            """, (formation_id,))
            
            result = cursor.fetchone()
            if not result or result[1] >= result[0]:
                return False
            
            # Insérer l'inscription
            cursor.execute("""
                INSERT INTO inscriptions 
                (client_nom, client_prenom, client_email, client_telephone, 
                 formation_id, statut_qualification, score_qualification)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                client_info.get('nom', ''),
                client_info.get('prenom', ''),
                client_info.get('email', ''),
                client_info.get('numero_telephone', ''),
                formation_id,
                statut_qualification,
                score
            ))
            
            # Mettre à jour le nombre de places réservées
            cursor.execute("""
                UPDATE formations 
                SET places_reservees = places_reservees + 1
                WHERE id = %s
            """, (formation_id,))
            
            self.connection.commit()
            logger.info(f"Place réservée pour {client_info.get('prenom', '')} {client_info.get('nom', '')}")
            return True
            
        except Error as e:
            logger.error(f"Erreur lors de la réservation: {e}")
            self.connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
    
    def populate_sample_data(self):
        """Remplit la base avec des données d'exemple"""
        try:
            cursor = self.connection.cursor()
            
            # Insérer des formations d'exemple
            formations = [
                ("Pâtisserie Française", "Formation complète en pâtisserie française", 15, 5, 1200.00, 5),
                ("Macarons", "Formation spécialisée macarons", 8, 2, 450.00, 2),
                ("Chocolat", "Travail du chocolat et confiserie", 10, 3, 600.00, 3),
                ("Entremets", "Entremets modernes et créatifs", 12, 7, 800.00, 4),
                ("CAP Pâtissier", "Formation CAP complète", 20, 15, 2500.00, 10),
                ("Viennoiseries", "Croissants et viennoiseries", 6, 6, 300.00, 1),  # Complet
            ]
            
            for formation in formations:
                cursor.execute("""
                    INSERT IGNORE INTO formations 
                    (nom, description, places_max, places_reservees, prix, duree_jours)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, formation)
            
            self.connection.commit()
            logger.info("Données d'exemple insérées")
            
        except Error as e:
            logger.error(f"Erreur lors de l'insertion des données: {e}")
        finally:
            if cursor:
                cursor.close()

    # ===== MÉTHODES POUR ANALYTICS & BOUCLE D'AMÉLIORATION =====
    
    def start_analytics_session(self, session_id: str, client_info: dict = None) -> bool:
        """Démarre une session de tracking analytics"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO analytics_sessions (session_id, client_info, start_time)
                VALUES (%s, %s, NOW())
                ON DUPLICATE KEY UPDATE start_time = NOW()
            """, (session_id, json.dumps(client_info) if client_info else None))
            self.connection.commit()
            return True
        except Error as e:
            logger.error(f"Erreur lors du démarrage de session analytics: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def end_analytics_session(self, session_id: str, completion_status: str, 
                            qualification_status: str = None, duration_seconds: int = None) -> bool:
        """Termine une session de tracking analytics"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                UPDATE analytics_sessions 
                SET end_time = NOW(),
                    completion_status = %s,
                    qualification_status = %s,
                    duration_seconds = %s
                WHERE session_id = %s
            """, (completion_status, qualification_status, duration_seconds, session_id))
            self.connection.commit()
            return True
        except Error as e:
            logger.error(f"Erreur lors de la fin de session analytics: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def log_analytics_event(self, session_id: str, event_type: str, event_data: dict = None) -> bool:
        """Enregistre un événement analytics"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO analytics_events (session_id, event_type, event_data)
                VALUES (%s, %s, %s)
            """, (session_id, event_type, json.dumps(event_data) if event_data else None))
            self.connection.commit()
            return True
        except Error as e:
            logger.error(f"Erreur lors de l'enregistrement d'événement analytics: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def log_unanswered_question(self, question_text: str) -> bool:
        """Enregistre une question non répondue"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO unanswered_questions (question_text, frequency)
                VALUES (%s, 1)
                ON DUPLICATE KEY UPDATE 
                    frequency = frequency + 1,
                    last_seen = NOW()
            """, (question_text,))
            self.connection.commit()
            return True
        except Error as e:
            logger.error(f"Erreur lors de l'enregistrement de question non répondue: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def get_analytics_metrics(self, days: int = 30) -> dict:
        """Récupère les métriques analytics des derniers N jours"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Taux de complétion
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_sessions,
                    SUM(CASE WHEN completion_status = 'completed' THEN 1 ELSE 0 END) as completed_sessions,
                    ROUND(SUM(CASE WHEN completion_status = 'completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as completion_rate
                FROM analytics_sessions 
                WHERE start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (days,))
            completion_metrics = cursor.fetchone()

            # Pourcentage de qualifiés
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_completed,
                    SUM(CASE WHEN qualification_status = 'QUALIFIÉ' THEN 1 ELSE 0 END) as qualified_count,
                    ROUND(SUM(CASE WHEN qualification_status = 'QUALIFIÉ' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as qualification_rate
                FROM analytics_sessions 
                WHERE completion_status = 'completed' 
                AND start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (days,))
            qualification_metrics = cursor.fetchone()

            # Temps médian (approximation avec AVG pour MariaDB/MySQL)
            cursor.execute("""
                SELECT 
                    AVG(duration_seconds) as avg_duration_seconds,
                    AVG(duration_seconds) as median_duration_seconds
                FROM analytics_sessions 
                WHERE completion_status = 'completed' 
                AND duration_seconds IS NOT NULL
                AND start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (days,))
            duration_metrics = cursor.fetchone()

            # Top questions non répondues
            cursor.execute("""
                SELECT question_text, frequency, last_seen
                FROM unanswered_questions 
                WHERE status = 'new'
                ORDER BY frequency DESC, last_seen DESC
                LIMIT 10
            """)
            unanswered_questions = cursor.fetchall()

            # Gérer les valeurs None pour éviter les erreurs de division
            avg_seconds = duration_metrics.get('avg_duration_seconds') or 0
            median_seconds = duration_metrics.get('median_duration_seconds') or 0
            
            return {
                'completion_rate': completion_metrics.get('completion_rate', 0),
                'total_sessions': completion_metrics.get('total_sessions', 0),
                'completed_sessions': completion_metrics.get('completed_sessions', 0),
                'qualification_rate': qualification_metrics.get('qualification_rate', 0),
                'qualified_count': qualification_metrics.get('qualified_count', 0),
                'avg_duration_minutes': round(avg_seconds / 60, 1) if avg_seconds > 0 else 0,
                'median_duration_minutes': round(median_seconds / 60, 1) if median_seconds > 0 else 0,
                'top_unanswered_questions': unanswered_questions
            }

        except Error as e:
            logger.error(f"Erreur lors de la récupération des métriques: {e}")
            return {}
        finally:
            if cursor:
                cursor.close()

def get_database_service() -> DatabaseService:
        """Retourne une instance du service de base de données"""
        return DatabaseService()

