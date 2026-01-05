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
from app.models import RequestCreate
from app.services.processor import Processor
from app.services.auth_mock import (
    get_all_users,
    get_current_user,
    UserProfile,
    Permission,
    Region,
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


def get_score_color(score: int) -> str:
    """Returns color code for score level."""
    if score >= 76:
        return "#721c24"  # Critical
    elif score >= 51:
        return "#dc3545"  # High
    elif score >= 26:
        return "#ffc107"  # Medium
    else:
        return "#28a745"  # Low


def get_score_level(score: int) -> str:
    """Returns level string for score."""
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


def init_session_state():
    """Initialize Streamlit session state."""
    if "db_initialized" not in st.session_state:
        try:
            init_db()
            st.session_state.db_initialized = True
        except Exception as e:
            st.error(f"Failed to initialize database: {e}")
            st.session_state.db_initialized = False
    
    # Initialize selected user (default to analyst_south for demo)
    if "selected_user_key" not in st.session_state:
        st.session_state.selected_user_key = "analyst_south"


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
            "region": current_user.region.value,
            "permissions": [p.value for p in Permission if current_user.has_permission(p)],
        })
    
    # Show access summary
    st.sidebar.markdown("**Access Level:**")
    if current_user.has_permission(Permission.VIEW_ALL_REGIONS):
        st.sidebar.success("🌍 All Regions")
    else:
        st.sidebar.info(f"📍 {current_user.region.value} only")
    
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
    
    st.markdown("Submit input data for AI-powered analysis.")
    
    # Show user context
    st.info(
        f"📍 Logged in as **{current_user.username}** | "
        f"Region: **{current_user.region.value}**"
    )
    
    with st.form("analysis_form"):
        # Region selector (ABAC)
        if current_user.has_permission(Permission.VIEW_ALL_REGIONS):
            region_options = [r.value for r in Region]
            region = st.selectbox("Region", region_options, index=0)
        else:
            region = current_user.region.value
            st.text_input("Region", value=region, disabled=True)
        
        input_text = st.text_area(
            "Input Data",
            placeholder="Enter the text you want to analyze...",
            height=200,
            help="This text will be processed by the AI model",
        )
        
        context = st.text_area(
            "Additional Context (optional)",
            placeholder="Any additional context or instructions for the analysis...",
            height=100,
            help="Optional context to help guide the analysis",
        )
        
        submitted = st.form_submit_button("🔍 Process", use_container_width=True)
    
    if submitted:
        # Validation
        if not input_text.strip():
            st.error("Input data is required")
            return
        
        # Process request with user context
        with st.spinner("🔄 Processing with AI..."):
            try:
                with get_session() as session:
                    # Pass current user to processor for ABAC
                    processor = Processor(session, user=current_user)
                    
                    request_data = RequestCreate(
                        input_text=input_text.strip(),
                        context=context.strip() if context else None,
                        region=region,
                    )
                    
                    request, result = processor.process_request(request_data)
                
                # Display results
                st.success("✅ Analysis Complete!")
                st.markdown("---")
                
                # Score display
                col1, col2, col3 = st.columns([1, 2, 1])
                
                with col2:
                    score_color = get_score_color(result.score)
                    score_level = get_score_level(result.score)
                    
                    st.markdown(f"""
                    <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, {score_color}22, {score_color}44); border-radius: 1rem; border: 2px solid {score_color};">
                        <h1 style="color: {score_color}; margin: 0; font-size: 4rem;">{result.score}</h1>
                        <h2 style="color: {score_color}; margin: 0.5rem 0;">{score_level}</h2>
                        <p style="margin: 0; color: #666;">Analysis Score</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
                
                # Categories
                if result.categories:
                    st.subheader("🏷️ Categories Identified")
                    for category in result.categories:
                        st.markdown(f"- {category}")
                else:
                    st.info("No specific categories identified.")
                
                # Summary/Reasoning
                st.subheader("🤖 AI Analysis")
                st.markdown(result.summary)
                
                # Validation status
                if result.validation_status != "PASS":
                    st.warning(
                        f"⚠️ **Validation Alert**: {result.validation_status}\n\n"
                        f"{result.validation_details or ''}"
                    )
                
                # Human Feedback Loop section
                st.markdown("---")
                render_feedback_section(result.id, current_user)
                
                # Request details
                with st.expander("📄 Request Details"):
                    st.json({
                        "request_id": request.id,
                        "region": request.region,
                        "created_by": current_user.username,
                        "created_at": request.created_at.isoformat(),
                    })
                
                # LLM Trace (Observability)
                with st.expander("🔍 LLM Trace (Observability)"):
                    st.caption(
                        "Full trace of LLM interaction for debugging and evaluation. "
                        "This data enables Error Analysis when the model makes mistakes."
                    )
                    if result.llm_trace:
                        st.json(result.llm_trace)
                    else:
                        st.info("No trace data available.")
                    
            except PermissionError as e:
                st.error(f"🚫 {str(e)}")
            except Exception as e:
                st.error(f"❌ Analysis failed: {str(e)}")
                st.exception(e)


def render_dashboard(current_user: UserProfile):
    """Render the dashboard with recent results."""
    st.header("📊 Analysis Dashboard")
    
    # Show user context and what they can see
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info(
            f"📍 Viewing as **{current_user.username}** | "
            f"Region: **{'All' if current_user.has_permission(Permission.VIEW_ALL_REGIONS) else current_user.region.value}** | "
            f"Max Score Visible: **{current_user.get_max_visible_score()}**"
        )
    
    try:
        with get_session() as session:
            processor = Processor(session, user=current_user)
            
            # Get stats with ABAC applied
            stats = processor.get_dashboard_stats()
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("📊 Visible Results", stats["total_analyzed"])
            with col2:
                st.metric("⚠️ High Score", stats["high_score_count"])
            with col3:
                st.metric("🔴 Critical", stats["critical_count"], delta_color="inverse")
            with col4:
                st.metric("📈 Avg Score", f"{stats['average_score']:.1f}")
            
            # Show which regions are visible
            if stats["regions_visible"]:
                st.caption(f"Regions visible: {', '.join(stats['regions_visible'])}")
            
            st.markdown("---")
            
            # Recent results table
            st.subheader("📋 Recent Analysis Results")
            
            recent = processor.get_recent_results(limit=10)
            
            if recent:
                for result in recent:
                    score_color = get_score_color(result.score)
                    score_level = get_score_level(result.score)
                    with st.expander(
                        f"Result #{result.id} | Score: {result.score} | "
                        f"{score_level} | Region: {result.region}",
                        expanded=False,
                    ):
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.metric("Score", result.score)
                            st.write(f"**Level:** {score_level}")
                            st.write(f"**Region:** {result.region}")
                            st.write(f"**Date:** {result.created_at.strftime('%Y-%m-%d %H:%M')}")
                        with col2:
                            st.write("**Categories:**")
                            for cat in result.categories:
                                st.markdown(f"- {cat}")
                            st.write("**AI Summary:**")
                            st.markdown(result.summary)
            else:
                st.info(
                    "No results visible with your current access level.\n\n"
                    "This could mean:\n"
                    "- No results exist in your region\n"
                    "- All results exceed your access level\n\n"
                    "💡 Try switching to a user with higher access in the Identity Simulator."
                )
            
            # ABAC demo: show what's hidden
            if not current_user.has_permission(Permission.VIEW_ALL_REGIONS):
                st.markdown("---")
                st.caption(
                    f"🔒 You are only seeing results from the **{current_user.region.value}** region. "
                    f"Switch to 'Alice Admin' or 'Bob Senior' to see all regions."
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
    - **Results Needing Review** - prioritized queue for expert review
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
            
            # Results needing review
            st.markdown("---")
            st.subheader("📋 Results Needing Review")
            
            st.caption(
                "Prioritized queue: validation failures first, then high-score results without feedback."
            )
            
            results_to_review = processor.get_results_needing_review(limit=10)
            
            if results_to_review:
                for result in results_to_review:
                    score_color = get_score_color(result.score)
                    score_level = get_score_level(result.score)
                    
                    # Build status tags
                    tags = []
                    if result.validation_status != "PASS":
                        tags.append(f"🚨 {result.validation_status}")
                    if result.human_feedback is None:
                        tags.append("⏳ Pending Feedback")
                    
                    tag_str = " | ".join(tags) if tags else ""
                    
                    with st.expander(
                        f"Result #{result.id} | {score_level} ({result.score}) | {tag_str}",
                        expanded=False,
                    ):
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            st.metric("Score", result.score)
                            st.write(f"**Level:** {score_level}")
                            st.write(f"**Region:** {result.region}")
                            st.write(f"**Validation:** {result.validation_status}")
                            
                            if result.validation_details:
                                st.error(result.validation_details)
                        
                        with col2:
                            st.write("**Categories:**")
                            for cat in result.categories:
                                st.markdown(f"- {cat}")
                            
                            st.write("**AI Summary:**")
                            st.markdown(result.summary[:500] + "..." if len(result.summary) > 500 else result.summary)
                        
                        # Feedback buttons
                        st.markdown("---")
                        render_feedback_section(result.id, current_user)
                        
                        # Trace viewer
                        if result.llm_trace:
                            with st.expander("🔍 LLM Trace"):
                                st.json(result.llm_trace)
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
    - 📍 **ABAC**: Attribute-based filtering by region
    
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
    
    | Role | Can Analyze | See High Score | All Regions |
    |------|-------------|----------------|-------------|
    | Admin | ✅ | ✅ | ✅ |
    | Senior Analyst | ✅ | ✅ | ✅ |
    | Analyst | ✅ | ✅ | ❌ (own region) |
    | Viewer | ❌ | ❌ | ❌ (own region) |
    
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
