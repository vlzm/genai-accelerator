# 🏦 AML/KYC Implementation Plan
  
> **Цель:** Реализовать AML/KYC логику на базе существующего GenAI Accelerator template.
>
> **Оценка времени:** ~60-90 минут
>
> **Дата создания:** 2026-01-11
  
---
  
## 📊 Сводка статусов
  
| Фаза | Описание | Статус | Время |
|------|----------|--------|-------|
| 0 | Подготовка окружения | ⏳ TODO | 5 мин |
| 1 | Модели данных (models.py) | ✅ DONE | - |
| 2 | Tools (sanctions, thresholds) | ✅ DONE | - |
| 3 | System Prompt | ✅ DONE | - |
| 4 | LLMResponse risk fields | ⏳ TODO | 5 мин |
| 5 | Processor logic | ⏳ TODO | 15 мин |
| 6 | Validation (PII) | ⏳ TODO | 10 мин |
| 7 | Streamlit UI | ⏳ TODO | 20 мин |
| 8 | API Schemas | ⏳ TODO | 10 мин |
| 9 | API Endpoints | ⏳ TODO | 15 мин |
| 10 | Database migration | ⏳ TODO | 5 мин |
  
---
  
## 📋 ФАЗА 0: Подготовка окружения
  
**Статус:** ⏳ TODO  
**Время:** 5 минут
  
### Действия
  
```bash
# 1. Запустить PostgreSQL
docker compose up -d postgres
  
# 2. Проверить что работает
docker compose logs postgres
  
# 3. Убедиться что .env настроен
cp .env.example .env
# Отредактировать .env: установить LLM_PROVIDER, API keys и т.д.
```
  
### Проверка
  
```bash
# Должно показать "database system is ready to accept connections"
docker compose logs postgres | grep "ready"
```
  
---
  
## 📋 ФАЗА 1: Модели данных
  
**Статус:** ✅ DONE  
**Файл:** `app/models.py`
  
### Что уже сделано
  
#### В класс `Request` (строки 36-39):
  
```python
amount: Optional[Decimal] = Field(default=None, decimal_places=2, description="Transaction amount")
currency: Optional[str] = Field(default="USD", max_length=3)
sender_id: Optional[str] = Field(default=None, max_length=100)
receiver_id: Optional[str] = Field(default=None, max_length=100)
```
  
#### В класс `AnalysisResult` (строки 75-76):
  
```python
risk_level: Optional[str] = Field(default="LOW", max_length=20, description="LOW, MEDIUM, HIGH, CRITICAL")
risk_factors: Optional[list[str]] = Field(default=[], sa_column=Column(JSON))
```
  
#### В класс `RequestCreate` (строки 121-124):
  
```python
amount: Optional[Decimal] = Field(default=None)
currency: Optional[str] = Field(default="USD")
sender_id: Optional[str] = None
receiver_id: Optional[str] = None
```
  
---
  
## 📋 ФАЗА 2: Tools — Sanctions & Thresholds
  
**Статус:** ✅ DONE  
**Файлы:** `app/services/tools/sanctions.py`, `thresholds.py`, `definitions.py`
  
### Файл: `app/services/tools/sanctions.py` — УЖЕ СОЗДАН
  
```python
"""
Sanctions and PEP checking tools.
MOCK implementations for demo.
"""
import json
  
SANCTIONS_LIST = {
    "ahmed ivanov": {"list": "OFAC_SDN", "reason": "Terrorist financing", "severity": "CRITICAL"},
    "shell corp ltd": {"list": "EU_SANCTIONS", "reason": "Money laundering", "severity": "CRITICAL"},
}
  
PEP_LIST = {
    "elena volkova": {"position": "Deputy Governor", "country": "Regionstan", "risk_level": "HIGH"},
}
  
def check_sanctions_list(entity_name: str) -> str:
    normalized = entity_name.lower().strip()
    if normalized in SANCTIONS_LIST:
        match = SANCTIONS_LIST[normalized]
        return json.dumps({"is_sanctioned": True, "entity_name": entity_name, **match})
    return json.dumps({"is_sanctioned": False, "entity_name": entity_name, "status": "CLEAN"})
  
def check_pep_status(person_name: str) -> str:
    normalized = person_name.lower().strip()
    if normalized in PEP_LIST:
        return json.dumps({"is_pep": True, **PEP_LIST[normalized]})
    return json.dumps({"is_pep": False, "person_name": person_name})
```
  
