import os
import time
import re
import streamlit as st
from dotenv import load_dotenv
from pinecone import Pinecone
from groq import Groq
from google import genai
from sentence_transformers import SentenceTransformer

# Load environment variables
load_dotenv()

st.set_page_config(
    page_title="Liberty Dental Plan - AI Chatbot",
    page_icon="🦷",
    layout="centered",
    initial_sidebar_state="expanded"
)

# --- CACHED RESOURCES ---
@st.cache_resource
def load_embedding_model():
    return SentenceTransformer('all-MiniLM-L6-v2')

@st.cache_resource
def get_pinecone_index():
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    return pc.Index("liberty-dental-kb")

@st.cache_resource
def get_groq_client():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- PUBLIC LINKS FOR ROUTING ---
PUBLIC_LINKS = {
    "Home": "https://uat-new.libertydentalplan.com/",
    "Members": "https://uat-new.libertydentalplan.com/members",
    "Find a Dentist": "https://findadentist-stage.libertydentalplan.com",
    "Member Login": "https://i-transact.libertydentalplan.com/iTransact/logon/logon.aspx",
    "Mobile App (Apple)": "https://apps.apple.com/us/app/liberty-dental/id1443527723",
    "Mobile App (Android)": "https://play.google.com/store/apps/details?id=com.libertydentalplan.mobile",
    "File a Grievance or Appeal": "https://uat-new.libertydentalplan.com/members/file-grievance-appeal",
    "Join Provider Network": "https://uat-new.libertydentalplan.com/providers/join-our-network",
    "Brokers": "https://uat-new.libertydentalplan.com/brokers",
    "Broker Contact": "https://uat-new.libertydentalplan.com/brokers/contact-client-services",
    "Teledentistry": "https://www.teledentistry.com/insurance/liberty",
    "Shop Plans": "https://sales.libertydentalplan.com/dentalplans",
    "Contact Liberty": "https://uat-new.libertydentalplan.com/about/contact-liberty-dental-plan",
}

RESTRICTED_PATTERNS = [
    "member id", "ssn", "social security", "date of birth", "dob",
    "password", "claim number", "my claim", "my eligibility",
    "my benefits", "my copay", "my deductible", "diagnose",
    "medical advice"
]

CAPABILITIES_PATTERNS = [
    "how can you help", "what can you help", "what can you do",
    "what can i ask", "what can i search", "what do you do",
    "help me", "what are you", "who are you", "what is this",
    "what topics", "what questions", "tell me about yourself",
    "how does this work", "what can this chatbot"
]

CAPABILITIES_RESPONSE = (
    "I'm the Liberty Dental Plan virtual assistant. Here's what I can help you with:\n\n"
    "**For Members:**\n"
    "- Find an in-network dentist near you\n"
    "- Log in to the Member Portal\n"
    "- Download the Liberty Dental mobile app\n"
    "- Teledentistry and dental emergencies\n"
    "- File a grievance or appeal\n\n"
    "**For Plan Shoppers:**\n"
    "- Explore individual and family dental plans\n"
    "- Shop and compare plans online\n\n"
    "**For Providers:**\n"
    "- Join the Liberty Dental network\n"
    "- Access the Provider Portal\n\n"
    "**For Brokers:**\n"
    "- Learn about selling Liberty plans\n"
    "- Contact client services\n\n"
    "Note: I can only help with public website information. For your personal account, claims, "
    "or benefits, please log in to the secure Member Portal."
)

# --- UTILITY FUNCTIONS ---
def normalize(text):
    return re.sub(r"[^a-z0-9\s]", " ", text.lower()).strip()

def has_restricted_request(question):
    normalized_question = normalize(question)
    return any(pattern in normalized_question for pattern in RESTRICTED_PATTERNS)

def is_capabilities_request(question):
    normalized_question = normalize(question)
    return any(pattern in normalized_question for pattern in CAPABILITIES_PATTERNS)

def format_links(link_names):
    if not link_names:
        return ""
    html = '<div class="helpful-links-container"><strong>Related Links:</strong><div class="helpful-links">'
    for name in link_names:
        url = PUBLIC_LINKS.get(name, "#")
        html += f'<a href="{url}" target="_blank" class="helpful-link-btn">{name}</a>'
    html += '</div></div>'
    return html

