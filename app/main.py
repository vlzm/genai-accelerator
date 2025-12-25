"""
Streamlit UI for KYC/AML Analyzer.

Provides a user interface for:
- Submitting transactions for risk analysis
- Viewing analysis results
- Reviewing historical reports

Run with: streamlit run app/main.py
"""

import streamlit as st
from decimal import Decimal, InvalidOperation

from app.database import init_db, get_session
from app.models import TransactionCreate
from app.services.risk_engine import RiskEngine


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


def get_risk_class(risk_level: str) -> str:
    """Returns CSS class for risk level."""
    return f"risk-{risk_level.lower()}"


def init_session_state():
    """Initialize Streamlit session state."""
    if "db_initialized" not in st.session_state:
        try:
            init_db()
            st.session_state.db_initialized = True
        except Exception as e:
            st.error(f"Failed to initialize database: {e}")
            st.session_state.db_initialized = False


def render_sidebar():
    """Render sidebar navigation."""
    with st.sidebar:
        st.title("🛡️ KYC/AML Analyzer")
        st.markdown("---")
        
        page = st.radio(
            "Navigation",
            ["📝 New Analysis", "📊 Dashboard", "ℹ️ About"],
            label_visibility="collapsed",
        )
        
        st.markdown("---")
        st.caption("Secure KYC/AML Analysis Tool")
        st.caption("v1.0.0 | Phase 1 MVP")
        
        return page


def render_new_analysis():
    """Render the new transaction analysis form."""
    st.header("📝 Transaction Risk Analysis")
    st.markdown("Submit a transaction for AI-powered AML/KYC risk assessment.")
    
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
        
        # Process transaction
        with st.spinner("🔄 Analyzing transaction with AI..."):
            try:
                with get_session() as session:
                    engine = RiskEngine(session)
                    
                    transaction_data = TransactionCreate(
                        comment=comment.strip(),
                        amount=amount_decimal,
                        currency=currency,
                        sender_id=sender_id.strip(),
                        receiver_id=receiver_id.strip(),
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
                
                # Transaction details
                with st.expander("📄 Transaction Details"):
                    st.json({
                        "transaction_id": transaction.id,
                        "sender_id": transaction.sender_id,
                        "receiver_id": transaction.receiver_id,
                        "amount": str(transaction.amount),
                        "currency": transaction.currency,
                        "created_at": transaction.created_at.isoformat(),
                    })
                    
            except Exception as e:
                st.error(f"❌ Analysis failed: {str(e)}")
                st.exception(e)


def render_dashboard():
    """Render the dashboard with recent reports."""
    st.header("📊 Risk Analysis Dashboard")
    
    try:
        with get_session() as session:
            engine = RiskEngine(session)
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            recent = engine.get_recent_reports(limit=100)
            high_risk = [r for r in recent if r.risk_score >= 50]
            critical = [r for r in recent if r.risk_level == "CRITICAL"]
            
            with col1:
                st.metric("Total Analyzed", len(recent))
            with col2:
                st.metric("High Risk", len(high_risk))
            with col3:
                st.metric("Critical", len(critical), delta_color="inverse")
            with col4:
                avg_score = sum(r.risk_score for r in recent) / len(recent) if recent else 0
                st.metric("Avg Risk Score", f"{avg_score:.1f}")
            
            st.markdown("---")
            
            # Recent reports table
            st.subheader("📋 Recent Analysis Reports")
            
            if recent:
                for report in engine.get_recent_reports(limit=10):
                    with st.expander(
                        f"Report #{report.id} | Score: {report.risk_score} | {report.risk_level}",
                        expanded=False,
                    ):
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.metric("Risk Score", report.risk_score)
                            st.write(f"**Level:** {report.risk_level}")
                            st.write(f"**Date:** {report.created_at.strftime('%Y-%m-%d %H:%M')}")
                        with col2:
                            st.write("**Risk Factors:**")
                            for factor in report.risk_factors:
                                st.markdown(f"- {factor}")
                            st.write("**AI Reasoning:**")
                            st.markdown(report.llm_reasoning)
            else:
                st.info("No reports yet. Submit a transaction for analysis to get started.")
                
    except Exception as e:
        st.error(f"Failed to load dashboard: {e}")


def render_about():
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
    - **AI**: Azure OpenAI
    - **Infrastructure**: Azure Container Apps / Terraform
    """)


def main():
    """Main application entry point."""
    init_session_state()
    
    if not st.session_state.get("db_initialized", False):
        st.error("⚠️ Database not initialized. Please check your configuration.")
        st.stop()
    
    page = render_sidebar()
    
    if page == "📝 New Analysis":
        render_new_analysis()
    elif page == "📊 Dashboard":
        render_dashboard()
    elif page == "ℹ️ About":
        render_about()


if __name__ == "__main__":
    main()