### Файл: `app/services/tools/thresholds.py` — УЖЕ СОЗДАН
  
```python
"""Transaction threshold validation."""
import json
  
THRESHOLDS = {"USD": 10000, "EUR": 10000, "DEFAULT": 10000}
  
def validate_amount_threshold(amount: float, currency: str = "USD") -> str:
    threshold = THRESHOLDS.get(currency.upper(), THRESHOLDS["DEFAULT"])
    breached = amount >= threshold
    structuring = threshold * 0.9 <= amount < threshold
    return json.dumps({
        "amount": amount,
        "threshold": threshold,
        "threshold_breached": breached,
        "structuring_suspected": structuring,
        "recommendation": "FILE_CTR" if breached else ("MANUAL_REVIEW" if structuring else "PROCEED"),
    })
```
  
### Файл: `app/services/tools/definitions.py` — УЖЕ ИЗМЕНЁН
  
Tool definitions и TOOL_FUNCTIONS уже настроены (строки 95-135, 267-274).
  
---
  
## 📋 ФАЗА 3: System Prompt
  
**Статус:** ✅ DONE  
**Файл:** `app/services/llm/base.py`
  
### Что уже сделано (строки 24-45):
  
```python
DEFAULT_SYSTEM_PROMPT = """You are a Senior AML/KYC Compliance Officer with access to verification tools.
  
CRITICAL INSTRUCTIONS:
1. For ANY person/company name → call check_sanctions_list
2. For high-value transactions → call check_pep_status  
3. ALWAYS call validate_amount_threshold
  
After gathering tool results, respond in JSON:
{
    "score": <0-100>,
    "categories": ["<category1>", ...],
    "summary": "<reasoning with tool results>",
    "risk_level": "<LOW|MEDIUM|HIGH|CRITICAL>",
    "risk_factors": ["<factor1>", ...]
}
  
Risk Levels:
- LOW (0-25): Clean checks, under threshold
- MEDIUM (26-50): PEP involvement or near threshold
- HIGH (51-75): Multiple flags, potential structuring
- CRITICAL (76-100): Sanctions match, definite structuring
"""
```
  
---
  
## 📋 ФАЗА 4: LLMResponse — Risk Fields
  
**Статус:** ⏳ TODO  
**Файл:** `app/services/llm/base.py`  
**Время:** 5 минут
  
### Изменение 1: Добавить поля в класс `LLMResponse`
  
**Найти** (около строки 68):
  
```python
class LLMResponse(BaseModel):
    score: Optional[int] = None
    categories: list[str] = []
    reasoning: str
    processed_content: Optional[str] = None
    tools_used: Optional[list[str]] = None
    trace: Optional[dict] = None
    mode: str = "analysis"
```
  
**Заменить на:**
  
```python
class LLMResponse(BaseModel):
    """
    Structured response from LLM analysis.
  
    Supports two modes:
    - Analysis mode: score and categories are populated
    - Chat mode: score is None, categories is empty, reasoning contains the response
    """
    score: Optional[int] = None  # None in chat mode
    categories: list[str] = []
    reasoning: str  # Maps to 'summary' in JSON response (or full chat response)
    processed_content: Optional[str] = None
    tools_used: Optional[list[str]] = None
    trace: Optional[dict] = None
    mode: str = "analysis"  # "analysis" | "chat"
    # AML-specific fields
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    risk_factors: list[str] = []
```
  
### Изменение 2: Обновить `_parse_llm_response`
  
**Найти** в методе `_parse_llm_response` (около строки 200-210):
  
```python
            # In chat mode, ensure score is None and categories is empty
            if mode == "chat":
                parsed['score'] = None
                parsed['categories'] = []
  
            return LLMResponse(**parsed)
```
  
**Заменить на:**
  
```python
            # In chat mode, ensure score is None and categories is empty
            if mode == "chat":
                parsed['score'] = None
                parsed['categories'] = []
                parsed.setdefault('risk_level', 'LOW')
                parsed.setdefault('risk_factors', [])
  
            # Ensure risk fields have defaults
            parsed.setdefault('risk_level', 'LOW')
            parsed.setdefault('risk_factors', [])
  
            return LLMResponse(**parsed)
```
  