def determine_related_links(text):
    """Simple heuristic to suggest links based on generated text content."""
    links = set()
    text_lower = text.lower()
    
    if "app" in text_lower or "download" in text_lower:
        links.update(["Mobile App (Apple)", "Mobile App (Android)"])
    if "shop" in text_lower or "buy" in text_lower or "individual" in text_lower:
        links.add("Shop Plans")
    if "login" in text_lower or "portal" in text_lower:
        links.add("Member Login")
    if "find" in text_lower and "dentist" in text_lower:
        links.add("Find a Dentist")
    if "teledentistry" in text_lower or "emergency" in text_lower:
        links.add("Teledentistry")
    if "provider" in text_lower or "join" in text_lower:
        links.add("Join Provider Network")
    if "broker" in text_lower:
        links.update(["Brokers", "Broker Contact"])
    if "grievance" in text_lower or "appeal" in text_lower:
        links.add("File a Grievance or Appeal")
        
    return list(links)

# --- AI ROUTING ENGINE ---
def fetch_answer_from_ai(question):
    if has_restricted_request(question):
        return (
            "For personal plan details, claim status, eligibility, benefits, copays, deductibles, or account-specific information, "
            "please log in to the secure Liberty member portal. I can only help with public Liberty Dental Plan website information.",
            ["Member Login", "Contact Liberty"]
        )

    if is_capabilities_request(question):
        return (CAPABILITIES_RESPONSE, ["Members", "Shop Plans", "Find a Dentist", "Join Provider Network"])

    # 1. Embed the query
    model = load_embedding_model()
    query_embedding = model.encode([question]).tolist()[0]
    
    # 2. Search Pinecone
    index = get_pinecone_index()
    try:
        results = index.query(
            vector=query_embedding,
            top_k=6,
            include_metadata=True
        )
    except Exception as e:
        print(f"Pinecone error: {e}")
        return "I'm having trouble accessing my knowledge base right now. Please try again later.", ["Contact Liberty"]

    if not results.matches or results.matches[0].score < 0.45:
        return (
            "I could not find specific information about that in our public knowledge base. "
            "Please visit the Contact Liberty page or use the appropriate secure portal for assistance.",
            ["Contact Liberty", "Member Login"]
        )

    # 3. Construct context
    context_parts = []
    for match in results.matches:
        metadata = match.metadata
        context_parts.append(f"Title: {metadata.get('title', '')}\nContent: {metadata.get('content', '')}")
    
    context = "\n\n".join(context_parts)
    
    # 4. Generate answer with Llama (Primary) or Gemini (Fallback)
    system_prompt = (
        "You are a helpful, professional customer support assistant for Liberty Dental Plan. "
        "Answer the user's question clearly and naturally using ONLY the provided knowledge base context. "
        "Do not hallucinate features, plans, or links. If the context does not contain the answer, politely state that you "
        "can only provide information available on the public website and direct them to contact support. "
        "Maintain a human-like, friendly, and professional tone. Keep responses concise."
    )

    try:
        groq_client = get_groq_client()
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": f"Context Information:\n{context}\n\nUser Question: {question}"
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=600,
        )
        answer = chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Llama/Groq error, falling back to Gemini: {e}")
        try:
            gemini_client = get_gemini_client()
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"Context Information:\n{context}\n\nUser Question: {question}",
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3,
                    max_output_tokens=600,
                )
            )
            answer = response.text
        except Exception as gemini_e:
            print(f"Gemini error: {gemini_e}")
            return "I'm sorry, I am experiencing a temporary technical issue generating an answer.", ["Contact Liberty"]
            
    # Determine helpful links based on the context/answer
    links = determine_related_links(answer + " " + question)
    
    return answer, links


