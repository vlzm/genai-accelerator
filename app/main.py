"""
Streamlit UI for KYC/AML Analyzer.

Provides a user interface for:
- Submitting transactions for risk analysis
- Viewing analysis results
- Reviewing historical reports

Implements:
- Mock Identity Provider for RBAC/ABAC demonstration
- Role-based access control for actions
- Attribute-based filtering for data

Run with: streamlit run app/main.py
"""

import streamlit as st
from decimal import Decimal, InvalidOperation

from app.database import init_db, get_session
from app.models import TransactionCreate
from app.services.risk_engine import RiskEngine
from app.services.auth_mock import (
    get_all_users,
    get_current_user,
    UserProfile,
    Permission,
    Region,
)


# Page configuration
st.set_page_config(
    page_title="KYC/AML Analyzer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .risk-low { 
        background-color: #d4edda; 
        padding: 1rem; 
        border-radius: 0.5rem; 
        border-left: 4px solid #28a745;
    }
    .risk-medium { 
        background-color: #fff3cd; 
        padding: 1rem; 
        border-radius: 0.5rem;
        border-left: 4px solid #ffc107;
    }
    .risk-high { 
        background-color: #f8d7da; 
        padding: 1rem; 
        border-radius: 0.5rem;
        border-left: 4px solid #dc3545;
    }
    .risk-critical { 
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
    .role-senior_officer { background-color: #007bff; color: white; }
    .role-officer { background-color: #28a745; color: white; }
    .role-viewer { background-color: #6c757d; color: white; }
</style>
""", unsafe_allow_html=True)


def get_risk_color(risk_level: str) -> str:
    """Returns color code for risk level."""
    colors = {
        "LOW": "#28a745",
        "MEDIUM": "#ffc107", 
        "HIGH": "#dc3545",
        "CRITICAL": "#721c24",
    }
    return colors.get(risk_level.upper(), "#6c757d")


def get_role_color(role: str) -> str:
    """Returns color for user role."""
    colors = {
        "admin": "#6f42c1",
        "senior_officer": "#007bff",
        "officer": "#28a745",
        "viewer": "#6c757d",
    }
    return colors.get(role, "#6c757d")


def render_feedback_section(report_id: int, current_user: UserProfile):
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
            "**Help improve the model.** Is this risk assessment correct?\n\n"
            "_Your feedback builds our 'Golden Dataset' for model evaluation._"
        )
        
        col1, col2 = st.columns(2)
        
        # Use unique keys based on report_id
        with col1:
            if st.button("👍 Correct", key=f"feedback_pos_{report_id}", use_container_width=True):
                try:
                    with get_session() as session:
                        engine = RiskEngine(session, user=current_user)
                        engine.submit_feedback(report_id, feedback=True)
                    st.success("✅ Thank you! Marked as correct. Data saved for model improvement.")
                except Exception as e:
                    st.error(f"Failed to save feedback: {e}")
        
        with col2:
            if st.button("👎 Incorrect", key=f"feedback_neg_{report_id}", use_container_width=True):
                st.session_state[f"show_feedback_form_{report_id}"] = True
        
        # Show feedback form if negative feedback selected
        if st.session_state.get(f"show_feedback_form_{report_id}", False):
            with st.form(f"feedback_form_{report_id}"):
                feedback_comment = st.text_area(
                    "What was wrong? (optional)",
                    placeholder="e.g., Risk score too high, wrong factors identified...",
                    help="Your explanation helps with Error Analysis",
                )
                
                if st.form_submit_button("Submit Feedback"):
                    try:
                        with get_session() as session:
                            engine = RiskEngine(session, user=current_user)
                            engine.submit_feedback(
                                report_id,
                                feedback=False,
                                comment=feedback_comment if feedback_comment else None,
                            )
                        st.warning("📝 Recorded as error. Will be reviewed by expert.")
                        st.session_state[f"show_feedback_form_{report_id}"] = False
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
    
    # Initialize selected user (default to officer_south for demo)
    if "selected_user_key" not in st.session_state:
        st.session_state.selected_user_key = "officer_south"


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
            "clearance_level": current_user.clearance_level,
            "permissions": [p.value for p in Permission if current_user.has_permission(p)],
        })
    
    # Show access summary
    st.sidebar.markdown("**Access Level:**")
    if current_user.has_permission(Permission.VIEW_ALL_REGIONS):
        st.sidebar.success("🌍 All Regions")
    else:
        st.sidebar.info(f"📍 {current_user.region.value} only")
    
    if current_user.has_permission(Permission.ANALYZE_TRANSACTIONS):
        st.sidebar.success("✅ Can Analyze")
    else:
        st.sidebar.warning("🚫 View Only")
    
    if current_user.has_permission(Permission.VIEW_HIGH_RISK):
        st.sidebar.success("🔴 High Risk Visible")
    else:
        st.sidebar.warning("🟡 Limited to <70 score")
    
    return current_user


def render_sidebar(current_user: UserProfile):
    """Render sidebar navigation."""
    with st.sidebar:
        st.title("🛡️ KYC/AML Analyzer")
        
        page = st.radio(
            "Navigation",
            ["📝 New Analysis", "📊 Dashboard", "🔬 Evaluation", "ℹ️ About"],
            label_visibility="collapsed",
        )
        
        st.markdown("---")
        st.caption("Secure KYC/AML Analysis Tool")
        st.caption("v2.1.0 | Observability Enabled")
        
        return page


def render_new_analysis(current_user: UserProfile):
    """Render the new transaction analysis form."""
    st.header("📝 Transaction Risk Analysis")
    
    # RBAC check: Can user analyze?
    if not current_user.has_permission(Permission.ANALYZE_TRANSACTIONS):
        st.error(
            f"🚫 **Access Denied**\n\n"
            f"Your role ({current_user.role.value}) does not have permission to analyze transactions.\n"
            f"Please contact an administrator to upgrade your access."
        )
        st.info("💡 Try switching to 'Carol Officer' or 'Alice Administrator' in the Identity Simulator.")
        return
    
    st.markdown("Submit a transaction for AI-powered AML/KYC risk assessment.")
    
    # Show user context
    st.info(
        f"📍 Logged in as **{current_user.username}** | "
        f"Region: **{current_user.region.value}** | "
        f"Clearance: **Level {current_user.clearance_level}**"
    )
    
    with st.form("transaction_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            sender_id = st.text_input(
                "Sender ID",
                placeholder="e.g., ACC-123456",
                help="Unique identifier for the sender",
            )
            
            amount = st.text_input(
                "Amount",
                placeholder="e.g., 10000.00",
                help="Transaction amount",
            )
            
            # Region selector (ABAC)
            if current_user.has_permission(Permission.VIEW_ALL_REGIONS):
                region_options = [r.value for r in Region]
                region = st.selectbox("Region", region_options, index=0)
            else:
                region = current_user.region.value
                st.text_input("Region", value=region, disabled=True)
            
        with col2:
            receiver_id = st.text_input(
                "Receiver ID", 
                placeholder="e.g., ACC-789012",
                help="Unique identifier for the receiver",
            )
            
            currency = st.selectbox(
                "Currency",
                ["USD", "EUR", "GBP", "CHF", "JPY"],
                help="Transaction currency",
            )
        
        comment = st.text_area(
            "Transaction Comment",
            placeholder="Enter the transaction comment or description to analyze...",
            height=150,
            help="This text will be analyzed for AML/KYC risk indicators",
        )
        
        submitted = st.form_submit_button("🔍 Analyze Transaction", use_container_width=True)
    
    if submitted:
        # Validation
        errors = []
        if not sender_id.strip():
            errors.append("Sender ID is required")
        if not receiver_id.strip():
            errors.append("Receiver ID is required")
        if not comment.strip():
            errors.append("Transaction comment is required")
        
        try:
            amount_decimal = Decimal(amount) if amount else Decimal("0")
            if amount_decimal <= 0:
                errors.append("Amount must be greater than 0")
        except InvalidOperation:
            errors.append("Invalid amount format")
            amount_decimal = None
        
        if errors:
            for error in errors:
                st.error(error)
            return
        
        # Process transaction with user context
        with st.spinner("🔄 Analyzing transaction with AI..."):
            try:
                with get_session() as session:
                    # Pass current user to engine for ABAC
                    engine = RiskEngine(session, user=current_user)
                    
                    transaction_data = TransactionCreate(
                        comment=comment.strip(),
                        amount=amount_decimal,
                        currency=currency,
                        sender_id=sender_id.strip(),
                        receiver_id=receiver_id.strip(),
                        region=region,
                    )
                    
                    transaction, report = engine.process_transaction(transaction_data)
                
                # Display results
                st.success("✅ Analysis Complete!")
                st.markdown("---")
                
                # Risk score display
                col1, col2, col3 = st.columns([1, 2, 1])
                
                with col2:
                    risk_color = get_risk_color(report.risk_level)
                    
                    st.markdown(f"""
                    <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, {risk_color}22, {risk_color}44); border-radius: 1rem; border: 2px solid {risk_color};">
                        <h1 style="color: {risk_color}; margin: 0; font-size: 4rem;">{report.risk_score}</h1>
                        <h2 style="color: {risk_color}; margin: 0.5rem 0;">{report.risk_level}</h2>
                        <p style="margin: 0; color: #666;">Risk Score</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
                
                # Risk factors
                if report.risk_factors:
                    st.subheader("⚠️ Risk Factors Identified")
                    for factor in report.risk_factors:
                        st.markdown(f"- {factor}")
                else:
                    st.info("No specific risk factors identified.")
                
                # LLM reasoning
                st.subheader("🤖 AI Analysis")
                st.markdown(report.llm_reasoning)
                
                # Guardrail status
                if report.guardrail_status != "PASS":
                    st.warning(
                        f"⚠️ **Guardrail Alert**: {report.guardrail_status}\n\n"
                        f"{report.guardrail_details or ''}"
                    )
                
                # Similar Cases (RAG) - Refresh engine with new session
                with get_session() as rag_session:
                    rag_engine = RiskEngine(rag_session, user=current_user)
                    
                    if rag_engine.is_rag_enabled():
                        with st.expander("🔍 Similar Historical Cases (RAG)", expanded=True):
                            st.caption(
                                "AI-powered similarity search finds past cases that may help inform your decision. "
                                "This feature can be disabled with RAG_ENABLED=false."
                            )
                            
                            # Need to re-fetch report in this session
                            from sqlmodel import select
                            from app.models import RiskReport as ReportModel
                            fresh_report = rag_session.exec(
                                select(ReportModel).where(ReportModel.id == report.id)
                            ).first()
                            
                            if fresh_report:
                                similar_cases = rag_engine.find_similar_cases(fresh_report, limit=3)
                                
                                if similar_cases:
                                    for i, similar in enumerate(similar_cases, 1):
                                        sim_color = get_risk_color(similar.risk_level)
                                        st.markdown(f"""
                                        **Case #{i}** (Report #{similar.id})
                                        - Risk: <span style="color: {sim_color}; font-weight: bold;">{similar.risk_level}</span> ({similar.risk_score})
                                        - Region: {similar.region}
                                        - Date: {similar.created_at.strftime('%Y-%m-%d')}
                                        - Factors: {', '.join(similar.risk_factors[:3])}{'...' if len(similar.risk_factors) > 3 else ''}
                                        """, unsafe_allow_html=True)
                                        st.markdown("---")
                                else:
                                    st.info(
                                        "No similar cases found yet. "
                                        "This improves as more transactions are analyzed."
                                    )
                
                # Human Feedback Loop section
                st.markdown("---")
                render_feedback_section(report.id, current_user)
                
                # Transaction details
                with st.expander("📄 Transaction Details"):
                    st.json({
                        "transaction_id": transaction.id,
                        "sender_id": transaction.sender_id,
                        "receiver_id": transaction.receiver_id,
                        "amount": str(transaction.amount),
                        "currency": transaction.currency,
                        "region": transaction.region,
                        "created_by": current_user.username,
                        "created_at": transaction.created_at.isoformat(),
                    })
                
                # LLM Trace (Observability)
                with st.expander("🔍 LLM Trace (Observability)"):
                    st.caption(
                        "Full trace of LLM interaction for debugging and evaluation. "
                        "This data enables Error Analysis when the model makes mistakes."
                    )
                    if report.llm_trace:
                        st.json(report.llm_trace)
                    else:
                        st.info("No trace data available.")
                    
            except PermissionError as e:
                st.error(f"🚫 {str(e)}")
            except Exception as e:
                st.error(f"❌ Analysis failed: {str(e)}")
                st.exception(e)


def render_dashboard(current_user: UserProfile):
    """Render the dashboard with recent reports."""
    st.header("📊 Risk Analysis Dashboard")
    
    # Show user context and what they can see
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info(
            f"📍 Viewing as **{current_user.username}** | "
            f"Region: **{'All' if current_user.has_permission(Permission.VIEW_ALL_REGIONS) else current_user.region.value}** | "
            f"Max Risk Score Visible: **{current_user.get_max_visible_risk_score()}**"
        )
    
    try:
        with get_session() as session:
            engine = RiskEngine(session, user=current_user)
            
            # Get stats with ABAC applied
            stats = engine.get_dashboard_stats()
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("📊 Visible Reports", stats["total_analyzed"])
            with col2:
                st.metric("⚠️ High Risk", stats["high_risk_count"])
            with col3:
                st.metric("🔴 Critical", stats["critical_count"], delta_color="inverse")
            with col4:
                st.metric("📈 Avg Score", f"{stats['average_score']:.1f}")
            
            # Show which regions are visible
            if stats["regions_visible"]:
                st.caption(f"Regions visible: {', '.join(stats['regions_visible'])}")
            
            st.markdown("---")
            
            # Recent reports table
            st.subheader("📋 Recent Analysis Reports")
            
            recent = engine.get_recent_reports(limit=10)
            
            if recent:
                for report in recent:
                    risk_color = get_risk_color(report.risk_level)
                    with st.expander(
                        f"Report #{report.id} | Score: {report.risk_score} | "
                        f"{report.risk_level} | Region: {report.region}",
                        expanded=False,
                    ):
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.metric("Risk Score", report.risk_score)
                            st.write(f"**Level:** {report.risk_level}")
                            st.write(f"**Region:** {report.region}")
                            st.write(f"**Date:** {report.created_at.strftime('%Y-%m-%d %H:%M')}")
                        with col2:
                            st.write("**Risk Factors:**")
                            for factor in report.risk_factors:
                                st.markdown(f"- {factor}")
                            st.write("**AI Reasoning:**")
                            st.markdown(report.llm_reasoning)
            else:
                st.info(
                    "No reports visible with your current access level.\n\n"
                    "This could mean:\n"
                    "- No reports exist in your region\n"
                    "- All reports exceed your clearance level\n\n"
                    "💡 Try switching to a user with higher access in the Identity Simulator."
                )
            
            # ABAC demo: show what's hidden
            if not current_user.has_permission(Permission.VIEW_ALL_REGIONS):
                st.markdown("---")
                st.caption(
                    f"🔒 You are only seeing reports from the **{current_user.region.value}** region. "
                    f"Switch to 'Alice Admin' or 'Bob Senior' to see all regions."
                )
                
    except Exception as e:
        st.error(f"Failed to load dashboard: {e}")
        st.exception(e)


def render_evaluation(current_user: UserProfile):
    """
    Render the Evaluation Dashboard.
    
    Shows model quality metrics, feedback statistics, and reports needing review.
    This is the "Enlightened Dictator" view for monitoring model performance.
    """
    st.header("🔬 Model Evaluation Dashboard")
    
    st.markdown("""
    This dashboard provides visibility into model quality through:
    - **Human Feedback Statistics** - accuracy based on expert verdicts
    - **Guardrail Metrics** - automated safety check results
    - **Reports Needing Review** - prioritized queue for expert review
    """)
    
    try:
        with get_session() as session:
            engine = RiskEngine(session, user=current_user)
            
            # Feedback statistics
            stats = engine.get_feedback_stats()
            
            st.subheader("📈 Feedback Statistics")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("📊 Total Reports", stats["total_reports"])
            
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
            
            # Guardrail failures
            st.markdown("---")
            st.subheader("🛡️ Guardrail Results")
            
            if stats["guardrail_failures"]:
                st.warning("⚠️ Guardrail failures detected:")
                
                for status, count in stats["guardrail_failures"].items():
                    st.markdown(f"- **{status}**: {count} occurrences")
                
                st.caption(
                    "Guardrail failures indicate potential issues like PII leakage "
                    "or inconsistent risk assessments. Review these reports immediately."
                )
            else:
                st.success("✅ All guardrails passing. No safety issues detected.")
            
            # Reports needing review
            st.markdown("---")
            st.subheader("📋 Reports Needing Review")
            
            st.caption(
                "Prioritized queue: guardrail failures first, then high-risk reports without feedback."
            )
            
            reports_to_review = engine.get_reports_needing_review(limit=10)
            
            if reports_to_review:
                for report in reports_to_review:
                    risk_color = get_risk_color(report.risk_level)
                    
                    # Build status tags
                    tags = []
                    if report.guardrail_status != "PASS":
                        tags.append(f"🚨 {report.guardrail_status}")
                    if report.human_feedback is None:
                        tags.append("⏳ Pending Feedback")
                    
                    tag_str = " | ".join(tags) if tags else ""
                    
                    with st.expander(
                        f"Report #{report.id} | {report.risk_level} ({report.risk_score}) | {tag_str}",
                        expanded=False,
                    ):
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            st.metric("Risk Score", report.risk_score)
                            st.write(f"**Level:** {report.risk_level}")
                            st.write(f"**Region:** {report.region}")
                            st.write(f"**Guardrail:** {report.guardrail_status}")
                            
                            if report.guardrail_details:
                                st.error(report.guardrail_details)
                        
                        with col2:
                            st.write("**Risk Factors:**")
                            for factor in report.risk_factors:
                                st.markdown(f"- {factor}")
                            
                            st.write("**AI Reasoning:**")
                            st.markdown(report.llm_reasoning[:500] + "..." if len(report.llm_reasoning) > 500 else report.llm_reasoning)
                        
                        # Feedback buttons
                        st.markdown("---")
                        render_feedback_section(report.id, current_user)
                        
                        # Trace viewer
                        if report.llm_trace:
                            with st.expander("🔍 LLM Trace"):
                                st.json(report.llm_trace)
            else:
                st.success("🎉 No reports requiring immediate review!")
                st.info("All reports have passed guardrails and received feedback.")
                
    except Exception as e:
        st.error(f"Failed to load evaluation data: {e}")
        st.exception(e)


def render_about(current_user: UserProfile):
    """Render the about page."""
    st.header("ℹ️ About KYC/AML Analyzer")
    
    st.markdown("""
    ## Overview
    
    The **Secure KYC/AML Analyzer** is a GenAI-powered compliance tool for detecting 
    risk in transaction comments. It uses Azure OpenAI to analyze transaction data 
    and identify potential AML (Anti-Money Laundering) and KYC (Know Your Customer) concerns.
    
    ## Security Features
    
    - 🔐 **Zero Trust Architecture**: No hardcoded secrets
    - 🌐 **Network Isolation**: Designed for Azure VNET deployment
    - 🎫 **Managed Identity**: Uses Azure AD for authentication
    - 🔒 **Key Vault Integration**: Secrets stored securely
    - 👤 **RBAC**: Role-based access control for actions
    - 📍 **ABAC**: Attribute-based filtering by region and clearance
    
    ## Observability & Evaluation
    
    Built-in features for model quality monitoring:
    
    - 🔍 **LLM Tracing**: Full trace of input, tool calls, and output for debugging
    - 🛡️ **Guardrails**: Automated safety checks (PII leakage, consistency)
    - 👍👎 **Human Feedback Loop**: Binary feedback collection for model improvement
    - 📊 **Evaluation Dashboard**: Accuracy estimates and review queue
    
    This enables the "Enlightened Dictator" approach to model quality:
    1. Collect real-world feedback (Golden Dataset)
    2. Analyze errors with full traces
    3. Make informed decisions about improvements
    
    ## Access Control Model
    
    | Role | Can Analyze | See High Risk | All Regions |
    |------|-------------|---------------|-------------|
    | Admin | ✅ | ✅ | ✅ |
    | Senior Officer | ✅ | ✅ | ✅ |
    | Officer | ✅ | ✅ | ❌ (own region) |
    | Viewer | ❌ | ❌ | ❌ (own region) |
    
    ## Risk Levels
    
    | Level | Score Range | Action |
    |-------|-------------|--------|
    | LOW | 0-25 | Normal transaction |
    | MEDIUM | 26-50 | May need review |
    | HIGH | 51-75 | Requires investigation |
    | CRITICAL | 76-100 | Immediate action needed |
    
    ## Technology Stack
    
    - **Backend**: Python 3.11+ / FastAPI
    - **Frontend**: Streamlit
    - **Database**: PostgreSQL (SQLModel)
    - **AI**: Azure OpenAI with Function Calling
    - **Infrastructure**: Azure Container Apps / Terraform
    - **Auth**: Azure Entra ID (mocked locally)
    - **Observability**: Custom LLM tracing + Guardrails
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