---
  
## 📋 ФАЗА 5: Processor — Business Logic
  
**Статус:** ⏳ TODO  
**Файл:** `app/services/processor.py`  
**Время:** 15 минут
  
### Изменение 1: Метод `create_request` — сохранение transaction fields
  
**Найти** (около строки 105-111):
  
```python
        request = Request(
            input_text=data.input_text,
            context=data.context,
            group=group,
            created_by_user_id=self.user.id if self.user else None,
            created_at=datetime.utcnow(),
        )
```
  
**Заменить на:**
  
```python
        request = Request(
            input_text=data.input_text,
            context=data.context,
            amount=data.amount,
            currency=data.currency,
            sender_id=data.sender_id,
            receiver_id=data.receiver_id,
            group=group,
            created_by_user_id=self.user.id if self.user else None,
            created_at=datetime.utcnow(),
        )
```
  
### Изменение 2: Метод `analyze_request` — построить context для LLM
  
**Найти** (около строки 148-154):
  
```python
        # Call LLM service for analysis (using agent mode with tools)
        llm_response: LLMResponse = self.llm_service.analyze_with_tools(
            input_text=request.input_text,
            context=request.context,
            mode=mode,
        )
```
  
**Заменить на:**
  
```python
        # Build transaction context for LLM
        analysis_context = request.context or ""
        if request.amount is not None:
            analysis_context += f"""
  
Transaction Details:
- Amount: {request.amount} {request.currency or 'USD'}
- Sender: {request.sender_id or 'Unknown'}
- Receiver: {request.receiver_id or 'Unknown'}
"""
  
        # Call LLM service for analysis (using agent mode with tools)
        llm_response: LLMResponse = self.llm_service.analyze_with_tools(
            input_text=request.input_text,
            context=analysis_context.strip() if analysis_context.strip() else None,
            mode=mode,
        )
```
  
### Изменение 3: Сохранение risk fields в `AnalysisResult`
  
**Найти** (около строки 182-203) создание AnalysisResult:
  
```python
        result = AnalysisResult(
            request_id=request.id,
            result_type=mode,
            score=llm_response.score,
            categories=llm_response.categories,
            summary=summary,
            ...
        )
```
  
**Добавить после `categories=llm_response.categories,`:**
  
```python
            risk_level=llm_response.risk_level,
            risk_factors=llm_response.risk_factors,
```
  
Полный блок должен выглядеть так:
  
```python
        result = AnalysisResult(
            request_id=request.id,
            result_type=mode,
            score=llm_response.score,
            categories=llm_response.categories,
            risk_level=llm_response.risk_level,       # ADD
            risk_factors=llm_response.risk_factors,   # ADD
            summary=summary,
            processed_content=llm_response.processed_content,
            model_version=self.llm_service.get_model_version(),
            group=request.group,
            analyzed_by_user_id=self.user.id if self.user else None,
            llm_trace=llm_response.trace or {},
            validation_status=validation_result.status,
            validation_details=validation_result.details,
            human_feedback=None,
            feedback_comment=None,
            feedback_by_user_id=None,
            feedback_at=None,
            created_at=datetime.utcnow(),
        )
```
  
---
  
## 📋 ФАЗА 6: Validation — PII Detection
  
**Статус:** ⏳ TODO  
**Файл:** `app/services/validation.py`  
**Время:** 10 минут
  
### Изменение 1: Добавить PII patterns и функцию
  
**Найти** после `LOW_QUALITY_INDICATORS` (около строки 39):
  
```python
LOW_QUALITY_INDICATORS = [
    "i don't know",
    ...
]
```
  
**Добавить после этого блока:**
  
