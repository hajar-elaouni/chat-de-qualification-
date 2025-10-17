from operator import itemgetter
import streamlit as st
import uuid
import time
from datetime import datetime

from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.messages import get_buffer_string
from langchain_core.prompts import format_document
from langchain.prompts.prompt import PromptTemplate
import google.generativeai as genai
from email_service import send_client_notification

condense_question = """Given the following conversation and a follow-up question, rephrase the follow-up question to be a standalone question.

Chat History:
{chat_history}

Follow Up Input: {question}
Standalone question:"""
CONDENSE_QUESTION_PROMPT = PromptTemplate.from_template(condense_question)

answer = """
### Instruction:
Tu es un assistant Dream Pastry spécialisé en formations de pâtisserie.
- Tu réponds et fais des recommandations UNIQUEMENT à partir des documents fournis ci-dessous (PDFs indexés).
- Si l'information n'est pas présente dans ces documents, dis clairement: "Je ne peux pas répondre avec certitude sur la base des documents disponibles."
- N'invente JAMAIS de chiffres, dates, durées, tarifs, conditions ou contenus. Pas de connaissances externes.
- Réponds en français, de façon claire et concise.
- Lorsque tu peux répondre, fournis les sources (nom de document et page) issues du contexte. Si tu ne peux pas répondre, n'affiche aucune source.
- Les recommandations/orientations doivent être justifiées par des extraits présents dans les documents (et sourcées).

## Recherche (extraits des documents):
{context}

## Question:
{question}
"""

ANSWER_PROMPT = ChatPromptTemplate.from_template(answer)

DEFAULT_DOCUMENT_PROMPT = PromptTemplate.from_template(
    template="Source Document: {source}, Page {page}:\n{page_content}"
)


def _combine_documents(
    docs, document_prompt=DEFAULT_DOCUMENT_PROMPT, document_separator="\n\n"
):
    doc_strings = [format_document(doc, document_prompt) for doc in docs]
    return document_separator.join(doc_strings)


memory = ConversationBufferMemory(return_messages=True, output_key="answer", input_key="question")


def getStreamingChain(question: str, memory, llm, db):
    retriever = db.as_retriever(search_kwargs={"k": 10})
    loaded_memory = RunnablePassthrough.assign(
        chat_history=RunnableLambda(
            lambda x: "\n".join(
                [f"{item['role']}: {item['content']}" for item in x["memory"]]
            )
        ),
    )

    standalone_question = {
        "standalone_question": {
            "question": lambda x: x["question"],
            "chat_history": lambda x: x["chat_history"],
        }
        | CONDENSE_QUESTION_PROMPT
        | llm
        | (lambda x: x.content if hasattr(x, "content") else x)
    }

    retrieved_documents = {
        "docs": itemgetter("standalone_question") | retriever,
        "question": lambda x: x["standalone_question"],
    }

    final_inputs = {
        "context": lambda x: _combine_documents(x["docs"]),
        "question": itemgetter("question"),
    }

    answer = final_inputs | ANSWER_PROMPT | llm

    final_chain = loaded_memory | standalone_question | retrieved_documents | answer

    return final_chain.stream({"question": question, "memory": memory})


import json
import re
from email_service import send_inscription_notification

FALLBACK_PATH = "Research/fallback_answers.json"
with open(FALLBACK_PATH, "r", encoding="utf-8") as f:
    fallback_answers = json.load(f)

# ===== FONCTIONS POUR ANALYTICS & TRACKING =====

def get_or_create_session_id() -> str:
    """Génère ou récupère un ID de session unique pour le tracking"""
    if "analytics_session_id" not in st.session_state:
        st.session_state["analytics_session_id"] = str(uuid.uuid4())
        st.session_state["analytics_start_time"] = time.time()
    return st.session_state["analytics_session_id"]

def start_analytics_tracking(client_info: dict = None) -> str:
    """Démarre le tracking analytics d'une session"""
    session_id = get_or_create_session_id()
    
    try:
        from database_service import get_database_service
        db = get_database_service()
        if db.connect():
            db.start_analytics_session(session_id, client_info)
            db.log_analytics_event(session_id, "question_asked", {
                "question": "Début de session de qualification",
                "timestamp": datetime.now().isoformat()
            })
            db.disconnect()
    except Exception as e:
        print(f"Erreur lors du démarrage du tracking analytics: {e}")
    
    return session_id

def log_analytics_event(event_type: str, event_data: dict = None):
    """Enregistre un événement analytics"""
    try:
        session_id = get_or_create_session_id()
        from database_service import get_database_service
        db = get_database_service()
        if db.connect():
            db.log_analytics_event(session_id, event_type, event_data)
            db.disconnect()
    except Exception as e:
        print(f"Erreur lors de l'enregistrement d'événement analytics: {e}")

