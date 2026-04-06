import base64
import csv
import html
import io
import os
import re
from datetime import datetime
import streamlit.components.v1 as components

import streamlit as st
import streamlit.components.v1 as components

from rag_pipeline import ask_ai

st.set_page_config(layout="wide", page_title="Reporting Xpress")

def check_password():
    """Returns `True` if the user had the correct password."""
    password_secret = os.getenv("WEB_PASSWORD", "cihubsecure")
    
    def password_entered():
        if st.session_state["password"] == password_secret:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.markdown("### 🔐 Reporting Xpress \n Please enter the shared access password to proceed.")
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
        
    return False

if not check_password():
    st.stop()

st.markdown(
    """
    <button id="skip-to-chat" class="skip-link" style="top: -9999px; left: 20px;">
        Skip to Chat Input
    </button>
    """,
    unsafe_allow_html=True,
)


with st.sidebar:
    st.header("App Settings")

    dark_mode = st.toggle("Dark Mode", value=False, help="Toggle between dark and light themes.")
    transparency_mode = st.toggle(
        "Explain the Logic",
        value=True,
        help="Shows the reasoning path for every AI response.",
    )
    st.divider()

    st.subheader("Session Tools")
    st.markdown(
        "<p style='font-size: 0.85rem; margin-bottom: 0;'>Restore Chat History</p>",
        unsafe_allow_html=True,
    )
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")

    if uploaded_file is not None:
        if "history_loaded" not in st.session_state or st.session_state.history_loaded != uploaded_file.name:
            stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
            reader = csv.DictReader(stringio)
            loaded_messages = []
            for row in reader:
                if "Role" in row and "Message" in row:
                    loaded_messages.append(
                        {
                            "role": row["Role"].lower(),
                            "content": row["Message"],
                            "timestamp": row.get("Timestamp", ""),
                        }
                    )
            if loaded_messages:
                st.session_state.messages = loaded_messages + st.session_state.get("messages", [])
                st.session_state.history_loaded = uploaded_file.name
                st.rerun()

    st.write("")
    st.markdown(
        "<p style='font-size: 0.85rem; margin-bottom: 5px;'>Generate Strategy Memo</p>",
        unsafe_allow_html=True,
    )
    if st.button("Generate Memo", use_container_width=True):
        if "messages" in st.session_state and st.session_state.messages:
            with st.spinner("Drafting executive memo..."):
                history_lines = [
                    f"{m['role'].capitalize()}: {re.sub(r'<[^>]+>', '', m['content'])}"
                    for m in st.session_state.messages
                ]
                history_text = "\n".join(history_lines)
                memo_prompt = (
                    "You are a fundraising strategist writing an executive memo. Based on the following "
                    "conversation history, generate a professional 1-page Executive Summary. It MUST include "
                    "three sections: 1. Key Takeaways 2. Action Items 3. Recommended Metrics to Track. "
                    "Format it in clean, professional Markdown. Do not include your reasoning logic.\n\n"
                    f"Conversation History:\n{history_text}"
                )
                memo_result = ask_ai(memo_prompt, require_logic=False)
                st.session_state.executive_summary = memo_result["answer"]
        else:
            st.warning("Ask Rex a few questions first to generate a memo!")

    if "executive_summary" in st.session_state:
        st.download_button(
            label="Download Memo (.md)",
            data=st.session_state.executive_summary.encode("utf-8"),
            file_name=f"ReportingXpress_StrategyMemo_{datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.write("")
    if st.button("Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.session_state.sources = []
        st.session_state.confidences = []
        st.session_state.confidence = 100.0
        st.session_state.question_input = ""
        if "executive_summary" in st.session_state:
            del st.session_state.executive_summary
        st.rerun()

    st.divider()
    st.subheader("About Rex")
    st.markdown(
        """
        **Rex** is your intelligent fundraising strategist. Powered by advanced AI and securely connected to the
        **Reporting Xpress Knowledge Base**, Rex analyzes research, reports, and best practices to provide
        evidence-based recommendations.
        """
    )

    with st.expander("What can Rex do?"):
        st.markdown(
            """
            - **Identify Trends:** Spot patterns in lapsing donors or giving tiers.
            - **Campaign Strategy:** Suggest key metrics to track before your next push.
            - **Best Practices:** Recommend proven retention and engagement tactics based on industry research.
            """
        )

    with st.expander("Data & Privacy"):
        st.markdown(
            """
            Your queries are processed securely. Rex strictly uses the curated knowledge base provided by
            Reporting Xpress to ensure accurate, safe, and professional recommendations without hallucinating.
            """
        )

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.caption("Reporting Xpress AI Assistant v1.1")


def log_feedback(question, answer, feedback_type):
    file_exists = os.path.isfile("feedback.csv")
    with open("feedback.csv", mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Timestamp", "Question", "Answer", "Feedback"])
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([timestamp, question, answer, feedback_type])


def strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def infer_analysis_title(question):
    question_lower = (question or "").lower()
    if any(term in question_lower for term in ["retention", "lapsed", "lapsing", "attrition"]):
        return "Segment Retention Analysis"
    if "campaign" in question_lower:
        return "Campaign Readiness Review"
    if any(term in question_lower for term in ["upgrade", "major gift", "mid-level"]):
        return "Donor Upgrade Opportunity"
    if any(term in question_lower for term in ["ltv", "lifetime value"]):
        return "Donor Value Analysis"
    return "Donor Engagement Analysis"


def summarize_answer(answer, max_sentences=2):
    plain_text = strip_html(answer)
    if not plain_text:
        return "Ask a question to generate a recommendation."
    sentences = re.split(r"(?<=[.!?])\s+", plain_text)
    return " ".join(sentences[:max_sentences]).strip()


def extract_logic_details(logic_html):
    sections = {}
    patterns = {
        "diagnosis": r"label-diag.*?<div class=\"logic-detail\">(.*?)</div>",
        "evidence": r"label-evid.*?<div class=\"logic-detail\">(.*?)</div>",
        "strategy": r"label-strat.*?<div class=\"logic-detail\">(.*?)</div>",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, logic_html or "", re.DOTALL)
        sections[key] = strip_html(match.group(1)) if match else ""
    return sections


def build_selection_reason(question, logic_details, source_count):
    if logic_details.get("diagnosis"):
        reason = f"This surfaced because Rex identified {logic_details['diagnosis'].rstrip('.')}. "
    elif question:
        reason = f"This surfaced to answer your question about {question.rstrip('?')}. "
    else:
        reason = "This surfaced because the retrieved evidence aligned strongly with your latest question. "

    if logic_details.get("evidence"):
        reason += f"It was selected using the strongest overlap across these supporting findings: {logic_details['evidence'].rstrip('.')}. "

    if source_count:
        reason += f"The recommendation is grounded in {source_count} source{'s' if source_count != 1 else ''}, which helps keep the guidance evidence-based."

    return reason.strip()


def build_suggested_action(answer, logic_details):
    strategy = logic_details.get("strategy", "")
    summary = summarize_answer(answer, max_sentences=3)

    if strategy and summary:
        return f"{strategy.rstrip('.')} In practice, {summary[0].lower() + summary[1:] if len(summary) > 1 else summary}."
    if strategy:
        return strategy
    return summary


def get_latest_completed_exchange(messages):
    pending_question = messages[-1]["content"] if messages and messages[-1]["role"] == "user" else None
    for idx in range(len(messages) - 1, -1, -1):
        msg = messages[idx]
        if msg.get("role") != "assistant":
            continue
        question_text = msg.get("question")
        if not question_text:
            for prev_idx in range(idx - 1, -1, -1):
                if messages[prev_idx].get("role") == "user":
                    question_text = messages[prev_idx].get("content", "")
                    break
        if pending_question and question_text == pending_question:
            continue
        return question_text or "", msg
    return "", None


def render_chat_message(message, is_user):
    timestamp = html.escape(message.get("timestamp", ""))
    if is_user:
        body = html.escape(strip_html(message["content"])).replace("\n", "<br>")
        return f"""
        <div class="chat-row user">
            <div class="chat-avatar">Y</div>
            <div class="chat-bubble">
                <div class="bubble-text">{body}</div>
                <div class="chat-meta">{timestamp}</div>
            </div>
        </div>
        """

    body = (message.get("content", "") or "").replace("\n", "<br>")
    return f"""
    <div class="chat-row assistant">
        <div class="chat-bubble">
            <div class="bubble-text">{body}</div>
            <div class="chat-meta">{timestamp}</div>
        </div>
        <div class="chat-avatar assistant-avatar">R</div>
    </div>
    """


def get_base64_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return None


current_dir = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(current_dir, "reportingxpresslogo.jpg")
logo_base64 = get_base64_image(logo_path)

if logo_base64:
    header_logo_html = (
        f'<img src="data:image/jpeg;base64,{logo_base64}" '
        'style="height: 40px; width: auto; border-radius: 4px; vertical-align: middle;">'
    )
else:
    header_logo_html = '<span style="font-size: 1.35rem; font-weight: 700; color: white;">Reporting Xpress</span>'


# --- UPDATED THEMES TO MATCH FIGMA ---
if dark_mode:
    page_bg = "#0d1728"
    panel_bg = "#111d31"
    panel_alt_bg = "#16253f"
    text_primary = "#eef4ff"
    text_secondary = "#b9c7de"
    border_color = "rgba(133, 154, 189, 0.20)"
    user_bubble_bg = "#f8fbff"
    user_bubble_text = "#244265"
    assistant_bubble_bg = "linear-gradient(135deg, #0a5fd8 0%, #2b86ed 100%)"
    logic_bg = "rgba(255, 255, 255, 0.10)"
    logic_border = "rgba(255, 255, 255, 0.35)"
    logic_text = "#e4ecff"
    input_bg = "#eef4ff"
    source_bg = "rgba(255, 255, 255, 0.05)"
    stat_bg = "rgba(255, 255, 255, 0.06)"
    divider_color = "rgba(255, 255, 255, 0.10)"
    card_shadow = "0 18px 45px rgba(4, 16, 36, 0.35)"
    confidence_good = "#4dd38a"
    confidence_mid = "#f6c453"
    confidence_low = "#ff7b7b"
else:
    page_bg = "#f0f4f8" # Figma clean gray/blue backdrop
    panel_bg = "#ffffff" # Pure white cards
    panel_alt_bg = "#f8fafc" # Soft grey headers
    text_primary = "#1e293b" # Slate text
    text_secondary = "#64748b" # Muted slate text
    border_color = "rgba(15, 23, 42, 0.12)" # Faint, crisp border
    user_bubble_bg = "#ffffff"
    user_bubble_text = "#1e293b"
    assistant_bubble_bg = "linear-gradient(135deg, #0f62d1 0%, #2b86ed 100%)"
    logic_bg = "#f8fafc"
    logic_border = "rgba(43, 134, 237, 0.30)"
    logic_text = "#475569"
    input_bg = "#ffffff"
    source_bg = "#f1f5f9"
    stat_bg = "#ffffff"
    divider_color = "rgba(15, 23, 42, 0.08)"
    card_shadow = "0 8px 30px rgba(15, 23, 42, 0.04)" # Soft, modern shadow matching Figma
    confidence_good = "#10b981"
    confidence_mid = "#f59e0b"
    confidence_low = "#ef4444"


st.markdown(
    f"""
    <style>
    .block-container {{
        padding-top: 0 !important;
        padding-bottom: 2rem !important;
        max-width: 1440px !important;
    }}

    [data-testid="stHeader"] {{
        height: 0px !important;
    }}

    [data-testid="collapsedControl"] {{
        top: 85px !important;
        z-index: 999999 !important;
    }}

    .insight-box-body {{
        white-space: normal !important;
        word-wrap: break-word !important;
        line-height: 1.5 !important;
        overflow-wrap: break-word !important;
    }}

    body, .stApp, [data-testid="stAppViewContainer"] {{
        background: {page_bg} !important;
        color: {text_primary} !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
    }}

    h1, h2, h3, h4, h5, h6, p, span, div, label {{
        color: {text_secondary} !important;
    }}

    .topbar-shell {{
        width: 100vw;
        margin-left: calc(50% - 50vw);
        margin-top: 18px;
        background: linear-gradient(90deg, #0a57c8 0%, #2b6fbe 55%, #215796 100%);
        box-shadow: 0 10px 24px rgba(12, 51, 108, 0.18);
    }}

    .topbar-inner {{
        max-width: 1440px;
        margin: 0 auto;
        padding: 18px 32px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
    }}

    .brand-wrap {{
        display: flex;
        align-items: center;
        gap: 14px;
        min-height: 40px;
    }}

    .brand-name {{
        color: #ffffff !important;
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        white-space: nowrap;
    }}

    .topbar-title {{
        color: #ffffff !important;
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        text-align: right;
    }}

    .page-shell {{
        padding: 28px 8px 0 8px;
    }}

    .panel-heading {{
        color: {text_primary} !important;
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }}

    .panel-subheading {{
        color: {text_secondary} !important;
        font-size: 0.98rem;
        margin-bottom: 1rem;
    }}

    [data-testid="stVerticalBlockBorderWrapper"] {{
        background: {panel_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 16px !important;
        box-shadow: {card_shadow} !important;
        padding: 1rem 1.15rem !important;
    }}

    .dashboard-panel-column,
    .dashboard-panel-column-inner {{
        background: {panel_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 16px !important;
        box-shadow: {card_shadow} !important;
        padding: 1.2rem 1.3rem 1.35rem 1.3rem !important;
        overflow: hidden !important;
    }}

    [data-testid="stVerticalBlockBorderWrapper"] > div {{
        background: transparent !important;
    }}

    [data-testid="stTextInputRootElement"] > div {{
        min-height: auto !important;
        background: {input_bg} !important;
        border-radius: 12px !important;
    }}

    div[data-baseweb="input"] {{
        min-height: 58px !important;
        border-radius: 12px !important;
        background: {input_bg} !important;
    }}

    div[data-baseweb="input"] > div {{
        min-height: 58px !important;
        display: flex !important;
        align-items: center !important;
    }}

    [data-testid="stTextInputRootElement"] input {{
        background: {input_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 12px !important;
        color: {text_primary} !important;
        min-height: 56px !important;
        height: 56px !important;
        padding-top: 0.8rem !important;
        padding-bottom: 0.8rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        line-height: 1.4 !important;
        box-sizing: border-box !important;
        vertical-align: baseline !important;
        box-shadow: inset 0 1px 2px rgba(17, 40, 75, 0.04);
    }}

    div[data-baseweb="input"] input {{
        min-height: 58px !important;
        height: 58px !important;
        padding: 0 1rem !important;
        line-height: normal !important;
    }}

    [data-testid="stTextInputRootElement"] input::placeholder {{
        color: #8da0bb !important;
    }}

    .stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button {{
        border-radius: 10px !important;
        min-height: 44px !important;
        font-weight: 600 !important;
        border: 1px solid {border_color} !important;
        background: {panel_alt_bg} !important;
        color: {text_primary} !important;
        box-shadow: 0 4px 10px rgba(24, 56, 104, 0.06) !important;
    }}

    [data-testid="stFormSubmitButton"] button[kind="primary"] {{
        background: linear-gradient(135deg, #0a5fd8 0%, #2b86ed 100%) !important;
        color: #ffffff !important;
        border: none !important;
    }}

    .metric-strip {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.65rem;
        margin-bottom: 1rem;
    }}

    div[data-testid="stHorizontalBlock"].prompt-chip-row {{
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        padding-bottom: 0.4rem;
        margin-bottom: 0.5rem;
        scroll-behavior: smooth;
    }}

    div[data-testid="stHorizontalBlock"].prompt-chip-row::-webkit-scrollbar {{
        height: 8px;
    }}

    div[data-testid="stHorizontalBlock"].prompt-chip-row::-webkit-scrollbar-track {{
        background: {panel_alt_bg};
        border-radius: 999px;
    }}

    div[data-testid="stHorizontalBlock"].prompt-chip-row::-webkit-scrollbar-thumb {{
        background: rgba(43, 134, 237, 0.55);
        border-radius: 999px;
    }}

    div[data-testid="stHorizontalBlock"].prompt-chip-row > div {{
        min-width: 220px;
        flex: 0 0 220px !important;
    }}

    .metric-tile {{
        background: {stat_bg};
        border: 1px solid {border_color};
        border-radius: 12px;
        padding: 0.85rem 0.9rem;
    }}

    .metric-value {{
        display: block;
        color: {text_primary};
        font-size: 1.3rem;
        font-weight: 700;
    }}

    .metric-label {{
        display: block;
        color: {text_secondary};
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-top: 0.1rem;
    }}

    .section-divider {{
        border-top: 1px solid {divider_color};
        color: {text_primary} !important;
        font-size: 1.45rem;
        font-weight: 700;
        margin: 1.6rem 0 1rem 0;
        padding-top: 0.9rem;
    }}

    .empty-panel {{
        background: {panel_alt_bg};
        border: 1px dashed {border_color};
        border-radius: 14px;
        padding: 1rem 1.1rem;
        color: {text_secondary};
    }}

    .chat-row {{
        display: flex;
        align-items: flex-end;
        gap: 12px;
        margin-bottom: 16px;
    }}

    .chat-row.assistant {{
        justify-content: flex-end;
    }}

    .chat-avatar {{
        width: 38px;
        height: 38px;
        border-radius: 999px;
        background: {panel_alt_bg};
        border: 1px solid {border_color};
        color: {text_secondary} !important;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        flex-shrink: 0;
    }}

    .assistant-avatar {{
        background: linear-gradient(135deg, #eaf2ff 0%, #f8fbff 100%);
        color: #2665bc !important;
    }}

    .chat-bubble {{
        max-width: 82%;
        border-radius: 16px;
        padding: 0.95rem 1rem;
        border: 1px solid {border_color};
        box-shadow: 0 10px 24px rgba(20, 50, 95, 0.06);
    }}

    .chat-row.user .chat-bubble {{
        background: {user_bubble_bg};
        color: {user_bubble_text} !important;
        border-top-left-radius: 6px;
    }}

    .chat-row.assistant .chat-bubble {{
        background: {assistant_bubble_bg};
        color: #ffffff !important;
        border: none;
        border-top-right-radius: 6px;
    }}

    .chat-row.assistant .chat-bubble p,
    .chat-row.assistant .chat-bubble span,
    .chat-row.assistant .chat-bubble div,
    .chat-row.assistant .chat-bubble strong {{
        color: #ffffff !important;
    }}

    .bubble-text {{
        color: inherit !important;
        font-size: 0.98rem;
        line-height: 1.6;
    }}

    .chat-meta {{
        color: inherit !important;
        opacity: 0.72;
        font-size: 0.75rem;
        margin-top: 0.5rem;
    }}

    .logic-box {{
        background: {logic_bg} !important;
        border: 1px solid {logic_border} !important;
        border-radius: 12px !important;
        padding: 0.9rem 1rem !important;
        margin: 0.25rem 0 1rem 0 !important;
    }}

    .logic-header {{
        color: {logic_text} !important;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 700;
        margin-bottom: 0.65rem;
    }}

    .logic-step {{
        border-left: 2px solid {logic_border};
        padding-left: 0.85rem;
        margin-bottom: 0.7rem;
    }}

    .logic-detail {{
        color: {logic_text} !important;
        line-height: 1.5;
    }}

    .thinking-card {{
        background: {panel_alt_bg};
        border: 1px solid {border_color};
        border-radius: 14px;
        padding: 0.95rem 1rem;
        margin-bottom: 1.3rem;
        display: flex;
        align-items: center;
        gap: 0.8rem;
        color: {text_primary};
    }}

    .thinking-dot {{
        width: 14px;
        height: 14px;
        border-radius: 999px;
        background: #2b86ed;
        box-shadow: 0 0 0 6px rgba(43, 134, 237, 0.18);
        animation: pulse-dot 1.2s ease-in-out infinite;
    }}

    @keyframes pulse-dot {{
        0%, 100% {{ transform: scale(1); opacity: 1; }}
        50% {{ transform: scale(0.82); opacity: 0.72; }}
    }}

    /* --- UNIFIED INSIGHTS GROUP CSS TO MATCH FIGMA --- */
    .insight-group {{
        border: 1px solid {border_color};
        border-radius: 12px;
        overflow: hidden;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.02);
    }}

    .insight-box {{
        background: {panel_bg};
        border-bottom: 1px solid {border_color};
        margin-bottom: 0;
        border-radius: 0;
    }}
    
    .insight-box:last-child {{
        border-bottom: none;
    }}

    .insight-box-header {{
        background: {panel_alt_bg};
        padding: 0.75rem 1.1rem;
        font-size: 0.9rem;
        font-weight: 600;
        color: {text_secondary} !important;
    }}

    .insight-box-body {{
        padding: 1.1rem;
        color: {text_primary} !important;
    }}

    .insight-box-body strong {{
        color: {text_primary} !important;
    }}

    .insight-box-body ul {{
        margin: 0;
        padding-left: 1.2rem;
    }}

    .confidence-band {{
        border-top: 1px solid {divider_color};
        padding-top: 1rem;
        margin-top: 1rem;
    }}

    .confidence-label {{
        color: {text_primary} !important;
        font-weight: 700;
        font-size: 1.1rem;
    }}

    .confidence-value {{
        font-weight: 800;
        font-size: 1.4rem;
    }}

    .source-chip {{
        display: inline-block;
        background: {source_bg};
        border: 1px solid {border_color};
        border-radius: 999px;
        padding: 0.38rem 0.7rem;
        margin: 0 0.45rem 0.45rem 0;
        color: {text_primary} !important;
        font-size: 0.84rem;
    }}

    .skip-link {{
        position: fixed !important;
        background: #0a5fd8 !important;
        color: white !important;
        padding: 12px 20px !important;
        border-radius: 8px !important;
        z-index: 999999 !important;
        font-weight: 700 !important;
        border: 2px solid white !important;
        cursor: pointer !important;
        font-family: inherit !important;
        font-size: 1rem !important;
    }}

    .skip-link:focus {{
        top: 20px !important;
        outline: 3px solid #8fd0ff !important;
    }}

    *:focus-visible {{
        outline: 3px solid #7cc7ff !important;
        outline-offset: 2px !important;
        border-radius: 6px !important;
    }}

    section[data-testid="stSidebar"] {{
        background: {panel_bg} !important;
        border-right: 1px solid {border_color};
    }}

    [data-testid="stExpander"] {{
        border: 1px solid {border_color} !important;
        border-radius: 12px !important;
        background: {panel_alt_bg} !important;
    }}

    @media (max-width: 900px) {{
        .topbar-inner {{
            padding: 16px 18px;
            align-items: flex-start;
            flex-direction: column;
        }}

        .brand-name {{
            font-size: 1.5rem;
        }}

        .topbar-title {{
            font-size: 1.5rem;
            text-align: left;
        }}

        .metric-strip {{
            grid-template-columns: 1fr;
        }}

        .chat-bubble {{
            max-width: 100%;
        }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    f"""
    <div class="topbar-shell">
        <div class="topbar-inner">
            <div class="brand-wrap">{header_logo_html}<span class="brand-name">Reporting Xpress</span></div>
            <div class="topbar-title">AI Fundraising Assistant</div>
        </div>
    </div>
    <div class="page-shell"></div>
    """,
    unsafe_allow_html=True,
)


if "messages" not in st.session_state:
    st.session_state.messages = []
if "confidences" not in st.session_state:
    st.session_state.confidences = []
if "sources" not in st.session_state:
    st.session_state.sources = []
if "confidence" not in st.session_state:
    st.session_state.confidence = 100.0
if "question_input" not in st.session_state:
    st.session_state.question_input = ""


chat_col, insight_col = st.columns([1.2, 1], gap="large")

with chat_col:
    st.markdown("<div id='chat-panel-marker'></div>", unsafe_allow_html=True)
    # --- FIX: Moved ENTIRE left side into the st.container to create ONE unified card ---
    with st.container(border=True):
        st.markdown("<div class='panel-heading'>Ask Your Question</div>", unsafe_allow_html=True)

        chip_prompts = [
            ("Best strategies for lapsed donors?", "What are the best strategies to re-engage lapsed donors?"),
            ("Key metrics before a campaign?", "What are the key metrics to track before launching a capital campaign?"),
            ("Interpreting donor engagement?", "How should I interpret donor engagement trends across recent campaigns?"),
            ("Upgrade mid-level donors?", "How can we effectively upgrade mid-level donors to major gifts?"),
            ("Maximize donor lifetime value?", "What factors most heavily influence donor lifetime value (LTV)?"),
        ]
        selected_prompt = None
        chip_cols = st.columns(5)
        for idx, (label, value) in enumerate(chip_prompts):
            if chip_cols[idx].button(label, use_container_width=True, key=f"chip_{idx}"):
                selected_prompt = value

        with st.form("question_form", clear_on_submit=True):
            input_col, send_col = st.columns([6.4, 1.0])
            with input_col:
                typed_prompt = st.text_input(
                    "Ask Rex a question",
                    key="question_input",
                    label_visibility="collapsed",
                    placeholder="Initializing AI...",
                )
            with send_col:
                submitted = st.form_submit_button("Send", use_container_width=True, type="primary")

        components.html(
            """
            <script>
            const doc = window.parent.document;
            
            // Typewriter Effect Variables
            const prompts = [
                "Ask about donor performance, metrics, or risk...",
                "Which donors are about to lapse?",
                "What is our donor retention rate?",
                "How are we doing compared to last year?",
                "Who are our best upgrade prospects?",
                "Show me a dashboard for my top donors."
            ];
            
            let textIndex = 0;
            let charIndex = 0;
            let isDeleting = false;
            
            function typeWriter() {
                // Target the Streamlit text input box
                const input = doc.querySelector('input[aria-label="Ask Rex a question"]')
                    || doc.querySelector('[data-testid="stTextInputRootElement"] input');
                
                // If the UI hasn't rendered it yet, wait 500ms and try again
                if (!input) {
                    setTimeout(typeWriter, 500);
                    return;
                }
                
                // Don't animate if user is interacting
                if (doc.activeElement === input || input.value.length > 0) {
                   setTimeout(typeWriter, 2000);
                   return;
                }
                
                const currentText = prompts[textIndex];
                
                // Handle Typing and Deleting
                if (isDeleting) {
                    input.placeholder = currentText.substring(0, charIndex - 1);
                    charIndex--;
                } else {
                    input.placeholder = currentText.substring(0, charIndex + 1);
                    charIndex++;
                }
                
                // Determine Speed
                let typeSpeed = 50; // Typing speed (ms)
                if (isDeleting) typeSpeed = 25; // Deleting is twice as fast
                
                // Handle Pauses at the end of words or when empty
                if (!isDeleting && charIndex === currentText.length) {
                    typeSpeed = 2500; // Pause for 2.5s so the user can read it
                    isDeleting = true;
                } else if (isDeleting && charIndex === 0) {
                    isDeleting = false;
                    textIndex = (textIndex + 1) % prompts.length; // Move to next prompt
                    typeSpeed = 500; // Brief pause before typing starts again
                }
                
                setTimeout(typeWriter, typeSpeed);
            }

            function bindSkip() {
                const skipChat = doc.getElementById('skip-to-chat');
                const questionInput = doc.querySelector('input[aria-label="Ask Rex a question"]')
                    || doc.querySelector('[data-testid="stTextInputRootElement"] input');
                if (skipChat && questionInput && !skipChat.dataset.bound) {
                    skipChat.dataset.bound = "true";
                    const focusInput = (e) => {
                        e.preventDefault();
                        questionInput.focus();
                    };
                    skipChat.onclick = focusInput;
                    skipChat.onkeydown = function(e) {
                        if (e.key === 'Enter' || e.key === ' ') focusInput(e);
                    };
                }
            }
            function enablePromptScroll() {
                const blocks = doc.querySelectorAll('div[data-testid="stHorizontalBlock"]');
                blocks.forEach((block) => {
                    if (block.children.length >= 5) {
                        block.classList.add('prompt-chip-row');
                    }
                });
            }
            enablePromptScroll();
            setInterval(bindSkip, 500);
            setInterval(enablePromptScroll, 500);
            
            // Start typewriter effect
            typeWriter();
            </script>
            """,
            height=0,
            width=0,
        )

        prompt = None
        if selected_prompt:
            prompt = selected_prompt
        elif submitted and typed_prompt.strip():
            prompt = typed_prompt.strip()

        if prompt:
            timestamp = datetime.now().strftime("%b %d, %Y - %I:%M %p")
            st.session_state.messages.append({"role": "user", "content": prompt, "timestamp": timestamp})

        st.markdown("<div class='section-divider'>Conversation History</div>", unsafe_allow_html=True)

        visible_count = 4
        cutoff = max(0, len(st.session_state.messages) - visible_count)
        visible_messages = st.session_state.messages[cutoff:]
        processing_user_message = None
        render_start_idx = cutoff

        if visible_messages and visible_messages[-1]["role"] == "user":
            processing_user_message = visible_messages[-1]
            visible_messages = []

        if processing_user_message:
            st.markdown(render_chat_message(processing_user_message, True), unsafe_allow_html=True)

        if not st.session_state.messages:
            st.markdown(
                "<div class='empty-panel'>Start with a question and Rex will build a recommended analysis here.</div>",
                unsafe_allow_html=True,
            )

        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            thinking_placeholder = st.empty()
            thinking_placeholder.markdown(
                """
                <div class="thinking-card">
                    <div class="thinking-dot"></div>
                    <div>Analyzing donor patterns and selecting the best supporting sources...</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            thinking_placeholder = None

        conversation_blocks = []
        visible_index = 0
        while visible_index < len(visible_messages):
            actual_idx = render_start_idx + visible_index
            current_msg = visible_messages[visible_index]

            if current_msg["role"] == "user":
                block = [(actual_idx, current_msg)]
                if visible_index + 1 < len(visible_messages) and visible_messages[visible_index + 1]["role"] == "assistant":
                    block.append((actual_idx + 1, visible_messages[visible_index + 1]))
                    visible_index += 2
                else:
                    visible_index += 1
            else:
                block = [(actual_idx, current_msg)]
                visible_index += 1

            conversation_blocks.append(block)

        for block in reversed(conversation_blocks):
            for i, msg in block:
                is_user = msg["role"] == "user"
                st.markdown(render_chat_message(msg, is_user), unsafe_allow_html=True)

                if not is_user:
                    if transparency_mode and "logic" in msg:
                        st.markdown(
                            f"<div class='logic-box'><div class='logic-header'>Reasoning Path</div>{msg['logic']}</div>",
                            unsafe_allow_html=True,
                        )

                    q_idx = i - 1
                    q_text = st.session_state.messages[q_idx]["content"] if q_idx >= 0 else "N/A"
                    feedback_col1, feedback_col2, _ = st.columns([0.14, 0.14, 0.72])
                    with feedback_col1:
                        if st.button("\U0001F44D", key=f"up_{i}", use_container_width=True):
                            log_feedback(q_text, msg["content"], "Thumbs Up")
                            st.toast("Feedback logged.")
                    with feedback_col2:
                        if st.button("\U0001F44E", key=f"down_{i}", use_container_width=True):
                            log_feedback(q_text, msg["content"], "Thumbs Down")
                            st.toast("Feedback recorded.")

        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            contextual_prompt = prompt
            if len(st.session_state.messages) > 1:
                history_lines = [
                    f"{m['role'].capitalize()}: {strip_html(m['content'])}"
                    for m in st.session_state.messages[-5:-1]
                ]
                history_text = "\n".join(history_lines)
                contextual_prompt = f"Previous Chat Context:\n{history_text}\n\nCurrent User Question: {prompt}"

            result = ask_ai(contextual_prompt, require_logic=transparency_mode)
            thinking_placeholder.empty()

            logic_steps = result.get(
                "logic",
                "<div class='logic-step'><div class='logic-detail'>Parsing complete.</div></div>",
            )
            formatted_answer = re.sub(r"\[(.*?)\]", r"<span style='font-weight: 700;'>[\1]</span>", result["answer"])

            timestamp = datetime.now().strftime("%b %d, %Y - %I:%M %p")
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": formatted_answer,
                    "timestamp": timestamp,
                    "logic": logic_steps,
                    "sources": result.get("sources", []),
                    "question": prompt,
                }
            )
            st.session_state.sources = result.get("sources", [])
            st.session_state.confidences.append(result.get("avg_confidence", 100))
            st.session_state.confidence = sum(st.session_state.confidences) / len(st.session_state.confidences)
            st.rerun()

        if cutoff > 0:
            with st.expander("View Previous Messages", expanded=False):
                for msg in st.session_state.messages[:cutoff]:
                    role_name = "You" if msg["role"] == "user" else "Rex"
                    safe_role = html.escape(role_name)
                    safe_body = html.escape(strip_html(msg["content"]))
                    safe_time = html.escape(msg.get("timestamp", ""))
                    st.markdown(
                        f"**{safe_role}:** {safe_body}  \n"
                        f"<span style='color:{text_secondary}; font-size:0.82rem;'>{safe_time}</span>",
                        unsafe_allow_html=True,
                    )

        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerow(["Timestamp", "Role", "Message"])
        for msg in st.session_state.messages:
            csv_writer.writerow([msg.get("timestamp", "N/A"), msg["role"].capitalize(), strip_html(msg["content"])])

        st.download_button(
            label="Download Chat History (CSV)",
            data=csv_buffer.getvalue().encode("utf-8"),
            file_name=f"ReportingXpress_ChatHistory_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )


with insight_col:
    st.markdown("<div id='insight-panel-marker'></div>", unsafe_allow_html=True)
    is_processing = bool(st.session_state.messages and st.session_state.messages[-1]["role"] == "user")
    latest_user = next((m for m in reversed(st.session_state.messages) if m["role"] == "user"), None)
    latest_question = strip_html(latest_user["content"]) if latest_user else ""
    completed_question, latest_assistant = get_latest_completed_exchange(st.session_state.messages)
    latest_answer = latest_assistant["content"] if latest_assistant else ""
    latest_logic = latest_assistant.get("logic", "") if latest_assistant else ""
    logic_details = extract_logic_details(latest_logic)
    action_summary = build_suggested_action(latest_answer, logic_details)
    has_fresh_answer = bool(latest_assistant and not is_processing and completed_question == latest_question)
    source_list = latest_assistant.get("sources", []) if has_fresh_answer else []
    confidence_value = st.session_state.get("confidence", 100.0)
    user_queries = sum(1 for msg in st.session_state.messages if msg.get("role") == "user")
    source_count = len(source_list) if has_fresh_answer else 0

    if confidence_value >= 80:
        confidence_label = "High"
        confidence_color = confidence_good
        confidence_symbol = "^"
    elif confidence_value >= 60:
        confidence_label = "Medium"
        confidence_color = confidence_mid
        confidence_symbol = ">"
    else:
        confidence_label = "Low"
        confidence_color = confidence_low
        confidence_symbol = "v"

    with st.container(border=True):
        st.markdown("<div class='panel-heading'>Analytics Insights</div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="metric-strip">
                <div class="metric-tile">
                    <span class="metric-value">{user_queries}</span>
                    <span class="metric-label">Queries This Session</span>
                </div>
                <div class="metric-tile">
                    <span class="metric-value">{confidence_value:.1f}%</span>
                    <span class="metric-label">Average Confidence</span>
                </div>
                <div class="metric-tile">
                    <span class="metric-value">{source_count}</span>
                    <span class="metric-label">Sources Retrieved</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # --- FIX: Wrapped all insight boxes in an insight-group to match Figma list style ---
        if latest_user and has_fresh_answer:
            selection_reason = build_selection_reason(latest_question, logic_details, source_count)
            source_chips = "".join(
                f"<span class='source-chip'>{html.escape(source['id'])}</span>"
                for source in source_list[:4]
            )
            if not source_chips:
                source_chips = f"<span style='color:{text_secondary};'>Sources will appear after a question is asked.</span>"

            st.markdown(
                f"""
                <div class="insight-group">
                    <div class="insight-box">
                        <div class="insight-box-header">Recommended Analytics</div>
                        <div class="insight-box-body">
                            <strong>{html.escape(infer_analysis_title(latest_question))}</strong>
                        </div>
                    </div>
                    <div class="insight-box">
                        <div class="insight-box-header">Why This Was Selected</div>
                        <div class="insight-box-body">{selection_reason}</div>
                    </div>
                    <div class="insight-box">
                        <div class="insight-box-header">Suggested Action</div>
                        <div class="insight-box-body">
                            {html.escape(action_summary)}
                        </div>
                    </div>
                    <div class="insight-box">
                        <div class="insight-box-header">Supporting Sources</div>
                        <div class="insight-box-body">{source_chips}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif latest_user and is_processing:
            st.markdown(
                f"""
                <div class="insight-group">
                    <div class="insight-box">
                        <div class="insight-box-header">Recommended Analytics</div>
                        <div class="insight-box-body">
                            <strong>{html.escape(infer_analysis_title(latest_question))}</strong>
                        </div>
                    </div>
                    <div class="insight-box">
                        <div class="insight-box-header">Why This Was Selected</div>
                        <div class="insight-box-body">
                            Rex is generating guidance for your latest question: "{html.escape(latest_question)}".
                        </div>
                    </div>
                    <div class="insight-box">
                        <div class="insight-box-header">Suggested Action</div>
                        <div class="insight-box-body">
                            Wait for the current answer to finish generating. This section will update with tailored next steps for the newest question.
                        </div>
                    </div>
                    <div class="insight-box">
                        <div class="insight-box-header">Supporting Sources</div>
                        <div class="insight-box-body">
                            Sources for the newest question will appear here after Rex finishes the current response.
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="empty-panel">
                    Ask a question to populate the recommended analytics, action summary, and supporting sources.
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(
            f"""
            <div class="confidence-band">
                <div class="confidence-label">AI Confidence Level</div>
                <div class="confidence-value" style="color:{confidence_color};">
                    {confidence_label} {confidence_symbol} ({confidence_value:.1f}%)
                </div>
                <div style="margin-top:0.25rem;">Based on relevant data retrieved.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if has_fresh_answer and source_list:
            with st.expander("View Source Excerpts", expanded=False):
                for source in source_list:
                    st.markdown(
                        f"**{html.escape(source['id'])}** \n{html.escape(source['text'][:300])}...",
                        unsafe_allow_html=True,
                    )

components.html(
    """
    <script>
    const doc = window.parent.document;

    function attachPanelClasses() {
        const markerMap = {
            'chat-panel-marker': 'dashboard-panel-column',
            'insight-panel-marker': 'dashboard-panel-column'
        };

        Object.entries(markerMap).forEach(([markerId, className]) => {
            const marker = doc.getElementById(markerId);
            if (!marker) return;
            const column = marker.closest('div[data-testid="column"]');
            if (column) {
                column.classList.add(className);
                if (column.firstElementChild) {
                    column.firstElementChild.classList.add(className + '-inner');
                }
            }
        });
    }

    attachPanelClasses();
    setInterval(attachPanelClasses, 500);
    </script>
    """,
    height=0,
    width=0,
)