```python
# PII patterns that should never appear in LLM output
PII_PATTERNS = [
    (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN'),                              # US Social Security Number
    (r'\b\d{16}\b', 'CREDIT_CARD'),                                 # Credit card (16 digits)
    (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', 'CREDIT_CARD'), # Credit card with spaces/dashes
    (r'\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b', 'IBAN'),                  # International Bank Account
]
  
  
def check_pii_leakage(response_text: str) -> ValidationResult:
    """
    Checks if LLM response contains PII that should not be exposed.
  
    This is a security guardrail to prevent sensitive data leakage.
  
    Args:
        response_text: LLM response to scan
  
    Returns:
        ValidationResult with FAIL_PII_LEAK if PII found
    """
    if not response_text:
        return ValidationResult(status="PASS")
  
    found_pii = []
    for pattern, pii_type in PII_PATTERNS:
        if re.search(pattern, response_text):
            found_pii.append(pii_type)
  
    if found_pii:
        return ValidationResult(
            status="FAIL_PII_LEAK",
            details=f"Potential PII detected: {', '.join(set(found_pii))}"
        )
  
    return ValidationResult(status="PASS")
```
  
### Изменение 2: Добавить import re
  
**В начало файла добавить:**
  
```python
import re
```
  
### Изменение 3: Обновить `run_all_validations`
  
**Найти** (около строки 114-145):
  
```python
def run_all_validations(
    response_text: str,
    score: int,
    categories: list[str],
) -> ValidationResult:
    """..."""
    # Important: Score/categories consistency
    consistency_check = check_score_consistency(score, categories)
    if not consistency_check.passed:
        return consistency_check
  
    # Informational: Response quality
    quality_check = check_response_quality(response_text)
    if not quality_check.passed:
        return quality_check
  
    return ValidationResult(status="PASS")
```
  
**Заменить на:**
  
```python
def run_all_validations(
    response_text: str,
    score: int,
    categories: list[str],
) -> ValidationResult:
    """
    Runs all validation checks and returns the first failure (or PASS).
  
    Checks are run in priority order:
    1. Consistency (important)
    2. PII leakage (security critical)
    3. Quality (informational)
  
    Args:
        response_text: Full LLM response
        score: Numeric score
        categories: List of categories/factors
  
    Returns:
        ValidationResult with first failure or PASS
    """
    # 1. Important: Score/categories consistency
    consistency_check = check_score_consistency(score, categories)
    if not consistency_check.passed:
        return consistency_check
  
    # 2. Security: PII leakage check
    pii_check = check_pii_leakage(response_text)
    if not pii_check.passed:
        return pii_check
  
    # 3. Informational: Response quality
    quality_check = check_response_quality(response_text)
    if not quality_check.passed:
        return quality_check
  
    return ValidationResult(status="PASS")
```
  
---
  
## 📋 ФАЗА 7: Streamlit UI
  
**Статус:** ⏳ TODO  
**Файл:** `app/main.py`  
**Время:** 20 минут
  
### Изменение 1: Добавить import Decimal
  
**В начало файла добавить:**
  
```python
from decimal import Decimal
```
  
### Изменение 2: Transaction fields в форме
  
**Найти** в функции `render_new_analysis` блок с формой (около строки 435):
  
```python
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
```
  
**Вставить ПОСЛЕ блока с group и ПЕРЕД "Dynamic placeholder":**
  
```python
        # Transaction fields (only for analysis mode)
        if mode_key == "analysis":
            st.markdown("##### 💰 Transaction Details *(optional)*")
            tx_col1, tx_col2 = st.columns(2)
            with tx_col1:
                amount = st.number_input(
                    "Amount",
                    min_value=0.0,
                    value=0.0,
                    step=100.0,
                    help="Transaction amount (0 = not specified)"
                )
                sender_id = st.text_input(
                    "Sender",
                    placeholder="e.g., John Smith or ACC-001",
                    help="Sender name or account ID"
                )
            with tx_col2:
                currency = st.selectbox(
                    "Currency",
                    ["USD", "EUR", "GBP", "CHF", "JPY"],
                    help="Transaction currency"
                )
                receiver_id = st.text_input(
                    "Receiver",
                    placeholder="e.g., Shell Corp Ltd or ACC-002",
                    help="Receiver name or account ID"
                )
            st.markdown("---")
        else:
            # Chat mode - no transaction fields
            amount = 0.0
            currency = "USD"
            sender_id = None
            receiver_id = None
```
  
### Изменение 3: Передать transaction fields в RequestCreate
  
**Найти** (около строки 483-487):
  