def end_analytics_tracking(completion_status: str, qualification_status: str = None):
    """Termine le tracking analytics d'une session"""
    try:
        session_id = get_or_create_session_id()
        duration_seconds = None
        
        if "analytics_start_time" in st.session_state:
            duration_seconds = int(time.time() - st.session_state["analytics_start_time"])
        
        from database_service import get_database_service
        db = get_database_service()
        if db.connect():
            db.end_analytics_session(session_id, completion_status, qualification_status, duration_seconds)
            db.disconnect()
        
        # Nettoyer la session
        if "analytics_session_id" in st.session_state:
            del st.session_state["analytics_session_id"]
        if "analytics_start_time" in st.session_state:
            del st.session_state["analytics_start_time"]
            
    except Exception as e:
        print(f"Erreur lors de la fin du tracking analytics: {e}")

def track_unanswered_question(question: str):
    """Enregistre une question non répondue pour enrichir la FAQ"""
    try:
        from database_service import get_database_service
        db = get_database_service()
        if db.connect():
            db.log_unanswered_question(question)
            db.disconnect()
    except Exception as e:
        print(f"Erreur lors de l'enregistrement de question non répondue: {e}")


def get_fallback_answer(question):
    # Recherche simple par mot-clé ou question exacte
    for key, value in fallback_answers.items():
        if key.lower() in question.lower():
            return value
    
    # Si aucune réponse trouvée, tracker la question non répondue
    track_unanswered_question(question)
    return None

def detect_inscription_intent(question: str) -> bool:
    """
    Détecte si le client exprime une intention d'inscription à une formation
    
    Args:
        question: La question du client
        
    Returns:
        bool: True si une intention d'inscription est détectée
    """
    # Mots-clés et expressions indiquant une intention d'inscription
    inscription_keywords = [
        r'\binscrire\b', r'\binscription\b', r'\bs\'inscrire\b',
        r'\bparticiper\b', r'\bparticiper à\b', r'\bsuivre\b',
        r'\bformation\b.*\bintéressé\b', r'\bintéressé\b.*\bformation\b',
        r'\bje veux\b.*\bformation\b', r'\bje souhaite\b.*\bformation\b',
        r'\bje voudrais\b.*\bformation\b', r'\bje désire\b.*\bformation\b',
        r'\bformation\b.*\bpour moi\b', r'\bformation\b.*\bmoi\b',
        r'\bcomment faire\b.*\binscription\b', r'\bcomment s\'inscrire\b',
        r'\bprocédure\b.*\binscription\b', r'\bétapes\b.*\binscription\b',
        r'\bmodalités\b.*\binscription\b', r'\bconditions\b.*\binscription\b'
    ]
    
    question_lower = question.lower()
    
    for pattern in inscription_keywords:
        if re.search(pattern, question_lower):
            return True
    
    return False

from datetime import datetime

def _format_session(sess: dict) -> str:
    sd = datetime.strptime(str(sess["start_datetime"]), "%Y-%m-%d %H:%M:%S")
    ed = datetime.strptime(str(sess["end_datetime"]), "%Y-%m-%d %H:%M:%S")
    label = f" ({sess['label']})" if sess.get("label") else ""
    loc = f" - {sess['location']}" if sess.get("location") else ""
    return f"{sd.strftime('%d/%m %H:%M')} → {ed.strftime('%H:%M')}{label}{loc}"