# --- UI STYLING ---
def inject_custom_css():
    st.markdown("""
        <style>
        /* Modern Typography */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        html, body, [class*="css"]  {
            font-family: 'Inter', sans-serif;
        }

        /* App Background */
        .stApp {
            background-color: #f8fafc;
        }

        /* Top Header Card */
        .ldp-header {
            padding: 2rem;
            border-radius: 16px;
            background: linear-gradient(135deg, #005eb8 0%, #008b8b 100%);
            color: white;
            margin-bottom: 2rem;
            box-shadow: 0 10px 25px -5px rgba(0, 94, 184, 0.4);
            text-align: center;
        }
        
        .ldp-header h1 {
            color: white;
            font-weight: 700;
            margin-bottom: 0.5rem;
            font-size: 2.2rem;
        }
        
        .ldp-header p {
            font-size: 1.1rem;
            opacity: 0.9;
            margin-bottom: 0;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: white;
            border-right: 1px solid #e2e8f0;
        }

        /* Helpful Links Styling */
        .helpful-links-container {
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid #e2e8f0;
        }
        
        .helpful-links {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.5rem;
        }
        
        .helpful-link-btn {
            background-color: #f1f5f9;
            color: #005eb8 !important;
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            text-decoration: none;
            font-size: 0.85rem;
            font-weight: 500;
            transition: all 0.2s ease;
            border: 1px solid #cbd5e1;
        }
        
        .helpful-link-btn:hover {
            background-color: #005eb8;
            color: white !important;
            border-color: #005eb8;
            text-decoration: none;
        }

        /* Chat bubbles */
        [data-testid="stChatMessage"] {
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1rem;
            background-color: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.03);
            border: 1px solid #f1f5f9;
        }
        
        /* User message specifically */
        [data-testid="stChatMessage"][data-baseweb="chat-message"][class*="user"] {
            background-color: #f0fdfa;
            border-color: #ccfbf1;
        }
        
        /* Quick Action Buttons */
        div.stButton > button {
            width: 100%;
            border-radius: 8px;
            background-color: white;
            color: #334155;
            border: 1px solid #cbd5e1;
            padding: 0.5rem 1rem;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        div.stButton > button:hover {
            border-color: #005eb8;
            color: #005eb8;
            background-color: #f8fafc;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        
        /* Status indicator */
        .status-badge {
            display: inline-block;
            padding: 0.25em 0.6em;
            font-size: 0.75em;
            font-weight: 700;
            line-height: 1;
            text-align: center;
            white-space: nowrap;
            vertical-align: baseline;
            border-radius: 0.25rem;
            background-color: #10b981;
            color: white;
            margin-bottom: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)


# --- MAIN APP LOGIC ---
def main():
    inject_custom_css()

    # Application Header
    st.markdown(
        """
        <div class="ldp-header">
            <span class="status-badge">AI Integration Live</span>
            <h1>Liberty AI Assistant</h1>
            <p>Powered by Contentful, Pinecone, and Llama</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Sidebar Configuration
    with st.sidebar:
        st.image("https://www.libertydentalplan.com/Images/Liberty-Dental-Plan-Logo.png", width=200)
        st.markdown("### Manager's Overview")
        st.info(
            "**End-User Personas Handled:**\n\n"
            "This POC is specifically tuned to the highest-value actions on the public UAT website:\n\n"
            "👤 **Members:** Find a dentist, Member Login, App Download, Teledentistry\n"
            "🛒 **Shoppers:** View plans & Benefits\n"
            "⚕️ **Providers:** Join network, Portal access\n"
            "🤝 **Brokers:** Get quotes"
        )
        st.markdown("---")
        st.markdown("### Technical Architecture")
        st.caption(
            "Connected directly to **Contentful CMS** for live knowledge extraction. "
            "Contexts are retrieved via semantic search using **Pinecone** and responses are generated in a human-like tone using **Llama 3.3 70B** via Groq."
        )
        
        if st.button("🔄 Reset Conversation", type="primary"):
            st.session_state.messages = []
            st.rerun()
            

    # Initialize Chat History
    if "messages" not in st.session_state or not st.session_state.messages:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Hello! I am the Liberty Dental Plan virtual assistant. I can help you find an in-network dentist, manage your current plan, download our mobile app, or answer questions about our individual and family plans. What are you looking for today?",
                "links": []
            }
        ]

    # Quick Actions
    st.markdown("#### Popular Questions")
    quick_actions = [
        "Find an in-network dentist",
        "Log in to my member portal",
        "I have a dental emergency",
        "Download the mobile app"
    ]
    
    cols = st.columns(4)
    for i, action in enumerate(quick_actions):
        if cols[i].button(action, key=f"qa_{i}"):
            handle_user_input(action)

    st.markdown("---")

    # Display Chat History
    for msg in st.session_state.messages:
        avatar = "🧑‍💻" if msg["role"] == "user" else "🦷"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])
            if msg.get("links"):
                st.markdown(format_links(msg["links"]), unsafe_allow_html=True)

    # Chat Input
    if prompt := st.chat_input("Type your question here... (e.g., 'How do I download the app?')"):
        handle_user_input(prompt)


def handle_user_input(prompt):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt, "links": []})
    
    # Display user message immediately
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)
        
    # Display assistant response with loading spinner
    with st.chat_message("assistant", avatar="🦷"):
        with st.spinner("Searching Liberty knowledge base..."):
            answer, links = fetch_answer_from_ai(prompt)
            st.markdown(answer)
            if links:
                st.markdown(format_links(links), unsafe_allow_html=True)
                
    # Save assistant message to state
    st.session_state.messages.append({"role": "assistant", "content": answer, "links": links})

if __name__ == "__main__":
    main()