```python
                    request_data = RequestCreate(
                        input_text=input_text.strip(),
                        context=context.strip() if context else None,
                        group=group,
                    )
```
  
**Заменить на:**
  
```python
                    request_data = RequestCreate(
                        input_text=input_text.strip(),
                        context=context.strip() if context else None,
                        group=group,
                        amount=Decimal(str(amount)) if amount > 0 else None,
                        currency=currency,
                        sender_id=sender_id.strip() if sender_id else None,
                        receiver_id=receiver_id.strip() if receiver_id else None,
                    )
```
  
### Изменение 4: Сохранить risk fields в session_state
  
**Найти** (около строки 493-506) блок `st.session_state.last_analysis_result`:
  
```python
                st.session_state.last_analysis_result = {
                    "request_id": request.id,
                    "result_id": result.id,
                    ...
                    "created_at": request.created_at.isoformat(),
                }
```
  
**Добавить поля перед закрывающей скобкой:**
  
```python
                    "risk_level": result.risk_level,
                    "risk_factors": result.risk_factors or [],
```
  
### Изменение 5: Отобразить risk level в результатах
  
**Найти** после блока с отображением score (около строки 556-557):
  
```python
                """, unsafe_allow_html=True)
  
            st.markdown("---")
```
  
**Вставить ПЕРЕД `st.markdown("---")`:**
  
```python
  
            # Risk Level display
            if result_data.get("risk_level") and result_data["risk_level"] != "LOW":
                risk_colors = {
                    "MEDIUM": "#ffc107",
                    "HIGH": "#dc3545",
                    "CRITICAL": "#721c24",
                }
                risk_color = risk_colors.get(result_data["risk_level"], "#6c757d")
  
                st.markdown(f"""
                <div style="text-align: center; margin-top: 1rem;">
                    <span style="background-color: {risk_color}; color: white; 
                           padding: 0.5rem 1rem; border-radius: 0.5rem; font-weight: bold;">
                        ⚠️ Risk Level: {result_data["risk_level"]}
                    </span>
                </div>
                """, unsafe_allow_html=True)
  
                # Risk factors
                if result_data.get("risk_factors"):
                    st.markdown("#### 🚩 Risk Factors")
                    for factor in result_data["risk_factors"]:
                        st.markdown(f"- {factor}")
```
  
### Изменение 6: Dashboard — показать risk level
  
**Найти** в функции `render_dashboard` (около строки 692):
  
```python
                    if result.result_type == "chat":
                        expander_title = f"💬 Chat #{result.id} | Group: {result.group}"
                    else:
                        expander_title = f"📊 Result #{result.id} | Score: {result.score} | {score_level} | Group: {result.group}"
```
  
**Заменить на:**
  
```python
                    if result.result_type == "chat":
                        expander_title = f"💬 Chat #{result.id} | Group: {result.group}"
                    else:
                        risk_badge = ""
                        if result.risk_level and result.risk_level != "LOW":
                            risk_badge = f" | ⚠️ {result.risk_level}"
                        expander_title = f"📊 Result #{result.id} | Score: {result.score} | {score_level}{risk_badge} | Group: {result.group}"
```
  
### Изменение 7: Evaluation — показать risk level
  
**Найти** в функции `render_evaluation` (около строки 868-870):
  
```python
                    if result.result_type == "chat":
                        expander_title = f"#{result.id} | 💬 Chat | {tag_str}"
                    else:
                        expander_title = f"#{result.id} | {score_level} ({result.score}) | {tag_str}"
```
  
**Заменить на:**
  
```python
                    if result.result_type == "chat":
                        expander_title = f"#{result.id} | 💬 Chat | {tag_str}"
                    else:
                        risk_badge = ""
                        if result.risk_level and result.risk_level != "LOW":
                            risk_badge = f" ⚠️{result.risk_level} |"
                        expander_title = f"#{result.id} |{risk_badge} {score_level} ({result.score}) | {tag_str}"
```
  
---
  
## 📋 ФАЗА 8: API Schemas
  
**Статус:** ⏳ TODO  
**Файл:** `app/api/schemas.py`  
**Время:** 10 минут
  
### Изменение 1: AnalyzeRequest — добавить transaction fields
  
**Найти** (строки 14-38):
  