def generate_qualification_questions(client_info: dict, formation_choisie: str = None) -> list[str]:
    questions = []

    if not formation_choisie:
        questions.append("Quelle formation vous intéresse le plus ? (Pâtisserie française/Macaron/Chocolat/Entremet/CAP Pâtissier/Autre)")
    else:
        from database_service import get_database_service
        db = get_database_service()
        if db.connect():
            sessions = db.list_sessions_by_formation_name(formation_choisie)
            db.disconnect()

            if sessions:
                # Mémoriser les options pour la suite (validation de la réponse utilisateur)
                # Note: cette fonction est rarement utilisée dans le flux actuel, mais on
                # s'assure d'écrire dans l'état global Streamlit si elle est appelée.
                st.session_state["sessions_options"] = sessions
                st.session_state["slot_required"] = True
                # Construire la question avec options numérotées
                lines = [f"Créneaux disponibles pour « {formation_choisie} »:"]
                for i, s in enumerate(sessions, 1):
                    lines.append(f"{i}. {_format_session(s)}")
                lines.append("Quel créneau vous convient ? Répondez par le numéro (ou « aucun » si indisponible).")
                questions.append("\n".join(lines))
            else:
                st.session_state["slot_required"] = False
                questions.append("Aucun créneau n’est disponible actuellement pour cette formation. Souhaitez‑vous une alerte quand un créneau s’ouvre ? (Oui/Non)")
        else:
            questions.append("Problème de connexion. Indiquez tout de même vos disponibilités (jours/heures).")

    # — Questions communes (inchangées) —
    questions.append("Avez-vous déjà une expérience en pâtisserie ? (Débutant/Intermédiaire/Avancé)")
    questions.append("Quel est votre objectif principal ? (Reconversion professionnelle/Perfectionnement/Passion personnelle)")

    age = client_info.get('age', 0)
    statut = client_info.get('statut', '')
    budget = client_info.get('budget', 0)
    cpf_status = client_info.get('cpf', '')
    
    if statut == "Demandeur d'emploi":
        questions.append("Depuis combien de temps êtes-vous demandeur d'emploi ?")
        questions.append("Avez-vous déjà suivi des formations professionnelles ?")
    elif statut == "Salarié":
        questions.append("Votre employeur est-il favorable à votre formation ?")
        questions.append("Pouvez-vous prendre un congé formation ?")
    elif statut == "Indépendant":
        questions.append("Combien d'heures par semaine pouvez-vous consacrer à la formation ?")
        questions.append("Votre activité actuelle vous permet-elle de suivre une formation ?")
    
    if cpf_status == "Non" or budget < 1000:
        questions.append("Comment envisagez-vous de financer cette formation ?")
        questions.append("Avez-vous des aides possibles (Pôle Emploi, OPCO, autres) ?")
        questions.append("Votre entreprise peut-elle faire une demande de prise en charge OPCO ?")
    
    questions.append("Qu'est-ce qui vous motive le plus dans l'apprentissage de la pâtisserie ?")
    questions.append("Avez-vous des contraintes particulières (handicap, transport, etc.) ?")
    
    return questions





def evaluate_qualification_score(client_info: dict, answers: dict) -> tuple[str, int, str]:
    """
    Évalue le score de qualification du client en utilisant Gemini
    
    Args:
        client_info: Informations du client
        answers: Réponses aux questions de qualification
        
    Returns:
        tuple: (statut_qualification, score, justification)
    """
    
    # Configure l'API Gemini
    API_KEY = "AIzaSyALngayFjP-pXf02p-gKj0lWWtWAHkyWMo" 
    genai.configure(api_key=API_KEY)
    
    # Construire le prompt avec toutes les informations
    prompt = f"""
    Tu es un expert en qualification de prospects pour Dream Pastry, une école de pâtisserie.

    **INFORMATIONS CLIENT:**
    - Nom: {client_info.get('nom', 'Non renseigné')}
    - Prénom: {client_info.get('prenom', 'Non renseigné')}
    - Âge: {client_info.get('age', 'Non renseigné')}
    - Statut: {client_info.get('statut', 'Non renseigné')}
    - CPF actif: {client_info.get('cpf', 'Non renseigné')}
    - Ville: {client_info.get('ville', 'Non renseigné')}
    - Préférence: {client_info.get('preference', 'Non renseigné')}
    - Budget: {client_info.get('budget', 'Non renseigné')}€

    **RÉPONSES AUX QUESTIONS DE QUALIFICATION:**
    """
    
    # Ajouter toutes les réponses
    for q, a in answers.items():
        prompt += f"- {q}: {a}\n"
        
    prompt += f"""

    **CRITÈRES D'ÉVALUATION:**

    1. **ÂGE** (20 points max):
    - 16-17 ans: non éligible (0 pts)
    - 18-55 ans: optimal (20 pts)
    - 56-65 ans: acceptable (10 pts)

    2. **STATUT** (20 points max):
    - Demandeur d'emploi: priorité (20 pts)
    - Salarié: possibilité (15 pts)
    - Indépendant: contraintes (10 pts)
    - Autre: vérification (5 pts)

    3. **BUDGET** (20 points max):
    - ≥1000€: suffisant (20 pts)
    - ≥500€: correct (15 pts)
    - ≥200€: limité (10 pts)
    - <200€: insuffisant (5 pts)

    4. **CPF** (20 points max):
    - Actif: facilité (20 pts)
    - Inactif: alternatives (10 pts) [si il ne peux pas faire une prise en charge]

    5. **EXPÉRIENCE PÂTISSERIE** (10 points max):
    - Débutant: idéal (10 pts)
    - Intermédiaire: bon (7 pts)
    - Avancé: correct (5 pts)


    **CLASSIFICATION FINALE:**
    - QUALIFIÉ: score ≥80 (tous critères respectés)
    - LISTE D'ATTENTE: score 60-79 (profil intéressant, à étudier)
    - REFUSÉ: score <60 (critères non respectés)

    **INSTRUCTIONS:**
    1. Calcule le score total (sur 100)
    2. Détermine la catégorie finale (QUALIFIÉ/LISTE D'ATTENTE/REFUSÉ)
    3. Justifie ta décision point par point
    4. Sois professionnel, informatif, sans promesse sur le financement CPF
    5. Réponds en français, style concis et poli

    **FORMAT DE RÉPONSE ATTENDU:**

    """

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        
        # Parser la réponse de Gemini
        response_text = response.text
        
        # Extraire la catégorie
        if "QUALIFIÉ" in response_text:
            statut_qualification = "QUALIFIÉ"
        elif "LISTE D'ATTENTE" in response_text:
            statut_qualification = "LISTE D'ATTENTE"
        else:
            statut_qualification = "REFUSÉ"
        
        # Extraire le score (cherche "SCORE: X/100")
        import re
        score_match = re.search(r'SCORE:\s*(\d+)/100', response_text)
        score = int(score_match.group(1)) if score_match else 0
        
        # La justification est le texte complet
        justification_finale = response_text
    
        return statut_qualification, score, justification_finale
        
    except Exception as e:
        print(f"Erreur lors de l'appel à Gemini: {e}")
        # Fallback en cas d'erreur
        return "REFUSÉ", 0, f"Erreur lors de l'évaluation: {str(e)}"


