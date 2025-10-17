import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, Optional
from email_config import get_email_config
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.config = get_email_config()
    
    def send_inscription_email(self, client_info: Dict[str, Any], formation_details: str) -> bool:
        """
        Envoie un email à l'équipe avec les informations du client qui souhaite s'inscrire
        
        Args:
            client_info: Informations du client (nom, prénom, etc.)
            formation_details: Détails de la formation demandée
            
        Returns:
            bool: True si l'email a été envoyé avec succès, False sinon
        """
        try:
            # Création du message
            msg = MIMEMultipart()
            msg['From'] = self.config["email_user"]
            msg['To'] = self.config["team_email"]
            msg['Subject'] = f"Nouvelle demande d'inscription - {client_info.get('prenom', '')} {client_info.get('nom', '')}"
            
            # Corps du message
            body = self._create_email_body(client_info, formation_details)
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Connexion et envoi
            server = smtplib.SMTP(self.config["smtp_server"], self.config["smtp_port"])
            
            if self.config["use_tls"]:
                server.starttls()
            
            server.login(self.config["email_user"], self.config["email_password"])
            text = msg.as_string()
            server.sendmail(self.config["email_user"], self.config["team_email"], text)
            server.quit()
            
            logger.info(f"Email d'inscription envoyé pour {client_info.get('prenom', '')} {client_info.get('nom', '')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'email: {str(e)}")
            return False

    def _create_email_body(self, client_info: Dict[str, Any], formation_details: str) -> str:
            """Crée le corps de l'email avec les informations du client"""
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            formation_interesse = "Non spécifiée"
            statut_qualification = "Non évalué"
            creneau = "Non précisé"

            # Parser les informations depuis formation_details
            lines = formation_details.split('\n')
            for line in lines:
                if "Formation demandée:" in line:
                    formation_interesse = line.split("Formation demandée:")[1].strip()
                elif "Statut:" in line:
                    statut_qualification = line.split("Statut:")[1].strip()
                elif "CRÉNEAU:" in line or "CRENEAU:" in line:
                    creneau = line.split(":")[1].strip()

            body = f"""
        NOUVELLE DEMANDE D'INSCRIPTION À UNE FORMATION

        Date et heure: {timestamp}

        INFORMATIONS CLIENT:
        - Nom: {client_info.get('nom', 'Non renseigné')}
        - Prénom: {client_info.get('prenom', 'Non renseigné')}
        - Téléphone: {client_info.get('numero_telephone', 'Non renseigné')}
        - Âge: {client_info.get('age', 'Non renseigné')}
        - Statut: {client_info.get('statut', 'Non renseigné')}
        - CPF actif: {client_info.get('cpf', 'Non renseigné')}
        - Ville: {client_info.get('ville', 'Non renseigné')}
        - Préférence: {client_info.get('preference', 'Non renseigné')}
        - Budget: {client_info.get('budget', 'Non renseigné')}€

        FORMATION CHOISIE:
        {formation_interesse}

        CRÉNEAU SÉLECTIONNÉ:
        {creneau}

        STATUT DE QUALIFICATION:
        {statut_qualification}

        ---
        Cet email a été généré automatiquement par le système Dream Pastry.
        Veuillez contacter le client dans les plus brefs délais.
            """
            return body

def send_inscription_notification(client_info: Dict[str, Any], formation_details: str) -> bool:
    """
    Fonction utilitaire pour envoyer une notification d'inscription
    
    Args:
        client_info: Informations du client
        formation_details: Détails de la formation
        
    Returns:
        bool: True si l'email a été envoyé avec succès
    """
    email_service = EmailService()
    return email_service.send_inscription_email(client_info, formation_details)



def send_client_notification(client_info: dict, status: str, formation_details: str = ""):
    """
    Envoie un email de notification au client selon son statut de qualification
    
    Args:
        client_info: Informations du client
        status: Statut de qualification (QUALIFIÉ, LISTE_D_ATTENTE, REFUSÉ)
        formation_details: Détails de la formation et du créneau choisi
    """
    try:
     
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = "hajarelaouni43@gmail.com"  
        sender_password = "rtsa ynab dwfi leso"  
        
        
       
        recipient_email = client_info.get('email', '')
        if not recipient_email:
            print("❌ Aucun email client fourni")
            return False
        
        
        if status == "QUALIFIÉ":
            subject = "🎉 Félicitations ! Votre qualification Dream Pastry"
            body = f"""
Bonjour {client_info.get('prenom', '')} {client_info.get('nom', '')},

🎉 **FÉLICITATIONS !**

Votre candidature pour nos formations Dream Pastry a été acceptée !

{formation_details}

📞 **Prochaines étapes :**
Notre équipe vous contactera dans les 24 heures pour :
• Finaliser votre inscription
• Vous expliquer les modalités de paiement
• Planifier votre formation
• Répondre à toutes vos questions

Nous avons hâte de vous accueillir dans notre école !

Cordialement,
L'équipe Dream Pastry
📧 contact@dreampastry.fr
📞 01 23 45 67 89
            """
            
        elif status == "LISTE_D_ATTENTE":
            subject = "⏳ Votre candidature Dream Pastry - Liste d'attente"
            body = f"""
Bonjour {client_info.get('prenom', '')} {client_info.get('nom', '')},

⏳ **VOTRE CANDIDATURE EST EN COURS D'ÉTUDE**

Votre profil nous intéresse ! Votre candidature est actuellement en liste d'attente.

{formation_details}

📞 **Prochaines étapes :**
Notre équipe vous contactera sous 48 heures pour :
• Étudier votre dossier plus en détail
• Vous proposer des alternatives si nécessaire
• Vous informer des prochaines sessions disponibles

Merci pour votre patience !

Cordialement,
L'équipe Dream Pastry
📧 contact@dreampastry.fr
📞 01 23 45 67 89
            """
            
        else:  # REFUSÉ
            subject = "📋 Votre candidature Dream Pastry"
            body = f"""
Bonjour {client_info.get('prenom', '')} {client_info.get('nom', '')},

📋 **VOTRE CANDIDATURE**

Merci pour votre intérêt pour nos formations Dream Pastry.

Après étude de votre dossier, votre profil ne correspond pas actuellement à nos critères d'admission.

📞 **Alternatives possibles :**
Notre équipe vous contactera pour :
• Vous proposer d'autres formations adaptées à votre profil
• Vous informer des prochaines sessions
• Vous conseiller sur les prérequis nécessaires

Nous restons à votre disposition !

Cordialement,
L'équipe Dream Pastry
📧 contact@dreampastry.fr
📞 01 23 45 67 89
            """
        
       
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        print(f"✅ Email envoyé au client {recipient_email} - Statut: {status}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur envoi email client: {e}")
        return False