```python
class AnalyzeRequest(BaseModel):
    """Request to analyze or chat with AI."""
    input_text: str = Field(..., max_length=5000, description="Primary input text to analyze or chat message")
    context: Optional[str] = Field(None, max_length=2000, description="Additional context")
    group: str = Field(default="default", max_length=50, description="Group for ABAC filtering")
    mode: str = Field(default="analysis", description="Mode: 'analysis' for scoring, 'chat' for conversational Q&A")
  
    model_config = {
        ...
    }
```
  
**Заменить на:**
  
```python
class AnalyzeRequest(BaseModel):
    """Request to analyze or chat with AI."""
    input_text: str = Field(..., max_length=5000, description="Primary input text to analyze or chat message")
    context: Optional[str] = Field(None, max_length=2000, description="Additional context")
    group: str = Field(default="default", max_length=50, description="Group for ABAC filtering")
    mode: str = Field(default="analysis", description="Mode: 'analysis' for scoring, 'chat' for conversational Q&A")
    # Transaction fields for AML analysis
    amount: Optional[float] = Field(None, ge=0, description="Transaction amount")
    currency: str = Field(default="USD", max_length=3, description="Currency code (USD, EUR, etc.)")
    sender_id: Optional[str] = Field(None, max_length=100, description="Sender name or account ID")
    receiver_id: Optional[str] = Field(None, max_length=100, description="Receiver name or account ID")
  
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "input_text": "Wire transfer to offshore account",
                    "context": "Customer flagged for unusual activity",
                    "group": "group_a",
                    "mode": "analysis",
                    "amount": 9500.00,
                    "currency": "USD",
                    "sender_id": "John Smith",
                    "receiver_id": "Shell Corp Ltd",
                },
                {
                    "input_text": "What are the common indicators of money laundering?",
                    "context": "I'm reviewing a suspicious transaction report.",
                    "group": "group_a",
                    "mode": "chat",
                }
            ]
        }
    }
```
  
### Изменение 2: RequestResponse — добавить transaction fields
  
**Найти** (строки 62-68):
  
```python
class RequestResponse(BaseModel):
    """Request details in API response."""
    id: int
    input_text: str
    context: Optional[str]
    group: str
    created_at: datetime
```
  
**Заменить на:**
  
```python
class RequestResponse(BaseModel):
    """Request details in API response."""
    id: int
    input_text: str
    context: Optional[str]
    group: str
    created_at: datetime
    # Transaction fields
    amount: Optional[float] = None
    currency: Optional[str] = None
    sender_id: Optional[str] = None
    receiver_id: Optional[str] = None
```
  
### Изменение 3: AnalysisResultResponse — добавить risk fields
  
**Найти** (строки 71-88):
  
```python
class AnalysisResultResponse(BaseModel):
    """Analysis result details in API response."""
    id: int
    request_id: int
    result_type: str = "analysis"
    score: Optional[int] = Field(default=None, ge=0, le=100)
    categories: list[str] = []
    summary: str
    processed_content: Optional[str]
    model_version: str
    group: str
    validation_status: str
    validation_details: Optional[str]
    human_feedback: Optional[bool]
    created_at: datetime
  
    # Observability - optional, only if requested
    llm_trace: Optional[dict] = None
```
  
**Заменить на:**
  
```python
class AnalysisResultResponse(BaseModel):
    """Analysis result details in API response."""
    id: int
    request_id: int
    result_type: str = "analysis"  # "analysis" | "chat"
    score: Optional[int] = Field(default=None, ge=0, le=100)  # None in chat mode
    categories: list[str] = []
    summary: str
    processed_content: Optional[str]
    model_version: str
    group: str
    validation_status: str
    validation_details: Optional[str]
    human_feedback: Optional[bool]
    created_at: datetime
    # Risk assessment fields
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    risk_factors: list[str] = []
    # Observability - optional, only if requested
    llm_trace: Optional[dict] = None
```
  
---
  
## 📋 ФАЗА 9: API Endpoints
  
**Статус:** ⏳ TODO  
**Файл:** `app/api/main.py`  
**Время:** 15 минут
  
### Изменение 1: Добавить import Decimal
  
**В начало файла (после других imports) добавить:**
  
```python
from decimal import Decimal
```
  
### Изменение 2: Endpoint `/analyze` — передать transaction fields
  