def check_client_eligibility(client_info: dict) -> tuple[bool, list[str], str]:
    """
    Vérifie l'éligibilité du client selon différents critères
    
    Args:
        client_info: Informations du client
        
    Returns:
        Tuple: (est_eligible, criteres_non_respectes, message_explicatif)
    """
    criteres_non_respectes = []
    messages_explicatifs = []
    
    # Conditions CPF
    age_min = 16
    age_max = 65
    statuts_eligibles = ["Salarié", "Demandeur d'emploi", "Indépendant"]
    budget_min = 500
    
    # Vérification de l'âge
    age = client_info.get('age', 0)
    if age < age_min:
        criteres_non_respectes.append("âge minimum")
        messages_explicatifs.append(f"L'âge minimum requis est de {age_min} ans")
    elif age > age_max:
        criteres_non_respectes.append("âge maximum")
        messages_explicatifs.append(f"L'âge maximum pour le CPF est de {age_max} ans")
    
    # Vérification du statut
    statut = client_info.get('statut', '')
    if statut not in statuts_eligibles:
        criteres_non_respectes.append("statut professionnel")
        messages_explicatifs.append(f"Le statut '{statut}' peut limiter les possibilités de financement")
    
    # Vérification du budget
    budget = client_info.get('budget', 0)
    if budget < budget_min:
        criteres_non_respectes.append("budget insuffisant")
        messages_explicatifs.append(f"Un budget minimum de {budget_min}€ est recommandé pour les formations")
    
    # Vérification du CPF
    cpf_status = client_info.get('cpf', '')
    if cpf_status == "Non":
        criteres_non_respectes.append("CPF inactif")
        messages_explicatifs.append("Le CPF n'est pas actif - possibilités de financement alternatives à explorer")
   
    
    est_eligible = len(criteres_non_respectes) == 0
    message_explicatif = " ; ".join(messages_explicatifs) if messages_explicatifs else "Tous les critères sont respectés"
    
    return est_eligible, criteres_non_respectes, message_explicatif

