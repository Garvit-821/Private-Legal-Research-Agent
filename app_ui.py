import streamlit as st
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# ==========================================
# 1. PAGE SETUP & GLOBAL STYLING (THE LOOK)
# ==========================================
st.set_page_config(page_title="Local-Cortex Workspace", page_icon="🧠", layout="wide")

# Custom Dark Glassmorphism CSS Inject
st.markdown("""
    <style>
        /* Base app wrappers */
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        
        /* Metric Card styling */
        div[data-testid="stMetricValue"] {
            font-size: 24px !important;
            font-weight: 700;
            color: #00f5ff !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 13px !important;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        /* Interactive Chat Enhancements */
        .stChatInputContainer {
            border-radius: 12px !important;
            border: 1px solid #8b5cf6 !important;
        }
        
        /* Sidebar layout tweak */
        section[data-testid="stSidebar"] {
            background-color: #040406 !important;
            border-right: 1px solid #8b5cf6;
        }
    </style>
""", unsafe_allow_html=True)
# ==========================================
# 2. SESSION STATE STATE MANAGEMENT
# ==========================================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "doc_context" not in st.session_state:
    st.session_state.doc_context = None
if "doc_metrics" not in st.session_state:
    st.session_state.doc_metrics = {"chars": 0, "words": 0, "lines": 0}

# ==========================================
# 3. SIDEBAR CONTROLS & INGESTION HUB
# ==========================================
with st.sidebar:
    st.markdown("### 🛰️ DEPLOYMENT CONTROL")
    st.info("🟢 SYSTEM: **Ollama**\n\n🧠 MODEL: `qwen2.5` (Local)")
    st.markdown("---")
    
    st.markdown("### 📁 INGESTION ENGINE")
    uploaded_file = st.file_uploader("Drop analysis blueprint", type=["txt", "pdf", "docx", "md"])
    
    if uploaded_file is not None:
        from backend import extract_text_from_bytes
        file_bytes = uploaded_file.getvalue()
        string_data = extract_text_from_bytes(uploaded_file.name, file_bytes)
        st.session_state.doc_context = string_data
        
        # Calculate file intelligence metrics
        st.session_state.doc_metrics["chars"] = len(string_data)
        st.session_state.doc_metrics["words"] = len(string_data.split())
        st.session_state.doc_metrics["lines"] = len(string_data.splitlines())
        
        st.toast(f"Matrix updated: {uploaded_file.name}", icon="✅")
        
        st.markdown("---")
        if st.button("🧼 PURGE CORE MEMORY", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

# ==========================================
# 4. MAIN COCKPIT DASHBOARD INTERFACE
# ==========================================
if st.session_state.doc_context is None:
    # High-end welcome layout when empty
    st.markdown("# 🧠 LOCAL-CORTEX")
    st.markdown("### Open-Source Local Intelligence Engine")
    st.markdown("---")
    st.warning("⚠️ INITIALIZATION HALTED: System waiting for local data ingestion profile. Drop a file in the left control deck to activate the neural pipeline.")
else:
    # Dashboard Header
    st.markdown(f"## 🧠 LOCAL-CORTEX ACTIVE: {uploaded_file.name.upper()}")
    
    # Live Token/Data Dashboard Grid
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(label="Engine Status", value="READY", delta="Online")
    m2.metric(label="Structural Lines parsed", value=f"{st.session_state.doc_metrics['lines']} lines")
    m3.metric(label="Token Matrix Size", value=f"{st.session_state.doc_metrics['words']} words")
    m4.metric(label="Memory Footprint", value="~2.3 GB", delta="-3.1 GB Saved", delta_color="inverse")
    st.markdown("---")

    # Main Split Screen: Left Side Document Viewer, Right Side Neural Chat
    left_deck, right_deck = st.columns([1, 1.2])

    with left_deck:
        st.markdown("### 👓 LIVE DATALINK STREAM")
        # Renders the uploaded document inside a beautiful, code-styled scrolling canvas block
        st.code(st.session_state.doc_context, language="text", line_numbers=True)

    with right_deck:
        st.markdown("### 🧠 INTERACTIVE LOGIC EXECUTION")
        
        # Initialize Backend Chain
        llm = ChatOllama(model="qwen2.5:3b", temperature=0.1, num_predict=768)

        system_prompt = (
            "You are an interactive local AI Document Assistant.\n\n"
            "--- DOCUMENT START ---\n"
            f"{st.session_state.doc_context}\n"
            "--- DOCUMENT END ---\n\n"
            "Instructions:\n"
            "- Extract metrics, numbers, and risks explicitly.\n"
            "- Formatting requirement: Always format key technical fields, dates, and amounts in **bold bold** or use clear clean Markdown block quotes.\n"
            "- Termination: Always output exactly two follow-up recommendation prompts starting with '💡 Suggestion:'."
        )

        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{user_input}")
        ])

        # Chat canvas interface container
        chat_container = st.container(height=450, border=True)
        
        with chat_container:
            for message in st.session_state.chat_history:
                if isinstance(message, HumanMessage):
                    with st.chat_message("user", avatar="👤"):
                        st.markdown(message.content)
                elif isinstance(message, AIMessage):
                    with st.chat_message("assistant", avatar="🤖"):
                        st.markdown(message.content)

        # Chat Input Interface
        if user_input := st.chat_input("Query the analytics matrix..."):
            # Render user bubble immediately
            with chat_container:
                with st.chat_message("user", avatar="👤"):
                    st.markdown(user_input)

            # Generate Agent output stream
            with chat_container:
                with st.chat_message("assistant", avatar="🤖"):
                    with st.spinner("⚡ Interrogating local document models..."):
                        formatted_prompt = prompt_template.format_messages(
                            chat_history=st.session_state.chat_history,
                            user_input=user_input
                        )
                        response = llm.invoke(formatted_prompt)
                        st.markdown(response.content)

            # Record metrics state history
            st.session_state.chat_history.append(HumanMessage(content=user_input))
            st.session_state.chat_history.append(AIMessage(content=response.content))
            
            # Auto refresh to stick scroll to page bottom cleanly
            st.rerun()