**Найти** (около строки 201-205):
  
```python
            request_data = RequestCreate(
                input_text=request.input_text,
                context=request.context,
                group=request.group,
            )
```
  
**Заменить на:**
  
```python
            request_data = RequestCreate(
                input_text=request.input_text,
                context=request.context,
                group=request.group,
                amount=Decimal(str(request.amount)) if request.amount else None,
                currency=request.currency,
                sender_id=request.sender_id,
                receiver_id=request.receiver_id,
            )
```
  
### Изменение 3: Endpoint `/analyze` — обновить response mapping
  
**Найти** (около строки 211-218):
  
```python
                request=RequestResponse(
                    id=req.id,
                    input_text=req.input_text,
                    context=req.context,
                    group=req.group,
                    created_at=req.created_at,
                ),
```
  
**Заменить на:**
  
```python
                request=RequestResponse(
                    id=req.id,
                    input_text=req.input_text,
                    context=req.context,
                    group=req.group,
                    created_at=req.created_at,
                    amount=float(req.amount) if req.amount else None,
                    currency=req.currency,
                    sender_id=req.sender_id,
                    receiver_id=req.receiver_id,
                ),
```
  
### Изменение 4: Endpoint `/analyze` — добавить risk fields в result
  
**Найти** (около строки 219-234):
  
```python
                result=AnalysisResultResponse(
                    id=result.id,
                    request_id=result.request_id,
                    result_type=result.result_type,
                    score=result.score,
                    categories=result.categories,
                    summary=result.summary,
                    processed_content=result.processed_content,
                    model_version=result.model_version,
                    group=result.group,
                    validation_status=result.validation_status,
                    validation_details=result.validation_details,
                    human_feedback=result.human_feedback,
                    created_at=result.created_at,
                    llm_trace=result.llm_trace,
                ),
```
  
**Заменить на:**
  
```python
                result=AnalysisResultResponse(
                    id=result.id,
                    request_id=result.request_id,
                    result_type=result.result_type,
                    score=result.score,
                    categories=result.categories,
                    summary=result.summary,
                    processed_content=result.processed_content,
                    model_version=result.model_version,
                    group=result.group,
                    validation_status=result.validation_status,
                    validation_details=result.validation_details,
                    human_feedback=result.human_feedback,
                    created_at=result.created_at,
                    risk_level=result.risk_level or "LOW",
                    risk_factors=result.risk_factors or [],
                    llm_trace=result.llm_trace,
                ),
```
  
### Изменение 5: Endpoint `/results` — добавить risk fields
  
**Найти** (около строки 276-293) в list comprehension:
  
```python
            return [
                AnalysisResultResponse(
                    id=r.id,
                    ...
                    llm_trace=r.llm_trace if include_trace else None,
                )
                for r in results
            ]
```
  
**Добавить перед `llm_trace`:**
  
```python
                    risk_level=r.risk_level or "LOW",
                    risk_factors=r.risk_factors or [],
```
  
### Изменение 6: Endpoint `/results/{result_id}` — добавить risk fields
  
**Найти** (около строки 333-348):
  
```python
            return AnalysisResultResponse(
                id=result.id,
                ...
                llm_trace=result.llm_trace if include_trace else None,
            )
```
  
**Добавить перед `llm_trace`:**
  
```python
                risk_level=result.risk_level or "LOW",
                risk_factors=result.risk_factors or [],
```
  
### Изменение 7: Endpoint `/results/needs-review` — добавить risk fields
  
**Найти** (около строки 465-481):
  
```python
            return [
                AnalysisResultResponse(
                    id=r.id,
                    ...
                    llm_trace=r.llm_trace,
                )
                for r in results
            ]
```
  
**Добавить перед `llm_trace`:**
  
```python
                    risk_level=r.risk_level or "LOW",
                    risk_factors=r.risk_factors or [],
```
  
---
  
## 📋 ФАЗА 10: Database Migration
  
**Статус:** ⏳ TODO  
**Время:** 5 минут
  
### Вариант A: Пересоздать БД (для dev)
  
```bash
# Если используется SQLite:
rm kyc.db
  
# Если используется PostgreSQL в Docker:
docker compose down -v
docker compose up -d postgres
```
  