def generate_cpf_discussion(client_info: dict, criteres_non_respectes: list[str]) -> str:
    """
    Génère une discussion informative sur le CPF avec garde-fous
    
    Args:
        client_info: Informations du client
        criteres_non_respectes: Liste des critères non respectés
        
    Returns:
        str: Message de discussion CPF
    """
    cpf_status = client_info.get('cpf', '')
    statut = client_info.get('statut', '')
    
    discussion_parts = []
    
    # Introduction informative
    discussion_parts.append("💡 **Informations sur le financement CPF :**")
    
    # Discussion selon le statut CPF
    if cpf_status == "Oui":
        discussion_parts.append("✅ Votre CPF est actif, ce qui ouvre des possibilités de financement.")
        discussion_parts.append("📋 **Possibilités de prise en charge selon votre profil :**")
        
        if statut == "Salarié":
            discussion_parts.append("• En tant que salarié, vous pouvez mobiliser votre CPF pour une formation")
            discussion_parts.append("• Possibilité de congé formation (avec accord employeur)")
            discussion_parts.append("• Prise en charge OPCO possible pour certaines formations")
            discussion_parts.append("• Financement partiel ou total selon les conditions")
        
        elif statut == "Demandeur d'emploi":
            discussion_parts.append("• En tant que demandeur d'emploi, vous avez accès à votre CPF")
            discussion_parts.append("• Possibilité de formation intensive")
            discussion_parts.append("• Financement facilité par Pôle Emploi")
        
        elif statut == "Indépendant":
            discussion_parts.append("• En tant qu'indépendant, vous pouvez utiliser votre CPF")
            discussion_parts.append("• Formation possible pendant ou en dehors de votre activité")
            discussion_parts.append("• Adaptation aux contraintes de votre activité")
        
        else:
            discussion_parts.append("• Votre statut peut offrir des possibilités spécifiques")
            discussion_parts.append("• À vérifier selon votre situation particulière")
    
    elif cpf_status == "Non":
        discussion_parts.append("⚠️ Votre CPF n'est pas actif selon vos informations.")
        discussion_parts.append("📋 **Alternatives de financement possibles :**")
        discussion_parts.append("• Financement personnel")
        discussion_parts.append("• Aide de Pôle Emploi (sous conditions d'éligibilité)")
        discussion_parts.append("• Prise en charge OPCO (si salarié et formation éligible)")
        discussion_parts.append("• Formation en alternance (sous conditions)")
        discussion_parts.append("• Autres dispositifs selon votre situation")
    
    # Garde-fous et avertissements
    discussion_parts.append("\n⚠️ **IMPORTANT - GARDE-FOUS OBLIGATOIRES :**")
    discussion_parts.append("• Les informations données sont à titre INFORMATIF UNIQUEMENT")
    discussion_parts.append("• Aucune promesse de financement n'est garantie")
    discussion_parts.append("• Chaque situation est unique et nécessite une analyse personnalisée")
    discussion_parts.append("• Les conditions de financement peuvent varier selon votre profil")
    discussion_parts.append("• Une étude approfondie sera nécessaire pour confirmer l'éligibilité")
    discussion_parts.append("• Les conditions CPF sont soumises à la réglementation en vigueur")
    discussion_parts.append("• Consultez les conditions officielles sur moncompteformation.gouv.fr")
    
    # Message sur les critères non respectés
    if criteres_non_respectes:
        discussion_parts.append(f"\n🔍 **Points d'attention identifiés :**")
        for critere in criteres_non_respectes:
            discussion_parts.append(f"• {critere.replace('_', ' ').title()}")
        discussion_parts.append("• Ces points seront étudiés lors de l'entretien personnalisé")
    
    # Conclusion
    discussion_parts.append("\n📞 **Prochaines étapes :**")
    discussion_parts.append("• Notre équipe vous contactera pour un entretien personnalisé")
    discussion_parts.append("• Analyse détaillée de votre situation et de vos besoins")
    discussion_parts.append("• Proposition de solutions de financement adaptées")
    discussion_parts.append("• Accompagnement dans les démarches administratives")
    
    return "\n".join(discussion_parts)


def detect_formation_interest(question: str, chat_history: list = None) -> str:
    """
    Détecte la formation spécifique qui intéresse le client
    
    Args:
        question: Question du client
        chat_history: Historique de la conversation
        
    Returns:
        str: Formation détectée ou "Non spécifiée"
    """
    # Liste des formations Dream Pastry
    formations = [
        "pâtisserie française", "pâtisserie", "capcakes", "cookies", "macarons", "Cap Blanc",
        "croissant", "pain", "viennoiserie", "chocolat", "entremet", "fraisier", "Tablette chocolat Dubai",
        "layercake", "wedding cake", "trompe l'oeil", "mignardise", "tartelette", 
        "cap pâtissier", "formation pâtisserie", "apprentissage pâtisserie"
    ]
    
    # Recherche dans la question actuelle
    question_lower = question.lower()
    for formation in formations:
        if formation in question_lower:
            return formation.title()
    
    # Recherche dans l'historique de chat si disponible
    if chat_history:
        for message in chat_history:
            if isinstance(message, dict) and message.get("role") == "user":
                content = message.get("content", "").lower()
                for formation in formations:
                    if formation in content:
                        return formation.title()
    
    return "Non spécifiée"

def process_inscription_request(client_info: dict, question: str, response: str) -> tuple[str, bool]:
    """
    Traite une demande d'inscription et envoie un email à l'équipe
    
    Args:
        client_info: Informations du client
        question: Question du client
        response: Réponse générée par le LLM
        
    Returns:
        tuple: (message_final, email_envoye)
    """
    if detect_inscription_intent(question):
        # Préparer les détails de la formation
        formation_details = f"Question du client: {question}\n\nRéponse fournie: {response}"
        
        # Envoyer l'email à l'équipe
        email_sent = send_inscription_notification(client_info, formation_details)
        
        if email_sent:
            additional_message = "\n\n📧 **Votre demande d'inscription a été transmise à notre équipe qui vous contactera dans les plus brefs délais.**"
            return response + additional_message, True
        else:
            additional_message = "\n\n⚠️ **Votre demande d'inscription a été notée. Notre équipe vous contactera prochainement.**"
            return response + additional_message, False
    
    return response, False

