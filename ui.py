import streamlit as st
import os
import re
from langchain_ollama import ChatOllama
from document_loader import load_documents_into_database

from models import get_list_of_models

from llm import getStreamingChain, get_fallback_answer, process_qualification_flow, detect_inscription_intent

EMBEDDING_MODEL = "nomic-embed-text"
PATH = "Research"

# Configuration de la page
st.set_page_config(
    page_title="Dream Pastry - Assistant Formation",
    page_icon="🧁",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Styles CSS personnalisés
st.markdown("""
<style>
    /* Styles généraux */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }
    
    .main-header h1 {
        color: white;
        font-size: 3rem;
        margin: 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .main-header p {
        color: rgba(255,255,255,0.9);
        font-size: 1.2rem;
        margin: 0.5rem 0 0 0;
    }
    
    /* Formulaire de qualification */
    .qualification-form {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
    
    .form-section {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #667eea;
    }
    
    .form-section h3 {
        color: #667eea;
        margin-top: 0;
        margin-bottom: 1rem;
    }
    
    /* Messages de chat */
    .chat-message {
        padding: 1rem;
        border-radius: 15px;
        margin: 0.5rem 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: 20%;
    }
    
    .assistant-message {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        margin-right: 20%;
    }
    
    /* Boutons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.5rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    
    /* Onglets */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: #f8f9fa;
        border-radius: 10px 10px 0 0;
        padding: 1rem 2rem;
        font-weight: 600;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    /* Métriques */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        text-align: center;
        border-top: 4px solid #667eea;
    }
    
    /* Status badges */
    .status-badge {
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
        margin: 0.25rem;
    }
    
    .status-qualified {
        background: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    
    .status-waiting {
        background: #fff3cd;
        color: #856404;
        border: 1px solid #ffeaa7;
    }
    
    .status-refused {
        background: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
    }
    
    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .fade-in {
        animation: fadeIn 0.5s ease-out;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .main-header h1 {
            font-size: 2rem;
        }
        
        .user-message, .assistant-message {
            margin-left: 0;
            margin-right: 0;
        }
    }
</style>
""", unsafe_allow_html=True)

# En-tête principal
st.markdown("""
<div class="main-header fade-in">
    <h1>🧁 Dream Pastry</h1>
    <p>Votre assistant intelligent pour les formations en pâtisserie</p>
</div>
""", unsafe_allow_html=True)

# Onglets pour l'interface
tab1, tab2 = st.tabs(["💬 Chat & Qualification", "📊 Analytics"])

if "messages" not in st.session_state:
    st.session_state.messages = []

# Formulaire de qualification client
if "client_info" not in st.session_state:
    st.session_state["client_info"] = None

# Mode de l'application
if "app_mode" not in st.session_state:
    st.session_state["app_mode"] = "chat"  # "chat" ou "qualification"

# Charge les documents UNE FOIS par session (cache mémoire)
if "documents_loaded" not in st.session_state:
    with st.spinner("Chargement des documents..."):
        try:
            st.session_state["vectorstore"] = load_documents_into_database(EMBEDDING_MODEL, PATH)
            st.session_state["documents_loaded"] = True
            st.success("✅ Documents chargés avec succès !")
        except Exception as e:
            st.error(f"❌ Erreur lors du chargement des documents: {str(e)}")

# ===== ONGLET 1: CHAT & QUALIFICATION =====
with tab1:
    if st.session_state["client_info"] is None:
        st.markdown("""
        <div class="qualification-form fade-in">
            <h2 style="text-align: center; color: #667eea; margin-bottom: 2rem;">
                🎯 Formulaire de Qualification
            </h2>
            <p style="text-align: center; color: #666; margin-bottom: 2rem;">
                Renseignez vos informations pour commencer votre parcours de formation personnalisé
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("formulaire_qualification"):
            # Section informations personnelles
            st.markdown("""
            <div class="form-section">
                <h3>👤 Informations Personnelles</h3>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                prenom = st.text_input("Prénom *", placeholder="Votre prénom")
                email = st.text_input("Email *", placeholder="votre.email@exemple.com")
                age = st.number_input("Âge *", min_value=16, max_value=100, value=25)
            with col2:
                nom = st.text_input("Nom *", placeholder="Votre nom")
                numero_telephone = st.text_input("Numéro de téléphone *", placeholder="0123456789")
                ville = st.text_input("Ville", placeholder="Votre ville")
            
            # Section professionnelle
            st.markdown("""
            <div class="form-section">
                <h3>💼 Situation Professionnelle</h3>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                statut = st.selectbox("Statut professionnel *", 
                                    ["Salarié", "Demandeur d'emploi", "Indépendant", "Étudiant", "Autre"],
                                    help="Votre situation professionnelle actuelle")
                cpf = st.radio("CPF actif ? *", ["Oui", "Non", "Je ne sais pas"],
                              help="Le Compte Personnel de Formation")
            with col2:
                preference = st.selectbox("Préférence de formation *", 
                                        ["Présentiel", "Distanciel", "Peu importe"],
                                        help="Votre préférence pour le mode de formation")
                budget = st.number_input("Budget disponible (€) *", min_value=100, value=1000,
                                       help="Budget que vous pouvez consacrer à la formation")
            
            # Section motivation
            st.markdown("""
            <div class="form-section">
                <h3>🎯 Motivation & Objectifs</h3>
            </div>
            """, unsafe_allow_html=True)
            
            motivation = st.text_area("Qu'est-ce qui vous motive dans l'apprentissage de la pâtisserie ?", 
                                    placeholder="Décrivez vos motivations et objectifs...",
                                    height=100)
            
            # Bouton de soumission stylisé
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                submit = st.form_submit_button("🚀 Commencer ma qualification", 
                                             use_container_width=True,
                                             type="primary")
            
            st.markdown("""
            <div style="text-align: center; color: #666; font-size: 0.9rem; margin-top: 1rem;">
                * Champs obligatoires
            </div>
            """, unsafe_allow_html=True)

        if submit:
            # Validation des champs obligatoires
            if not nom or not prenom or not numero_telephone or not email or not statut or not cpf or not preference or budget < 100:
                st.error("❌ Veuillez remplir tous les champs obligatoires (marqués d'un *)")
            else:
                numero_ok = re.fullmatch(r"0\d{9}", numero_telephone)
                email_ok = re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email)

                if not numero_ok:
                    st.error("❌ Veuillez entrer un numéro de téléphone français valide (10 chiffres, commence par 0).")
                elif not email_ok:
                    st.error("❌ Veuillez entrer une adresse email valide.")
                else:
                    st.session_state["client_info"] = {
                        "nom": nom,
                        "prenom": prenom,
                        "numero_telephone": numero_telephone,
                        "email": email,
                        "age": age,
                        "statut": statut,
                        "cpf": cpf,
                        "ville": ville,
                        "preference": preference,
                        "budget": budget,
                        "motivation": motivation if motivation else "Non renseigné"
                    }
                    
                    # Message de bienvenue stylisé
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); 
                                padding: 1.5rem; border-radius: 15px; margin: 1rem 0; 
                                border-left: 4px solid #28a745;">
                        <h3 style="color: #155724; margin: 0 0 1rem 0;">🎉 Bienvenue {prenom} !</h3>
                        <p style="color: #155724; margin: 0;">
                            Vos informations ont été enregistrées avec succès. Vous pouvez maintenant commencer votre qualification personnalisée !
                        </p>
                    </div>
                    """.format(prenom=prenom), unsafe_allow_html=True)
                    
                    welcome = (
                        f"Bonjour {prenom} ! Merci d'avoir renseigné vos informations. Vous avez {age} ans, statut : {statut}, ville : {ville}, préférence : {preference}, budget : {budget}€. "
                        "N'hésitez pas à poser vos questions ou demander des recommandations de formation adaptées à votre profil."
                    )
                    st.session_state.messages.append({"role": "assistant", "content": welcome})
                    st.rerun()

    else:
        # En-tête info stylisé
        client_info = st.session_state["client_info"]
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 1rem 2rem; border-radius: 15px; margin: 1rem 0; 
                    color: white; text-align: center;">
            <h3 style="margin: 0; color: white;">👤 Connecté en tant que {client_info['prenom']} {client_info['nom']}</h3>
            <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">
                {client_info['statut']} • {client_info['ville']} • Budget: {client_info['budget']}€
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Boutons de mode stylisés
        st.markdown("""
        <div style="text-align: center; margin: 2rem 0;">
            <h4 style="color: #667eea; margin-bottom: 1rem;">Choisissez votre mode d'interaction</h4>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💬 Mode Chat", 
                        type="primary" if st.session_state["app_mode"] == "chat" else "secondary",
                        use_container_width=True):
                st.session_state["app_mode"] = "chat"
                st.rerun()
        with col2:
            if st.button("🎯 Mode Qualification", 
                        type="primary" if st.session_state["app_mode"] == "qualification" else "secondary",
                        use_container_width=True):
                st.session_state["app_mode"] = "qualification"
                st.rerun()

        # Mode Chat
        if st.session_state["app_mode"] == "chat":
            # En-tête du chat
            st.markdown("""
            <div style="background: #f8f9fa; padding: 1rem; border-radius: 10px; margin: 1rem 0; 
                        border-left: 4px solid #667eea;">
                <h4 style="margin: 0; color: #667eea;">💬 Chat avec l'Assistant Dream Pastry</h4>
                <p style="margin: 0.5rem 0 0 0; color: #666; font-size: 0.9rem;">
                    Posez vos questions sur nos formations, nos programmes ou obtenez des conseils personnalisés
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Affiche l'historique avec style personnalisé
            for message in st.session_state.messages:
                if message["role"] == "user":
                    st.markdown(f"""
                    <div class="user-message fade-in">
                        <strong>Vous:</strong><br>
                        {message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="assistant-message fade-in">
                        <strong>🧁 Assistant Dream Pastry:</strong><br>
                        {message["content"]}
                    </div>
                    """, unsafe_allow_html=True)

            # Saisie utilisateur stylisée
            if prompt := st.chat_input("💬 Posez votre question sur nos formations..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                # Afficher immédiatement le message utilisateur
                st.markdown(f"""
                <div class="user-message fade-in">
                    <strong>Vous:</strong><br>
                    {prompt}
                </div>
                """, unsafe_allow_html=True)
                st.session_state["pending_user_message"] = prompt

            # Si un message est en attente, on génère exactement UNE FOIS
            if "pending_user_message" in st.session_state:
                user_msg = st.session_state["pending_user_message"]
                
                # Indicateur de chargement stylisé
                with st.spinner("🧁 L'assistant réfléchit à votre question..."):
                    try:
                        if detect_inscription_intent(user_msg):
                            st.session_state["app_mode"] = "qualification"
                            del st.session_state["pending_user_message"]
                            st.rerun()
                        else:
                            llm = ChatOllama(model="gemma3:4b")
                            db = st.session_state.get("vectorstore")

                            # Fallback rapide si connu
                            fallback_answer = get_fallback_answer(user_msg)
                            if fallback_answer:
                                response = fallback_answer
                            else:
                                # Streaming contrôlé via placeholder
                                chain = getStreamingChain(user_msg, st.session_state.messages, llm, db)
                                response = ""
                                placeholder = st.empty()
                                for chunk in chain:
                                    if hasattr(chunk, "content"):
                                        response += chunk.content
                                    else:
                                        response += str(chunk)
                                    placeholder.markdown(f"""
                                    <div class="assistant-message fade-in">
                                        <strong>🧁 Assistant Dream Pastry:</strong><br>
                                        {response}▌
                                    </div>
                                    """, unsafe_allow_html=True)
                                
                                # Affichage final stylisé
                                placeholder.markdown(f"""
                                <div class="assistant-message fade-in">
                                    <strong>🧁 Assistant Dream Pastry:</strong><br>
                                    {response}
                                </div>
                                """, unsafe_allow_html=True)

                            st.session_state.messages.append({"role": "assistant", "content": response})
                    except Exception as e:
                        error_msg = f"❌ Erreur: {str(e)}"
                        st.markdown(f"""
                        <div style="background: #f8d7da; color: #721c24; padding: 1rem; 
                                    border-radius: 10px; border-left: 4px solid #dc3545; margin: 1rem 0;">
                            <strong>❌ Erreur:</strong> {str(e)}
                        </div>
                        """, unsafe_allow_html=True)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                # Dans tous les cas, on supprime le flag pour éviter un double traitement
                if "pending_user_message" in st.session_state:
                    del st.session_state["pending_user_message"]

        # Mode Qualification
        elif st.session_state["app_mode"] == "qualification":
            # En-tête de qualification stylisé
            st.markdown("""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 2rem; border-radius: 15px; margin: 1rem 0; text-align: center;">
                <h2 style="margin: 0; color: white;">🎯 Processus de Qualification</h2>
                <p style="margin: 0.5rem 0 0 0; color: rgba(255,255,255,0.9);">
                    Répondez aux questions pour évaluer votre éligibilité à nos formations
                </p>
            </div>
            """, unsafe_allow_html=True)

            if "qualification_messages" not in st.session_state:
                st.session_state["qualification_messages"] = []

            # Affiche l'historique de qualification avec style
            for message in st.session_state["qualification_messages"]:
                if message["role"] == "user":
                    st.markdown(f"""
                    <div class="user-message fade-in">
                        <strong>Vous:</strong><br>
                        {message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="assistant-message fade-in">
                        <strong>🎯 Évaluateur Dream Pastry:</strong><br>
                        {message["content"]}
                    </div>
                    """, unsafe_allow_html=True)

            # Saisie utilisateur pour qualification stylisée
            if prompt := st.chat_input("💬 Répondez à la question..."):
                st.session_state["qualification_messages"].append({"role": "user", "content": prompt})
                st.markdown(f"""
                <div class="user-message fade-in">
                    <strong>Vous:</strong><br>
                    {prompt}
                </div>
                """, unsafe_allow_html=True)

                # Indicateur de traitement stylisé
                with st.spinner("🎯 Évaluation de votre réponse en cours..."):
                    try:
                        final_response, email_sent, qualification_completee = process_qualification_flow(
                            st.session_state["client_info"],
                            prompt,
                            "",
                            st.session_state,
                        )
                        
                        # Affichage de la réponse stylisé
                        st.markdown(f"""
                        <div class="assistant-message fade-in">
                            <strong>🎯 Évaluateur Dream Pastry:</strong><br>
                            {final_response}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.session_state["qualification_messages"].append({"role": "assistant", "content": final_response})

                        # Messages de statut stylisés
                        if email_sent:
                            if "QUALIFIÉ" in final_response:
                                st.markdown("""
                                <div style="background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); 
                                            padding: 1.5rem; border-radius: 15px; margin: 1rem 0; 
                                            border-left: 4px solid #28a745; text-align: center;">
                                    <h3 style="color: #155724; margin: 0 0 1rem 0;">🎉 Félicitations !</h3>
                                    <p style="color: #155724; margin: 0;">
                                        Vous êtes qualifié ! Votre dossier a été transmis à notre équipe et vous recevrez un email de confirmation !
                                    </p>
                                </div>
                                """, unsafe_allow_html=True)
                            elif "LISTE D'ATTENTE" in final_response:
                                st.markdown("""
                                <div style="background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%); 
                                            padding: 1.5rem; border-radius: 15px; margin: 1rem 0; 
                                            border-left: 4px solid #ffc107; text-align: center;">
                                    <h3 style="color: #856404; margin: 0 0 1rem 0;">⏳ Liste d'attente</h3>
                                    <p style="color: #856404; margin: 0;">
                                        Vous êtes sur liste d'attente. Notre équipe vous contactera sous 48h et vous recevrez un email d'information.
                                    </p>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown("""
                                <div style="background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%); 
                                            padding: 1.5rem; border-radius: 15px; margin: 1rem 0; 
                                            border-left: 4px solid #dc3545; text-align: center;">
                                    <h3 style="color: #721c24; margin: 0 0 1rem 0;">❌ Non qualifié</h3>
                                    <p style="color: #721c24; margin: 0;">
                                        Votre profil ne correspond pas actuellement à nos critères. Vous recevrez un email avec des alternatives.
                                    </p>
                                </div>
                                """, unsafe_allow_html=True)

                        if qualification_completee:
                            st.markdown("---")
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
                                if st.button("💬 Retourner au chat", type="primary", use_container_width=True):
                                    st.session_state["app_mode"] = "chat"
                                    st.rerun()
                    except Exception as e:
                        error_msg = f"❌ Erreur lors de la qualification: {str(e)}"
                        st.markdown(f"""
                        <div style="background: #f8d7da; color: #721c24; padding: 1rem; 
                                    border-radius: 10px; border-left: 4px solid #dc3545; margin: 1rem 0;">
                            <strong>❌ Erreur:</strong> {str(e)}
                        </div>
                        """, unsafe_allow_html=True)
                        st.session_state["qualification_messages"].append({"role": "assistant", "content": error_msg})

# ===== ONGLET 2: DASHBOARD ANALYTICS =====
with tab2:
    # En-tête du dashboard stylisé
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 2rem; border-radius: 15px; margin: 1rem 0; text-align: center;">
        <h2 style="margin: 0; color: white;">📊 Dashboard Analytics</h2>
        <p style="margin: 0.5rem 0 0 0; color: rgba(255,255,255,0.9);">
            Suivi des performances et amélioration continue
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sélecteur de période stylisé
    st.markdown("""
    <div style="background: #f8f9fa; padding: 1.5rem; border-radius: 10px; margin: 1rem 0; 
                border-left: 4px solid #667eea;">
        <h4 style="margin: 0 0 1rem 0; color: #667eea;">⚙️ Paramètres d'analyse</h4>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 3])
    with col1:
        days = st.selectbox("📅 Période d'analyse", [7, 30, 90], index=1, 
                           format_func=lambda x: f"Derniers {x} jours",
                           help="Sélectionnez la période d'analyse des données")
    with col2:
        if st.button("🔄 Actualiser les données", type="secondary", use_container_width=True):
            st.rerun()
    
    try:
        from database_service import get_database_service
        db = get_database_service()
        
        if db.connect():
            metrics = db.get_analytics_metrics(days)
            db.disconnect()
            
            if metrics and any(metrics.values()):
                # En-tête des métriques
                st.markdown("""
                <div style="background: #f8f9fa; padding: 1.5rem; border-radius: 10px; margin: 2rem 0; 
                            border-left: 4px solid #667eea;">
                    <h4 style="margin: 0 0 1rem 0; color: #667eea;">📊 Métriques Principales</h4>
                </div>
                """, unsafe_allow_html=True)
                
                # Métriques principales stylisées
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    completion_rate = metrics.get('completion_rate', 0) or 0
                    st.markdown(f"""
                    <div class="metric-card fade-in">
                        <h3 style="color: #667eea; margin: 0 0 0.5rem 0;">📈</h3>
                        <h2 style="color: #333; margin: 0 0 0.5rem 0;">{completion_rate}%</h2>
                        <p style="color: #666; margin: 0; font-size: 0.9rem;">Taux de complétion</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    qualification_rate = metrics.get('qualification_rate', 0) or 0
                    st.markdown(f"""
                    <div class="metric-card fade-in">
                        <h3 style="color: #28a745; margin: 0 0 0.5rem 0;">✅</h3>
                        <h2 style="color: #333; margin: 0 0 0.5rem 0;">{qualification_rate}%</h2>
                        <p style="color: #666; margin: 0; font-size: 0.9rem;">Taux de qualification</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    median_duration = metrics.get('median_duration_minutes', 0) or 0
                    st.markdown(f"""
                    <div class="metric-card fade-in">
                        <h3 style="color: #ffc107; margin: 0 0 0.5rem 0;">⏱️</h3>
                        <h2 style="color: #333; margin: 0 0 0.5rem 0;">{median_duration} min</h2>
                        <p style="color: #666; margin: 0; font-size: 0.9rem;">Temps médian</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col4:
                    total_sessions = metrics.get('total_sessions', 0) or 0
                    st.markdown(f"""
                    <div class="metric-card fade-in">
                        <h3 style="color: #dc3545; margin: 0 0 0.5rem 0;">📊</h3>
                        <h2 style="color: #333; margin: 0 0 0.5rem 0;">{total_sessions}</h2>
                        <p style="color: #666; margin: 0; font-size: 0.9rem;">Total sessions</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Détails des métriques stylisés
                st.markdown("""
                <div style="background: #f8f9fa; padding: 1.5rem; border-radius: 10px; margin: 2rem 0; 
                            border-left: 4px solid #667eea;">
                    <h4 style="margin: 0 0 1rem 0; color: #667eea;">📋 Détails & Recommandations</h4>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("""
                    <div style="background: white; padding: 1.5rem; border-radius: 10px; 
                                box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin: 1rem 0;">
                        <h4 style="color: #667eea; margin: 0 0 1rem 0;">📋 Détails des sessions</h4>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    completed_sessions = metrics.get('completed_sessions', 0) or 0
                    qualified_count = metrics.get('qualified_count', 0) or 0
                    avg_duration = metrics.get('avg_duration_minutes', 0) or 0
                    
                    st.markdown(f"""
                    <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin: 0.5rem 0;">
                        <strong>Sessions complétées:</strong> {completed_sessions}
                    </div>
                    <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin: 0.5rem 0;">
                        <strong>Clients qualifiés:</strong> {qualified_count}
                    </div>
                    <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin: 0.5rem 0;">
                        <strong>Temps moyen:</strong> {avg_duration} minutes
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown("""
                    <div style="background: white; padding: 1.5rem; border-radius: 10px; 
                                box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin: 1rem 0;">
                        <h4 style="color: #667eea; margin: 0 0 1rem 0;">🎯 Recommandations</h4>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    completion_rate = metrics.get('completion_rate', 0) or 0
                    qual_rate = metrics.get('qualification_rate', 0) or 0
                    
                    # Recommandations pour le taux de complétion
                    if completion_rate < 50:
                        st.markdown("""
                        <div style="background: #fff3cd; color: #856404; padding: 1rem; 
                                    border-radius: 8px; border-left: 4px solid #ffc107; margin: 0.5rem 0;">
                            <strong>⚠️ Taux de complétion faible</strong><br>
                            Simplifier le questionnaire
                        </div>
                        """, unsafe_allow_html=True)
                    elif completion_rate > 80:
                        st.markdown("""
                        <div style="background: #d4edda; color: #155724; padding: 1rem; 
                                    border-radius: 8px; border-left: 4px solid #28a745; margin: 0.5rem 0;">
                            <strong>✅ Excellent taux de complétion</strong><br>
                            Continuer sur cette lancée
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div style="background: #d1ecf1; color: #0c5460; padding: 1rem; 
                                    border-radius: 8px; border-left: 4px solid #17a2b8; margin: 0.5rem 0;">
                            <strong>ℹ️ Taux de complétion correct</strong><br>
                            Peut être amélioré
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Recommandations pour le taux de qualification
                    if qual_rate < 30:
                        st.markdown("""
                        <div style="background: #fff3cd; color: #856404; padding: 1rem; 
                                    border-radius: 8px; border-left: 4px solid #ffc107; margin: 0.5rem 0;">
                            <strong>⚠️ Peu de clients qualifiés</strong><br>
                            Ajuster les critères
                        </div>
                        """, unsafe_allow_html=True)
                    elif qual_rate > 70:
                        st.markdown("""
                        <div style="background: #d4edda; color: #155724; padding: 1rem; 
                                    border-radius: 8px; border-left: 4px solid #28a745; margin: 0.5rem 0;">
                            <strong>✅ Bon taux de qualification</strong><br>
                            Critères bien ajustés
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div style="background: #d1ecf1; color: #0c5460; padding: 1rem; 
                                    border-radius: 8px; border-left: 4px solid #17a2b8; margin: 0.5rem 0;">
                            <strong>ℹ️ Taux de qualification correct</strong><br>
                            Peut être optimisé
                        </div>
                        """, unsafe_allow_html=True)
                
                # Top questions non répondues
                st.markdown("---")
                st.subheader("❓ Top Questions Non Répondues")
                
                unanswered = metrics.get('top_unanswered_questions', [])
                if unanswered:
                    st.write("Ces questions sont fréquemment posées mais non couvertes dans la FAQ :")
                    
                    for i, q in enumerate(unanswered, 1):
                        with st.expander(f"#{i} - {q['question_text'][:100]}..."):
                            st.write(f"**Question complète:** {q['question_text']}")
                            st.write(f"**Fréquence:** {q['frequency']} fois")
                            st.write(f"**Dernière fois:** {q['last_seen']}")
                            
                            # Bouton pour ajouter à la FAQ (simulation)
                            if st.button(f"📝 Ajouter à la FAQ", key=f"add_faq_{i}"):
                                st.success("✅ Question ajoutée à la liste d'amélioration de la FAQ")
                else:
                    st.info("🎉 Aucune question non répondue récurrente !")
                
                # Graphiques (simulation avec des données de base)
                st.markdown("---")
                st.subheader("📈 Évolution des métriques")
                
                import pandas as pd
                import numpy as np
                
                # Simulation de données historiques
                dates = pd.date_range(end='today', periods=days, freq='D')
                total_sessions = metrics.get('total_sessions', 0) or 0
                data = {
                    'Date': dates,
                    'Taux complétion': np.random.normal(completion_rate, 5, days),
                    'Taux qualification': np.random.normal(qual_rate, 3, days),
                    'Sessions': np.random.poisson(max(total_sessions // days, 1), days)
                }
                df = pd.DataFrame(data)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.line_chart(df.set_index('Date')[['Taux complétion', 'Taux qualification']])
                
                with col2:
                    st.bar_chart(df.set_index('Date')['Sessions'])
                
            else:
                st.warning("⚠️ Aucune donnée analytics disponible pour cette période")
                
        else:
            st.error("❌ Impossible de se connecter à la base de données")
            
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement des analytics: {str(e)}")
        st.write("Vérifiez que la base de données est configurée et que les tables analytics existent.")