### Вариант B: Миграция (для production)
  
```bash
# Если используется Alembic:
alembic revision --autogenerate -m "Add transaction and risk fields"
alembic upgrade head
```
  
### Проверка
  
```bash
# Запустить приложение
streamlit run app/main.py
  
# Или API
uvicorn app.api.main:app --reload
```
  
---
  
## 📋 ФАЗА 11: Тестирование
  
**Статус:** ⏳ TODO  
**Время:** 10 минут
  
### Test Case 1: Clean Transaction
  
```
Input: "Wire transfer for equipment purchase"
Amount: 5000
Currency: USD
Sender: ABC Corporation
Receiver: XYZ Supplies Inc
  
Expected:
- Score: 0-25 (LOW)
- Risk Level: LOW
- Tools called: check_sanctions_list (x2), validate_amount_threshold
```
  
### Test Case 2: Threshold Breach
  
```
Input: "International wire transfer"
Amount: 15000
Currency: USD
Sender: John Doe
Receiver: Jane Smith
  
Expected:
- Score: 26-50 (MEDIUM)
- Risk Level: MEDIUM
- Risk Factors: ["Threshold breached", "CTR required"]
```
  
### Test Case 3: Structuring Suspected
  
```
Input: "Multiple transfers today"
Amount: 9500
Currency: USD
Sender: John Doe
Receiver: Cash Depot LLC
  
Expected:
- Score: 51-75 (HIGH)
- Risk Level: HIGH
- Risk Factors: ["Structuring suspected"]
```
  
### Test Case 4: Sanctions Match
  
```
Input: "Payment for consulting services"
Amount: 5000
Currency: USD
Sender: Ahmed Ivanov
Receiver: Local Business
  
Expected:
- Score: 76-100 (CRITICAL)
- Risk Level: CRITICAL
- Risk Factors: ["OFAC SDN match", "Terrorist financing"]
```
  
### Test Case 5: PEP Involvement
  
```
Input: "Real estate purchase deposit"
Amount: 50000
Currency: USD
Sender: Elena Volkova
Receiver: Luxury Properties LLC
  
Expected:
- Score: 51-75 (HIGH)
- Risk Level: HIGH
- Risk Factors: ["PEP involvement", "High-value transaction"]
```
  
---
  
## ✅ Checklist
  
### Pre-Implementation
- [ ] Docker postgres running
- [ ] .env configured with LLM_PROVIDER and keys
- [ ] Existing DB backed up (if needed)
  
### Implementation
- [ ] ФАЗА 4: LLMResponse risk fields
- [ ] ФАЗА 5: Processor changes
- [ ] ФАЗА 6: Validation PII
- [ ] ФАЗА 7: Streamlit UI
- [ ] ФАЗА 8: API Schemas
- [ ] ФАЗА 9: API Endpoints
- [ ] ФАЗА 10: DB Migration
  
### Post-Implementation
- [ ] All test cases pass
- [ ] No linter errors
- [ ] API docs updated (/docs)
- [ ] Commit changes
  
---
  
## 📚 Quick Reference
  
### Risk Levels
  
| Level | Score Range | Meaning |
|-------|-------------|---------|
| LOW | 0-25 | Clean checks, under threshold |
| MEDIUM | 26-50 | PEP involvement or near threshold |
| HIGH | 51-75 | Multiple flags, potential structuring |
| CRITICAL | 76-100 | Sanctions match, definite structuring |
  
### Thresholds
  
| Currency | CTR Threshold | Structuring Zone |
|----------|---------------|------------------|
| USD | <img src="https://latex.codecogs.com/gif.latex?10,000%20|"/>9,000 - $9,999 |
| EUR | €10,000 | €9,000 - €9,999 |
| GBP | £10,000 | £9,000 - £9,999 |
  
### Mock Sanctions List
  
| Entity | List | Severity |
|--------|------|----------|
| Ahmed Ivanov | OFAC_SDN | CRITICAL |
| Shell Corp Ltd | EU_SANCTIONS | CRITICAL |
  
### Mock PEP List
  
| Person | Position | Risk |
|--------|----------|------|
| Elena Volkova | Deputy Governor | HIGH |
  
---
  
*Document generated: 2026-01-11*
  