def getChatChain(llm, db):
    retriever = db.as_retriever(search_kwargs={"k": 10})

    loaded_memory = RunnablePassthrough.assign(
        chat_history=RunnableLambda(memory.load_memory_variables)
        | itemgetter("history"),
    )

    standalone_question = {
        "standalone_question": {
            "question": lambda x: x["question"],
            "chat_history": lambda x: get_buffer_string(x["chat_history"]),
        }
        | CONDENSE_QUESTION_PROMPT
        | llm
        | (lambda x: x.content if hasattr(x, "content") else x)
    }

    # Now we retrieve the documents
    retrieved_documents = {
        "docs": itemgetter("standalone_question") | retriever,
        "question": lambda x: x["standalone_question"],
    }

    # Now we construct the inputs for the final prompt
    final_inputs = {
        "context": lambda x: _combine_documents(x["docs"]),
        "question": itemgetter("question"),
    }

    # And finally, we do the part that returns the answers
    answer = {
        "answer": final_inputs
        | ANSWER_PROMPT
        | llm.with_config(callbacks=[StreamingStdOutCallbackHandler()]),
        "docs": itemgetter("docs"),
    }

    final_chain = loaded_memory | standalone_question | retrieved_documents | answer

    def chat(question: str):
        inputs = {"question": question}
        result = final_chain.invoke(inputs)
        memory.save_context(inputs, {"answer": result["answer"].content if hasattr(result["answer"], "content") else result["answer"]})

    return chat

