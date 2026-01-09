"""
Streamlit UI for Azure GenAI Accelerator.

Provides a user interface for:
- Submitting input data for AI analysis
- Viewing analysis results
- Reviewing historical results

Implements:
- Mock Identity Provider for RBAC/ABAC demonstration
- Role-based access control for actions
- Attribute-based filtering for data

Run with: streamlit run app/main.py
"""

import streamlit as st

from app.database import init_db, get_session
from app.models import RequestCreate, AnalysisResult
from app.services.processor import Processor
from app.services.auth_mock import (
    get_all_users,
    get_current_user,
    UserProfile,
    Permission,
    Group,
)


# Page configuration
st.set_page_config(
    page_title="Azure GenAI Accelerator",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .score-low { 
        background-color: #d4edda; 
        padding: 1rem; 
        border-radius: 0.5rem; 
        border-left: 4px solid #28a745;
    }
    .score-medium { 
        background-color: #fff3cd; 
        padding: 1rem; 
        border-radius: 0.5rem;
        border-left: 4px solid #ffc107;
    }
    .score-high { 
        background-color: #f8d7da; 
        padding: 1rem; 
        border-radius: 0.5rem;
        border-left: 4px solid #dc3545;
    }
    .score-critical { 
        background-color: #721c24; 
        color: white;
        padding: 1rem; 
        border-radius: 0.5rem;
        border-left: 4px solid #491217;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    .user-badge {
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        font-size: 0.85rem;
        margin-bottom: 0.5rem;
    }
    .role-admin { background-color: #6f42c1; color: white; }
    .role-senior_analyst { background-color: #007bff; color: white; }
    .role-analyst { background-color: #28a745; color: white; }
    .role-viewer { background-color: #6c757d; color: white; }
</style>
""", unsafe_allow_html=True)


def get_score_color(score: int | None) -> str:
    """Returns color code for score level."""
    if score is None:
        return "#007bff"  # Blue for chat mode (no score)
    if score >= 76:
        return "#721c24"  # Critical
    elif score >= 51:
        return "#dc3545"  # High
    elif score >= 26:
        return "#ffc107"  # Medium
    else:
        return "#28a745"  # Low


def get_score_level(score: int | None) -> str:
    """Returns level string for score."""
    if score is None:
        return "CHAT"  # For chat mode
    if score >= 76:
        return "CRITICAL"
    elif score >= 51:
        return "HIGH"
    elif score >= 26:
        return "MEDIUM"
    else:
        return "LOW"


def get_role_color(role: str) -> str:
    """Returns color for user role."""
    colors = {
        "admin": "#6f42c1",
        "senior_analyst": "#007bff",
        "analyst": "#28a745",
        "viewer": "#6c757d",
    }
    return colors.get(role, "#6c757d")


def render_feedback_section(result_id: int, current_user: UserProfile):
    """
    Render the Human Feedback section for Data Flywheel.
    
    This implements Human-in-the-Loop evaluation for model improvement.
    Collected feedback enables:
    - Building "Golden Dataset" for model evaluation
    - Error analysis to understand model failures
    - Fine-tuning data collection
    """
    with st.expander("🕵️ Human Verification (Data Flywheel)", expanded=True):
        st.markdown(
            "**Help improve the model.** Is this analysis correct?\n\n"
            "_Your feedback builds our 'Golden Dataset' for model evaluation._"
        )
        
        col1, col2 = st.columns(2)
        
        # Use unique keys based on result_id
        with col1:
            if st.button("👍 Correct", key=f"feedback_pos_{result_id}", use_container_width=True):
                try:
                    with get_session() as session:
                        processor = Processor(session, user=current_user)
                        processor.submit_feedback(result_id, feedback=True)
                    st.success("✅ Thank you! Marked as correct. Data saved for model improvement.")
                except Exception as e:
                    st.error(f"Failed to save feedback: {e}")
        
        with col2:
            if st.button("👎 Incorrect", key=f"feedback_neg_{result_id}", use_container_width=True):
                st.session_state[f"show_feedback_form_{result_id}"] = True
        
        # Show feedback form if negative feedback selected
        if st.session_state.get(f"show_feedback_form_{result_id}", False):
            with st.form(f"feedback_form_{result_id}"):
                feedback_comment = st.text_area(
                    "What was wrong? (optional)",
                    placeholder="e.g., Score too high, wrong categories identified...",
                    help="Your explanation helps with Error Analysis",
                )
                
                if st.form_submit_button("Submit Feedback"):
                    try:
                        with get_session() as session:
                            processor = Processor(session, user=current_user)
                            processor.submit_feedback(
                                result_id,
                                feedback=False,
                                comment=feedback_comment if feedback_comment else None,
                            )
                        st.warning("📝 Recorded as error. Will be reviewed by expert.")
                        st.session_state[f"show_feedback_form_{result_id}"] = False
                    except Exception as e:
                        st.error(f"Failed to save feedback: {e}")


def render_similar_cases(result: AnalysisResult, current_user: UserProfile):
    """
    Render similar historical cases using RAG.
    
    Displays cases with similar content/outcomes to help users
    make informed decisions based on historical patterns.
    Includes RAG trace for debugging and transparency.
    
    Args:
        result: The current AnalysisResult to find similar cases for
        current_user: Current user for ABAC filtering
    """
    with st.expander("📚 Similar Historical Cases (RAG)", expanded=False):
        try:
            with get_session() as session:
                processor = Processor(session, user=current_user)
                
                # Check if RAG is enabled
                if not processor.is_rag_enabled():
                    st.info(
                        "🔌 **RAG is disabled.**\n\n"
                        "Set `RAG_ENABLED=true` in environment to enable "
                        "similar case search using vector embeddings."
                    )
                    return
                
                # Find similar cases with trace
                similar_cases, rag_trace = processor.find_similar_cases(
                    result, 
                    limit=3,
                    min_similarity=0.3,  # 30% minimum similarity threshold
                )
                
                if not similar_cases:
                    st.info(
                        "No similar cases found above the similarity threshold (30%).\n\n"
                        "Similar cases will appear here as more analyses are performed "
                        "and embeddings are generated."
                    )
                    # Show trace even when no results for debugging
                    with st.expander("🔍 RAG Trace (Debug)", expanded=False):
                        st.json(rag_trace.to_dict())
                    return
                
                st.caption(
                    f"Found **{len(similar_cases)}** similar case(s) "
                    f"(threshold: ≥30% similarity)"
                )
                
                # Display each similar case with similarity score
                for i, similar_result in enumerate(similar_cases, 1):
                    similar = similar_result.result
                    similarity_pct = similar_result.similarity_pct
                    
                    score_color = get_score_color(similar.score)
                    score_level = get_score_level(similar.score)
                    
                    # Color for similarity badge
                    if similarity_pct >= 70:
                        sim_color = "#28a745"  # Green - high similarity
                    elif similarity_pct >= 50:
                        sim_color = "#ffc107"  # Yellow - medium
                    else:
                        sim_color = "#6c757d"  # Gray - low
                    
                    st.markdown(f"---")
                    
                    # Header with similarity badge
                    st.markdown(
                        f"**Case #{similar.id}** | "
                        f'<span style="background-color: {sim_color}; color: white; '
                        f'padding: 2px 8px; border-radius: 4px; font-size: 0.85em;">'
                        f'{similarity_pct:.0f}% similar</span> | '
                        f"Score: **{similar.score}** ({score_level})",
                        unsafe_allow_html=True,
                    )
                    
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        st.markdown(
                            f'<div style="background-color: {score_color}22; '
                            f'border-left: 3px solid {score_color}; padding: 0.5rem; '
                            f'border-radius: 0.25rem;">'
                            f'<strong style="color: {score_color};">{similar.score}</strong>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        st.caption(f"Group: {similar.group}")
                        if similar.created_at:
                            st.caption(f"{similar.created_at.strftime('%Y-%m-%d')}")
                    
                    with col2:
                        # Categories
                        if similar.categories:
                            cats = ", ".join(similar.categories[:3])
                            if len(similar.categories) > 3:
                                cats += f" (+{len(similar.categories) - 3} more)"
                            st.markdown(f"**Categories:** {cats}")
                        
                        # Truncated summary
                        summary_preview = similar.summary[:200]
                        if len(similar.summary) > 200:
                            summary_preview += "..."
                        st.markdown(f"*{summary_preview}*")
                        
                        # Feedback status if available
                        if similar.human_feedback is not None:
                            feedback_icon = "👍" if similar.human_feedback else "👎"
                            st.caption(f"Human verdict: {feedback_icon}")
                
                # RAG Trace for debugging
                with st.expander("🔍 RAG Trace (Debug)", expanded=False):
                    st.caption(
                        "Details of how similar cases were found. "
                        "Shows embedding model, similarity scores, and filtering."
                    )
                    st.json(rag_trace.to_dict())
                
        except Exception as e:
            st.warning(f"⚠️ Could not load similar cases: {e}")


def init_session_state():
    """Initialize Streamlit session state."""
    if "db_initialized" not in st.session_state:
        try:
            init_db()
            st.session_state.db_initialized = True
        except Exception as e:
            st.error(f"Failed to initialize database: {e}")
            st.session_state.db_initialized = False
    
    # Initialize selected user (default to analyst_a for demo)
    if "selected_user_key" not in st.session_state:
        st.session_state.selected_user_key = "analyst_a"


def get_current_user_from_session() -> UserProfile:
    """Get the currently selected user from session state."""
    return get_current_user(st.session_state.selected_user_key)


def render_identity_simulator():
    """Render the Identity Simulator in sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.header("🔐 Identity Simulator")
    st.sidebar.caption("In Azure: Entra ID. Locally: Mock users for RBAC/ABAC demo.")
    
    users = get_all_users()
    
    # User selection dropdown
    selected_key = st.sidebar.selectbox(
        "Login as:",
        options=list(users.keys()),
        index=list(users.keys()).index(st.session_state.selected_user_key),
        format_func=lambda x: f"{users[x].username} ({users[x].role.value})",
        key="user_selector",
    )
    
    # Update session state
    st.session_state.selected_user_key = selected_key
    current_user = users[selected_key]
    
    # Display current user info
    role_color = get_role_color(current_user.role.value)
    st.sidebar.markdown(
        f'<div style="background-color: {role_color}; color: white; padding: 0.5rem; '
        f'border-radius: 0.5rem; text-align: center; font-weight: bold;">'
        f'{current_user.role.value.upper()}</div>',
        unsafe_allow_html=True,
    )
    
    # Show user attributes (ABAC context)
    with st.sidebar.expander("📋 User Claims (ABAC)", expanded=False):
        st.json({
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role.value,
            "group": current_user.group.value,
            "permissions": [p.value for p in Permission if current_user.has_permission(p)],
        })
    
    # Show access summary
    st.sidebar.markdown("**Access Level:**")
    if current_user.has_permission(Permission.VIEW_ALL_GROUPS):
        st.sidebar.success("🌍 All Groups")
    else:
        st.sidebar.info(f"📍 {current_user.group.value} only")
    
    if current_user.has_permission(Permission.ANALYZE):
        st.sidebar.success("✅ Can Analyze")
    else:
        st.sidebar.warning("🚫 View Only")
    
    if current_user.has_permission(Permission.VIEW_SENSITIVE):
        st.sidebar.success("🔴 High Score Visible")
    else:
        st.sidebar.warning("🟡 Limited to <70 score")
    
    return current_user


def render_sidebar(current_user: UserProfile):
    """Render sidebar navigation."""
    with st.sidebar:
        st.title("🚀 GenAI Accelerator")
        
        page = st.radio(
            "Navigation",
            ["📝 New Analysis", "📊 Dashboard", "🔬 Evaluation", "ℹ️ About"],
            label_visibility="collapsed",
        )
        
        st.markdown("---")
        st.caption("Azure GenAI Accelerator")
        st.caption("v1.0.0 | Template Edition")
        
        return page


def render_new_analysis(current_user: UserProfile):
    """Render the new analysis form."""
    st.header("📝 AI-Powered Analysis")
    
    # RBAC check: Can user analyze?
    if not current_user.has_permission(Permission.ANALYZE):
        st.error(
            f"🚫 **Access Denied**\n\n"
            f"Your role ({current_user.role.value}) does not have permission to analyze.\n"
            f"Please contact an administrator to upgrade your access."
        )
        st.info("💡 Try switching to 'Carol Analyst' or 'Alice Administrator' in the Identity Simulator.")
        return
    
    st.markdown("Submit input data for AI-powered analysis or chat with the AI assistant.")
    
    # Show user context
    st.info(
        f"📍 Logged in as **{current_user.username}** | "
        f"Group: **{current_user.group.value}**"
    )
    
    # Mode selector - outside form for dynamic UI updates
    mode = st.radio(
        "Mode",
        ["📊 Analysis (Score)", "💬 Chat (Q&A)"],
        horizontal=True,
        help="Analysis mode provides a score and categories. Chat mode is for conversational Q&A.",
    )
    mode_key = "analysis" if "Analysis" in mode else "chat"
    
    with st.form("analysis_form"):
        # Group selector (ABAC)
        if current_user.has_permission(Permission.VIEW_ALL_GROUPS):
            group_options = [g.value for g in Group]
            group = st.selectbox("Group", group_options, index=0)
        else:
            group = current_user.group.value
            st.text_input("Group", value=group, disabled=True)
        
        # Dynamic placeholder based on mode
        if mode_key == "chat":
            input_placeholder = "Ask a question or describe what you need help with..."
            input_label = "Your Message"
        else:
            input_placeholder = "Enter the text you want to analyze..."
            input_label = "Input Data"
        
        input_text = st.text_area(
            input_label,
            placeholder=input_placeholder,
            height=200,
            help="This text will be processed by the AI model",
        )
        
        context = st.text_area(
            "Additional Context (optional)",
            placeholder="Any additional context or instructions...",
            height=100,
            help="Optional context to help guide the response",
        )
        
        button_label = "💬 Send" if mode_key == "chat" else "🔍 Analyze"
        submitted = st.form_submit_button(button_label, use_container_width=True)
    
    if submitted:
        # Validation
        if not input_text.strip():
            st.error("Input is required")
            return
        
        # Process request with user context
        spinner_text = "💬 Generating response..." if mode_key == "chat" else "🔄 Processing with AI..."
        with st.spinner(spinner_text):
            try:
                with get_session() as session:
                    # Pass current user to processor for ABAC
                    processor = Processor(session, user=current_user)
                    
                    request_data = RequestCreate(
                        input_text=input_text.strip(),
                        context=context.strip() if context else None,
                        group=group,
                    )
                    
                    # Pass mode to processor
                    request, result = processor.process_request(request_data, mode=mode_key)
                
                # Store result in session_state for persistence across reruns
                st.session_state.last_analysis_result = {
                    "request_id": request.id,
                    "result_id": result.id,
                    "result_type": result.result_type,
                    "score": result.score,
                    "categories": result.categories,
                    "summary": result.summary,
                    "validation_status": result.validation_status,
                    "validation_details": result.validation_details,
                    "llm_trace": result.llm_trace,
                    "group": request.group,
                    "created_by": current_user.username,
                    "created_at": request.created_at.isoformat(),
                }
                st.rerun()  # Rerun to display from session_state
                
            except PermissionError as e:
                st.error(f"🚫 {str(e)}")
            except Exception as e:
                st.error(f"❌ Analysis failed: {str(e)}")
                st.exception(e)
    
    # Display result from session_state (persists across button clicks)
    if "last_analysis_result" in st.session_state:
        result_data = st.session_state.last_analysis_result
        
        # Button to clear and start new analysis
        if st.button("🔄 New Analysis", use_container_width=True):
            del st.session_state.last_analysis_result
            st.rerun()
        
        st.markdown("---")
        
        # Display results based on mode
        if result_data["result_type"] == "chat":
            # CHAT MODE - Simple text response
            st.success("✅ Response Generated!")
            
            # Chat-style response display
            st.markdown("### 🤖 Assistant Response")
            st.markdown(
                f'<div style="background-color: #f0f2f6; padding: 1.5rem; '
                f'border-radius: 1rem; border-left: 4px solid #007bff;">'
                f'{result_data["summary"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            # ANALYSIS MODE - Full score display
            st.success("✅ Analysis Complete!")
            
            # Score display
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col2:
                score_color = get_score_color(result_data["score"])
                score_level = get_score_level(result_data["score"])
                
                st.markdown(f"""
                <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, {score_color}22, {score_color}44); border-radius: 1rem; border: 2px solid {score_color};">
                    <h1 style="color: {score_color}; margin: 0; font-size: 4rem;">{result_data["score"]}</h1>
                    <h2 style="color: {score_color}; margin: 0.5rem 0;">{score_level}</h2>
                    <p style="margin: 0; color: #666;">Analysis Score</p>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Categories
            if result_data["categories"]:
                st.subheader("🏷️ Categories Identified")
                for category in result_data["categories"]:
                    st.markdown(f"- {category}")
            else:
                st.info("No specific categories identified.")
            
            # Summary/Reasoning
            st.subheader("🤖 AI Analysis")
            st.markdown(result_data["summary"])
        
        # Validation status
        if result_data["validation_status"] != "PASS":
            st.warning(
                f"⚠️ **Validation Alert**: {result_data['validation_status']}\n\n"
                f"{result_data['validation_details'] or ''}"
            )
        
        # Human Feedback Loop section
        st.markdown("---")
        render_feedback_section(result_data["result_id"], current_user)
        
        # Request details
        with st.expander("📄 Request Details"):
            st.json({
                "request_id": result_data["request_id"],
                "result_id": result_data["result_id"],
                "group": result_data["group"],
                "created_by": result_data["created_by"],
                "created_at": result_data["created_at"],
            })
        
        # Tools & Observability
        if result_data["llm_trace"] and result_data["llm_trace"].get("tool_calls"):
            with st.expander("🔧 Tools Used (Agent Mode)", expanded=True):
                trace = result_data["llm_trace"]
                st.caption(
                    f"**Mode:** {trace.get('mode', 'unknown')} | "
                    f"**Iterations:** {trace.get('total_iterations', 0)}"
                )
                st.markdown("---")
                
                for tc in trace["tool_calls"]:
                    tool_name = tc.get("tool", "unknown")
                    status = tc.get("status", "unknown")
                    status_icon = "✅" if status == "success" else "❌"
                    
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.markdown(f"**{status_icon} {tool_name}**")
                    with col2:
                        if tc.get("arguments"):
                            st.code(str(tc["arguments"]), language="json")
                    
                    if tc.get("result"):
                        result_preview = str(tc["result"])
                        if len(result_preview) > 300:
                            result_preview = result_preview[:300] + "..."
                        st.info(f"📤 Result: {result_preview}")
                    
                    if tc.get("error"):
                        st.error(f"❌ Error: {tc['error']}")
                    
                    st.markdown("---")
        
        # Full LLM Trace (Observability)
        with st.expander("🔍 Full LLM Trace (Observability)"):
            st.caption(
                "Full trace of LLM interaction for debugging and evaluation. "
                "This data enables Error Analysis when the model makes mistakes."
            )
            if result_data["llm_trace"]:
                st.json(result_data["llm_trace"])
            else:
                st.info("No trace data available.")


def render_dashboard(current_user: UserProfile):
    """Render the dashboard with recent results."""
    st.header("📊 Analysis Dashboard")
    
    # Show user context and what they can see
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info(
            f"📍 Viewing as **{current_user.username}** | "
            f"Group: **{'All' if current_user.has_permission(Permission.VIEW_ALL_GROUPS) else current_user.group.value}** | "
            f"Max Score Visible: **{current_user.get_max_visible_score()}**"
        )
    
    try:
        with get_session() as session:
            processor = Processor(session, user=current_user)
            
            # Get stats with ABAC applied
            stats = processor.get_dashboard_stats()
            
            # Summary metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("📊 Total Results", stats["total_analyzed"])
            with col2:
                st.metric("💬 Chat", stats.get("chat_count", 0))
            with col3:
                st.metric("⚠️ High Score", stats["high_score_count"])
            with col4:
                st.metric("🔴 Critical", stats["critical_count"], delta_color="inverse")
            with col5:
                st.metric("📈 Avg Score", f"{stats['average_score']:.1f}")
            
            # Show which groups are visible
            if stats["groups_visible"]:
                st.caption(f"Groups visible: {', '.join(stats['groups_visible'])}")
            
            st.markdown("---")
            
            # Recent results table
            st.subheader("📋 Recent Analysis Results")
            
            recent = processor.get_recent_results(limit=10)
            
            if recent:
                for result in recent:
                    score_color = get_score_color(result.score)
                    score_level = get_score_level(result.score)
                    
                    # Build expander title based on result type
                    if result.result_type == "chat":
                        expander_title = f"💬 Chat #{result.id} | Group: {result.group}"
                    else:
                        expander_title = f"📊 Result #{result.id} | Score: {result.score} | {score_level} | Group: {result.group}"
                    
                    with st.expander(expander_title, expanded=False):
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            if result.result_type == "chat":
                                st.markdown("**Type:** 💬 Chat")
                            else:
                                st.metric("Score", result.score)
                                st.write(f"**Level:** {score_level}")
                            st.write(f"**Group:** {result.group}")
                            st.write(f"**Date:** {result.created_at.strftime('%Y-%m-%d %H:%M')}")
                        with col2:
                            if result.result_type != "chat" and result.categories:
                                st.write("**Categories:**")
                                for cat in result.categories:
                                    st.markdown(f"- {cat}")
                            st.write("**AI Response:**" if result.result_type == "chat" else "**AI Summary:**")
                            st.markdown(result.summary)
                        
                        # Similar historical cases (RAG)
                        render_similar_cases(result, current_user)
            else:
                st.info(
                    "No results visible with your current access level.\n\n"
                    "This could mean:\n"
                    "- No results exist in your group\n"
                    "- All results exceed your access level\n\n"
                    "💡 Try switching to a user with higher access in the Identity Simulator."
                )
            
            # ABAC demo: show what's hidden
            if not current_user.has_permission(Permission.VIEW_ALL_GROUPS):
                st.markdown("---")
                st.caption(
                    f"🔒 You are only seeing results from the **{current_user.group.value}** group. "
                    f"Switch to 'Alice Admin' or 'Bob Senior' to see all groups."
                )
                
    except Exception as e:
        st.error(f"Failed to load dashboard: {e}")
        st.exception(e)


def render_evaluation(current_user: UserProfile):
    """
    Render the Evaluation Dashboard.
    
    Shows model quality metrics, feedback statistics, and results needing review.
    """
    st.header("🔬 Model Evaluation Dashboard")
    
    st.markdown("""
    This dashboard provides visibility into model quality through:
    - **Human Feedback Statistics** - accuracy based on expert verdicts
    - **Validation Metrics** - automated safety check results
    - **Results Needing Review** - all results requiring review for full observability
    """)
    
    try:
        with get_session() as session:
            processor = Processor(session, user=current_user)
            
            # Feedback statistics
            stats = processor.get_feedback_stats()
            
            st.subheader("📈 Feedback Statistics")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("📊 Total Results", stats["total_results"])
            
            with col2:
                st.metric(
                    "💬 With Feedback",
                    stats["with_feedback"],
                    delta=f"{stats['feedback_rate']*100:.0f}% rate",
                )
            
            with col3:
                st.metric(
                    "👍 Positive",
                    stats["positive_feedback"],
                    delta_color="normal",
                )
            
            with col4:
                st.metric(
                    "👎 Negative",
                    stats["negative_feedback"],
                    delta_color="inverse",
                )
            
            # Accuracy estimate
            if stats["accuracy_estimate"] is not None:
                st.markdown("---")
                accuracy_pct = stats["accuracy_estimate"] * 100
                
                # Color based on accuracy
                if accuracy_pct >= 90:
                    color = "#28a745"
                    status = "Excellent"
                elif accuracy_pct >= 75:
                    color = "#ffc107"
                    status = "Good"
                else:
                    color = "#dc3545"
                    status = "Needs Improvement"
                
                st.markdown(f"""
                <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, {color}22, {color}44); 
                     border-radius: 1rem; border: 2px solid {color};">
                    <h1 style="color: {color}; margin: 0; font-size: 3rem;">{accuracy_pct:.1f}%</h1>
                    <h3 style="color: {color}; margin: 0.5rem 0;">Estimated Accuracy</h3>
                    <p style="margin: 0; color: #666;">Based on {stats['with_feedback']} human verdicts ({status})</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info(
                    "📊 **No accuracy data yet.** "
                    "Collect human feedback using the 👍/👎 buttons to build the Golden Dataset."
                )
            
            # Validation failures
            st.markdown("---")
            st.subheader("🛡️ Validation Results")
            
            if stats["validation_failures"]:
                st.warning("⚠️ Validation failures detected:")
                
                for status, count in stats["validation_failures"].items():
                    st.markdown(f"- **{status}**: {count} occurrences")
                
                st.caption(
                    "Validation failures indicate potential issues like low quality responses "
                    "or inconsistent assessments. Review these results immediately."
                )
            else:
                st.success("✅ All validations passing. No issues detected.")
            
            # All Results for Review (with ABAC filtering)
            st.markdown("---")
            st.subheader("📋 All Results")
            
            st.caption(
                "All results with ABAC filtering. Priority: validation failures → pending feedback → reviewed. "
                "Results never disappear after feedback."
            )
            
            results_to_review = processor.get_results_needing_review(limit=20)
            
            if results_to_review:
                for result in results_to_review:
                    score_color = get_score_color(result.score)
                    score_level = get_score_level(result.score)
                    
                    # Build status tags based on current state
                    tags = []
                    if result.validation_status != "PASS":
                        tags.append(f"🚨 {result.validation_status}")
                    if result.human_feedback is None:
                        tags.append("⏳ Pending")
                    elif result.human_feedback is True:
                        tags.append("👍 Correct")
                    elif result.human_feedback is False:
                        tags.append("👎 Incorrect")
                    
                    # Add type indicator for chat results
                    if result.result_type == "chat":
                        tags.insert(0, "💬 Chat")
                    
                    tag_str = " | ".join(tags) if tags else ""
                    
                    # Build title based on result type
                    if result.result_type == "chat":
                        expander_title = f"#{result.id} | 💬 Chat | {tag_str}"
                    else:
                        expander_title = f"#{result.id} | {score_level} ({result.score}) | {tag_str}"
                    
                    with st.expander(expander_title, expanded=False):
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            if result.result_type == "chat":
                                st.markdown("**Type:** 💬 Chat")
                            else:
                                st.metric("Score", result.score)
                                st.write(f"**Level:** {score_level}")
                            st.write(f"**Group:** {result.group}")
                            st.write(f"**Validation:** {result.validation_status}")
                            
                            if result.validation_details:
                                st.error(result.validation_details)
                        
                        with col2:
                            # Show categories only for analysis results
                            if result.result_type != "chat" and result.categories:
                                st.write("**Categories:**")
                                for cat in result.categories:
                                    st.markdown(f"- {cat}")
                            
                            st.write("**AI Response:**" if result.result_type == "chat" else "**AI Summary:**")
                            st.markdown(result.summary[:500] + "..." if len(result.summary) > 500 else result.summary)
                        
                        # Feedback buttons
                        st.markdown("---")
                        render_feedback_section(result.id, current_user)
                        
                        # Similar historical cases (RAG)
                        render_similar_cases(result, current_user)
                        
                        # Tools & Trace viewer
                        if result.llm_trace:
                            trace = result.llm_trace
                            
                            # Show tools summary if tools were used
                            if trace.get("tool_calls"):
                                with st.expander("🔧 Tools Used", expanded=True):
                                    st.caption("Tools called during analysis:")
                                    for tc in trace["tool_calls"]:
                                        tool_name = tc.get("tool", "unknown")
                                        status = tc.get("status", "unknown")
                                        status_icon = "✅" if status == "success" else "❌"
                                        
                                        st.markdown(f"**{status_icon} {tool_name}**")
                                        
                                        # Arguments
                                        if tc.get("arguments"):
                                            st.code(str(tc["arguments"]), language="json")
                                        
                                        # Result preview
                                        if tc.get("result"):
                                            result_str = str(tc["result"])
                                            if len(result_str) > 200:
                                                result_str = result_str[:200] + "..."
                                            st.markdown(f"*Result:* `{result_str}`")
                                        
                                        if tc.get("error"):
                                            st.error(f"Error: {tc['error']}")
                                        
                                        st.markdown("---")
                            
                            # Full trace for debugging
                            with st.expander("🔍 Full LLM Trace"):
                                st.json(trace)
            else:
                st.success("🎉 No results requiring immediate review!")
                st.info("All results have passed validation and received feedback.")
                
    except Exception as e:
        st.error(f"Failed to load evaluation data: {e}")
        st.exception(e)


def render_about(current_user: UserProfile):
    """Render the about page."""
    st.header("ℹ️ About Azure GenAI Accelerator")
    
    st.markdown("""
    ## Overview
    
    The **Azure GenAI Accelerator** is a production-ready template for building
    GenAI-powered applications on Azure. It provides a secure, scalable foundation
    with enterprise-grade features out of the box.
    
    ## Key Features
    
    - 🔐 **Zero Trust Architecture**: No hardcoded secrets
    - 🌐 **Network Isolation**: Designed for Azure VNET deployment
    - 🎫 **Managed Identity**: Uses Azure Entra ID for authentication
    - 🔒 **Key Vault Integration**: Secrets stored securely
    - 👤 **RBAC**: Role-based access control for actions
    - 📍 **ABAC**: Attribute-based filtering by group
    
    ## Observability & Evaluation
    
    Built-in features for model quality monitoring:
    
    - 🔍 **LLM Tracing**: Full trace of input and output for debugging
    - 🛡️ **Validation**: Automated quality checks
    - 👍👎 **Human Feedback Loop**: Binary feedback collection for model improvement
    - 📊 **Evaluation Dashboard**: Accuracy estimates and review queue
    
    ## Technology Stack
    
    - **Backend**: Python 3.11+ / FastAPI
    - **Frontend**: Streamlit
    - **Database**: PostgreSQL (SQLModel)
    - **AI**: Azure OpenAI / OpenAI / Anthropic / Ollama
    - **Infrastructure**: Azure Container Apps / Terraform
    - **Auth**: Azure Entra ID (mocked locally)
    
    ## Access Control Model
    
    | Role | Can Analyze | See High Score | All Groups |
    |------|-------------|----------------|------------|
    | Admin | ✅ | ✅ | ✅ |
    | Senior Analyst | ✅ | ✅ | ✅ |
    | Analyst | ✅ | ✅ | ❌ (own group) |
    | Viewer | ❌ | ❌ | ❌ (own group) |
    
    ## Score Levels
    
    | Level | Score Range | Meaning |
    |-------|-------------|---------|
    | LOW | 0-25 | Minimal significance |
    | MEDIUM | 26-50 | Moderate significance |
    | HIGH | 51-75 | High significance |
    | CRITICAL | 76-100 | Critical, immediate review |
    """)
    
    # Show current user's permissions
    st.markdown("---")
    st.subheader("🔑 Your Current Permissions")
    
    permissions = [p for p in Permission if current_user.has_permission(p)]
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Granted:**")
        for p in permissions:
            st.success(f"✅ {p.value}")
    
    with col2:
        st.markdown("**Denied:**")
        denied = [p for p in Permission if not current_user.has_permission(p)]
        for p in denied:
            st.error(f"❌ {p.value}")


def main():
    """Main application entry point."""
    init_session_state()
    
    if not st.session_state.get("db_initialized", False):
        st.error("⚠️ Database not initialized. Please check your configuration.")
        st.stop()
    
    # Render Identity Simulator first (returns current user)
    current_user = render_identity_simulator()
    
    # Render navigation
    page = render_sidebar(current_user)
    
    # Render selected page with user context
    if page == "📝 New Analysis":
        render_new_analysis(current_user)
    elif page == "📊 Dashboard":
        render_dashboard(current_user)
    elif page == "🔬 Evaluation":
        render_evaluation(current_user)
    elif page == "ℹ️ About":
        render_about(current_user)


if __name__ == "__main__":
    main()