def process_qualification_flow(client_info: dict, question: str, response: str, session_state: dict) -> tuple[str, bool, bool]:
    """
    Traite le flux de qualification du client avec vérification des places
    """
    from datetime import datetime
    from database_service import get_database_service

    def _format_session(sess: dict) -> str:
        sd = datetime.strptime(str(sess["start_datetime"]), "%Y-%m-%d %H:%M:%S")
        ed = datetime.strptime(str(sess["end_datetime"]), "%Y-%m-%d %H:%M:%S")
        label = f" ({sess['label']})" if sess.get("label") else ""
        loc = f" - {sess['location']}" if sess.get("location") else ""
        return f"{sd.strftime('%d/%m %H:%M')} → {ed.strftime('%H:%M')}{label}{loc}"

    # Init état
    if "qualification_in_progress" not in session_state:
        session_state["qualification_in_progress"] = False
        session_state["qualification_questions"] = []
        session_state["qualification_answers"] = {}
        session_state["current_question_index"] = 0
        session_state["sessions_options"] = []
        session_state["selected_session_id"] = None
        session_state["formation_choisie"] = None
        session_state["slot_required"] = False
        session_state["refuse_no_slot"] = False

    # Démarrage du flux
    if not session_state["qualification_in_progress"]:
        session_state["qualification_in_progress"] = True

        # Analytics start
        start_analytics_tracking(client_info)
        log_analytics_event("qualification", {"action": "start", "client_info": client_info})

        # 1ère question: formation
        questions = [
            "Quelle formation vous intéresse le plus ? (Pâtisserie française/Macaron/Chocolat/Entremet/CAP Pâtissier/Autre)"
        ]

        # Questions communes
        questions.append("Avez-vous déjà une expérience en pâtisserie ? (Débutant/Intermédiaire/Avancé)")
        questions.append("Quel est votre objectif principal ? (Reconversion professionnelle/Perfectionnement/Passion personnelle)")

        statut = client_info.get('statut', '')
        budget = client_info.get('budget', 0)
        cpf_status = client_info.get('cpf', '')
        if statut == "Demandeur d'emploi":
            questions.append("Depuis combien de temps êtes-vous demandeur d'emploi ?")
            questions.append("Avez-vous déjà suivi des formations professionnelles ?")
        elif statut == "Salarié":
            questions.append("Votre employeur est-il favorable à votre formation ?")
            questions.append("Pouvez-vous prendre un congé formation ?")
        elif statut == "Indépendant":
            questions.append("Combien d'heures par semaine pouvez-vous consacrer à la formation ?")
            questions.append("Votre activité actuelle vous permet-elle de suivre une formation ?")
        if cpf_status == "Non" or budget < 1000:
            questions.append("Comment envisagez-vous de financer cette formation ?")
            questions.append("Avez-vous des aides possibles (Pôle Emploi, OPCO, autres) ?")
            questions.append("Votre entreprise peut-elle faire une demande de prise en charge OPCO ?")
        questions.append("Qu'est-ce qui vous motive le plus dans l'apprentissage de la pâtisserie ?")
        questions.append("Avez-vous des contraintes particulières (handicap, transport, etc.) ?")

        session_state["qualification_questions"] = questions

        qualification_message = f"""
🎯 **PROCESSUS DE QUALIFICATION**

Merci pour votre intérêt ! Pour mieux vous orienter, nous allons vous poser quelques questions de qualification.

**Question 1/{len(questions)}:** {questions[0]}

Veuillez répondre à cette question pour continuer le processus.
"""
        return qualification_message, False, False

    # Flux en cours
    current_index = session_state["current_question_index"]
    questions = session_state["qualification_questions"]
    current_q_text = questions[current_index]

    # Cas Q1: formation => injecter question de créneaux
    if current_index == 0:
        session_state["formation_choisie"] = question.strip()
        db = get_database_service()
        if db.connect():
            sessions = db.list_sessions_by_formation_name(session_state["formation_choisie"])
            db.disconnect()
        else:
            sessions = []

        if sessions:
            session_state["sessions_options"] = sessions
            session_state["slot_required"] = True
            lines = [f"Créneaux disponibles pour « {session_state['formation_choisie']} »:"]
            for i, s in enumerate(sessions, 1):
                lines.append(f"{i}. {_format_session(s)}")
            lines.append("Quel créneau vous convient ? Répondez par le numéro (ou « aucun » si indisponible).")
            questions.insert(1, "\n".join(lines))
        else:
            session_state["slot_required"] = False
            questions.insert(1, "Aucun créneau n’est disponible pour cette formation. Souhaitez‑vous une alerte quand un créneau s’ouvre ? (Oui/Non)")

        # Sauvegarder la réponse de la Q1
        session_state["qualification_answers"]["formation"] = session_state["formation_choisie"]

        # Afficher la Q2 (créneaux)
        session_state["current_question_index"] = 1
        next_question = questions[1]
        next_message = f"""
Merci pour votre réponse !

**Question 2/{len(questions)}:** {next_question}

Veuillez répondre pour continuer.
"""
        return next_message, False, False

    # Cas Q2: validation choix de créneau
    if "Créneaux disponibles pour" in current_q_text:
        user_raw = question.strip().lower()
        if user_raw == "aucun":
            session_state["selected_session_id"] = None
            session_state["qualification_answers"]["creneau_selection"] = "aucun"
            if session_state.get("slot_required", False):
                session_state["refuse_no_slot"] = True
        else:
            try:
                idx = int(user_raw)
                options = session_state.get("sessions_options", [])
                if 1 <= idx <= len(options):
                    chosen = options[idx - 1]
                    session_state["selected_session_id"] = chosen["id"]
                    session_state["qualification_answers"]["creneau_selection"] = str(idx)
                else:
                    return "Veuillez répondre par un numéro valide parmi les options listées, ou « aucun ». Réessayez.", False, False
            except ValueError:
                return "Veuillez répondre par un numéro (ex: 1) ou « aucun ». Réessayez.", False, False
    else:
        # Stockage générique
        question_key = current_q_text.split(":")[0].lower().replace(" ", "_")
        session_state["qualification_answers"][question_key] = question

        # Analytics: log question answered
        log_analytics_event("question_answered", {
            "question": current_q_text,
            "answer": question,
            "question_index": session_state["current_question_index"]
        })

    # Avancer
    session_state["current_question_index"] += 1

    # Fin du questionnaire ?
    if session_state["current_question_index"] >= len(questions):
        # Évaluation finale
        statut, score, justification = evaluate_qualification_score(
            client_info,
            session_state["qualification_answers"]
        )

        # Refus si créneau requis non choisi
        if session_state.get("refuse_no_slot", False):
            statut = "REFUSÉ"
            justification += (
                "\n\n❌ Créneau non sélectionné alors que des dates étaient disponibles."
                "\nVeuillez nous indiquer un créneau pour poursuivre l'inscription."
            )

        formation_interesse = session_state["formation_choisie"]

        db_service = get_database_service()
        if not db_service.connect():
            return "Erreur de connexion à la base de données. Veuillez réessayer plus tard.", False, True

        availability = db_service.get_formation_availability(formation_interesse)

        # Si non disponible → alternatives
        if not availability["disponible"]:
            alternatives = db_service.get_alternative_formations(formation_interesse)
            session_label = ""
            if session_state.get("selected_session_id") and session_state.get("sessions_options"):
                chosen = next((s for s in session_state["sessions_options"] if s["id"] == session_state["selected_session_id"]), None)
                if chosen:
                    session_label = f"\n**CRÉNEAU CHOISI:** {_format_session(chosen)}"

            message_final = f"""
{justification}

**FORMATION COMPLÈTE OU NON DISPONIBLE**

La formation "{formation_interesse}" n'est pas disponible actuellement.

**FORMATIONS ALTERNATIVES DISPONIBLES:**
"""
            if alternatives:
                for alt in alternatives:
                    message_final += f"• {alt['nom']} - {alt['places_disponibles']} places disponibles - {alt['prix']}€\n"
            else:
                message_final += "Aucune formation alternative disponible actuellement.\n"

            message_final += """
**Veuillez choisir une autre formation ou contactez-nous pour être informé(e) des prochaines sessions.**

📧 **Votre demande a été transmise à notre équipe qui vous contactera pour vous proposer des alternatives.**
"""
            db_service.disconnect()

            # Reset état
            session_state["qualification_in_progress"] = False
            session_state["qualification_questions"] = []
            session_state["qualification_answers"] = []
            session_state["current_question_index"] = 0
            session_state["sessions_options"] = []
            session_state["selected_session_id"] = None
            session_state["slot_required"] = False
            session_state["refuse_no_slot"] = False

            # Analytics fin (non disponible)
            log_analytics_event("completion", {"status": statut, "score": score, "formation": formation_interesse, "session_chosen": session_label})
            end_analytics_tracking("completed", statut)

            return message_final, True, True

        # Réservation si qualifié
        if statut == "QUALIFIÉ":
            reservation_success = db_service.reserve_place(
                availability["formation_id"],
                client_info,
                statut,
                score
            )
            if reservation_success:
                session_label = ""
                if session_state.get("selected_session_id") and session_state.get("sessions_options"):
                    chosen = next((s for s in session_state["sessions_options"] if s["id"] == session_state["selected_session_id"]), None)
                    if chosen:
                        session_label = f"\n**CRÉNEAU CHOISI:** {_format_session(chosen)}"

                message_final = f"""
{justification}

**FÉLICITATIONS !** Vous êtes qualifié et une place vous a été réservée !

**FORMATION:** {availability['nom']}
**PLACES DISPONIBLES:** {max(availability['places_disponibles'] - 1, 0)} restantes
**PRIX:** {availability['prix']}€
**DURÉE:** {availability['duree_jours']} jours{session_label}

📧 **Votre inscription a été confirmée ! Notre équipe vous contactera dans les 24h pour finaliser les détails.**
"""
            else:
                message_final = f"""
{justification}

**PROBLÈME DE RÉSERVATION**

Votre qualification est confirmée mais nous n'avons pas pu réserver votre place.
Cela peut arriver si la formation s'est remplie entre temps.

📧 **Votre dossier a été transmis à notre équipe qui vous contactera pour vous proposer une solution.**
"""
        else:
            message_final = f"""
{justification}

**Votre profil nécessite une étude approfondie.**

📧 **Votre dossier a été transmis à notre équipe qui vous contactera sous 48h.**
"""

        db_service.disconnect()

        # Reset état global
        sessions_options = session_state.get("sessions_options", [])
        chosen = None
        if session_state.get("selected_session_id"):
            chosen = next((s for s in sessions_options if s["id"] == session_state["selected_session_id"]), None)

        session_state["qualification_in_progress"] = False
        session_state["qualification_questions"] = []
        session_state["qualification_answers"] = {}
        session_state["current_question_index"] = 0
        session_state["sessions_options"] = []
        session_state["selected_session_id"] = None
        session_state["slot_required"] = False
        session_state["refuse_no_slot"] = False

        # Email + analytics
        chosen_str = _format_session(chosen) if chosen else "Non précisé"
        formation_details = (
            f"Formation demandée: {formation_interesse}\n"
            f"Statut: {statut}\n"
            f"{justification}\n"
            f"FORMATION: {availability['nom']}\n"
            f"CRÉNEAU: {chosen_str}\n"
            f"PRIX: {availability['prix']}€\n"
            f"DURÉE: {availability['duree_jours']} jours"
        )
        send_inscription_notification(client_info, formation_details)
        
        client_email_sent = send_client_notification(
            client_info, 
            statut, 
            formation_details
        )

        log_analytics_event("completion", {
            "status": statut,
            "score": score,
            "formation": formation_interesse,
            "session_chosen": chosen_str,
            "client_email_sent": client_email_sent 
        })
        end_analytics_tracking("completed", statut)

        return message_final, True, True

    # Continuer le questionnaire
    idx = session_state["current_question_index"]
    if idx >= len(questions):
        return "Merci, vos réponses sont complètes. Notre équipe vous recontactera rapidement.", True, True

    next_question = questions[idx]
    question_num = idx + 1
    total_questions = len(questions)

    next_message = f"""
Merci pour votre réponse !

**Question {question_num}/{total_questions}:** {next_question}

Veuillez répondre pour continuer.
"""
    return next_message, False, False