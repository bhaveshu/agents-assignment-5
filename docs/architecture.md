# Financial Approval System: System Architecture Documentation

**UCLA Extension — Agentic AI Course**  
**Author:** Bhavesh  

This document details the architectural layout, state machine transitions, human-in-the-loop (HITL) escalation matrix, and safety guardrails governing the Financial Approval System.

---

## 1. System Architecture & Component Interactions

The system adopts a decoupled, multi-tier agentic architecture connecting a Next.js / CopilotKit frontend to a LangGraph state graph executed inside an asynchronous FastAPI server.

```mermaid
flowchart TD
    subgraph ClientLayer ["Client Layer (Next.js 14)"]
        UI["User Interface (Browser)"]
        CC["CopilotChat Component"]
        RF["Request Form Component"]
        AD["Approval Dashboard Component"]
        AP["ApprovalPanel (Interrupt Modal)"]
    end

    subgraph TransportLayer ["Transport & API Layer"]
        ProxyRoute["/api/copilotkit (Next.js App Router)"]
        HistoryRoute["/api/pipeline/history (Proxy)"]
        SSEStream["Server-Sent Events (SSE Stream)"]
    end

    subgraph BackendLayer ["Agentic Execution Engine (FastAPI + LangGraph)"]
        FastAPIServer["FastAPI Server (:8000)"]
        AGUI["AG-UI LangGraph Protocol Bridge"]
        StateGraph["StateGraph (8 Nodes, 6 Routing Functions)"]
        SQLiteCheckpointer[("SQLite Checkpointer (checkpoints.db)")]
    end

    subgraph ModelLayer ["Model & Observability Providers"]
        LLM["Google Gemini / OpenAI (LLM Provider)"]
        LangSmith["LangSmith Platform (Traces & Datasets)"]
    end

    %% Interactions
    UI --> CC
    UI --> RF
    UI --> AD
    CC --> ProxyRoute
    RF --> ProxyRoute
    AD --> HistoryRoute
    ProxyRoute --> AGUI
    HistoryRoute --> FastAPIServer
    AGUI --> StateGraph
    StateGraph --> SQLiteCheckpointer
    StateGraph --> LLM
    StateGraph -.->|"Traces & Spans"| LangSmith
    StateGraph -->|"Interrupt Event"| SSEStream
    SSEStream --> AP
    AP -->|"resolve(decision)"| AGUI
```

### Component Breakdown
1. **Frontend Presentation**:
   - `CopilotChat`: Conversational UI providing natural language intake and workflow explanations.
   - `RequestForm`: Structured input form allowing direct parameter entry with client-side validation.
   - `ApprovalPanel`: Dynamic modal rendered via `useLangGraphInterrupt()` whenever human intervention is required.
   - `ApprovalDashboard`: Real-time analytics view providing executive KPIs, budget tracking, and pipeline execution logs.
2. **Transport & Protocol**:
   - Next.js API route (`/api/copilotkit`) proxies requests to FastAPI using CopilotKit's `LangGraphHttpAgent`.
   - Communication follows an asynchronous SSE streaming protocol supporting token streaming, tool calls, and execution interrupts.
3. **Execution & Checkpointing**:
   - FastAPI hosts the `LangGraphAGUIAgent` attached to an `AsyncSqliteSaver` checkpointer.
   - Interrupt states persist directly to disk (`checkpoints.db`), ensuring fault tolerance and zero in-memory state loss across server restarts.
4. **LLM & Observability**:
   - Powered by Gemini (`gemini-3.8-flash`) or OpenAI (`gpt-4o-mini`) via unified LangChain chat wrappers.
   - Every node execution, prompt, model completion, and interrupt resolution is traced in LangSmith under the `financial-approval-system` project.

---

## 2. State Machine Diagram & Workflow Transitions

The state machine coordinates 8 nodes and 6 conditional routers. It enforces early validation exits and escalates to human reviewers as request risk increases.

```mermaid
stateDiagram-v2
    [*] --> submit_request: New Financial Request

    state submit_request {
        [*] --> ValidateInput
        ValidateInput --> SanitizeText
    }

    submit_request --> handle_rejection: is_valid == False (Negative / Over $100k / Injection / Bad Dept)
    submit_request --> assess_risk: is_valid == True

    state assess_risk {
        [*] --> CallLLM
        CallLLM --> ClassifyTier
    }

    assess_risk --> validate_budget: Risk == "low" (<= $10,000)
    assess_risk --> manager_review: Risk in ["medium", "high", "critical"]

    state validate_budget {
        [*] --> CheckDeptBudget
    }

    validate_budget --> process_request: Low Risk & Within Budget
    validate_budget --> manager_review: Low Risk & OVER Budget

    state manager_review {
        [*] --> PauseForManager: interrupt()
        PauseForManager --> ResumeWithDecision
    }

    manager_review --> handle_rejection: Manager Rejects
    manager_review --> validate_budget: Manager Approves (Medium Risk)
    manager_review --> finance_review: Manager Approves (High or Critical Risk)

    state validate_budget_med {
        [*] --> CheckBudgetAfterManager
    }
    validate_budget --> process_request: Medium Risk & Within Budget
    validate_budget --> finance_review: Medium Risk & OVER Budget

    state finance_review {
        [*] --> PauseForFinance: interrupt()
        PauseForFinance --> ResumeWithFinanceDecision
    }

    finance_review --> handle_rejection: Finance Rejects
    finance_review --> process_request: High Risk & Approved
    finance_review --> final_signoff: Critical Risk & Approved

    state final_signoff {
        [*] --> PauseForExec: interrupt()
        PauseForExec --> ResumeWithExecDecision
    }

    final_signoff --> handle_rejection: Executive Rejects
    final_signoff --> process_request: Executive Approves

    state process_request {
        [*] --> MaskPII
        MaskPII --> MarkApproved
    }

    state handle_rejection {
        [*] --> IdentifyRejector
        IdentifyRejector --> MarkRejected
    }

    process_request --> [*]: Request Completed (Approved)
    handle_rejection --> [*]: Request Completed (Rejected)
```

---

## 3. Human-in-the-Loop (HITL) Decision Matrix

The table below outlines when the system pauses execution for human decision-makers versus when it executes autonomously.

| Request Amount | AI Risk Level | Priority | Department Budget Status | Required Human Review Stages | Human Reviews | Automated Behavior / Path |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| $\le \$0$ or $> \$100\text{k}$ | *Bypassed* | Any | *Not checked* | **None** (Rejected immediately) | 0 | Auto-rejected at intake (`submit_request` $\rightarrow$ `handle_rejection`) |
| Invalid Dept | *Bypassed* | Any | *Not checked* | **None** (Rejected immediately) | 0 | Auto-rejected at intake (`submit_request` $\rightarrow$ `handle_rejection`) |
| $\le \$10,000$ | **Low** | Low / Normal | Within Budget | **None** (Auto-Approved) | 0 | `submit` $\rightarrow$ `assess_risk` $\rightarrow$ `validate_budget` $\rightarrow$ `process_request` |
| $\le \$10,000$ | **Low** | Low / Normal | **Over Budget** | **Manager Review** | 1 | `submit` $\rightarrow$ `assess_risk` $\rightarrow$ `budget` $\rightarrow$ **`manager`** $\rightarrow$ `process` |
| $\$10,001$ – $\$50,000$ | **Medium** | Low / Normal | Within Budget | **Manager Review** | 1 | `submit` $\rightarrow$ `assess_risk` $\rightarrow$ **`manager`** $\rightarrow$ `budget` $\rightarrow$ `process` |
| $\$10,001$ – $\$50,000$ | **Medium** | Low / Normal | **Over Budget** | **Manager + Finance** | 2 | `submit` $\rightarrow$ `assess` $\rightarrow$ **`manager`** $\rightarrow$ `budget` $\rightarrow$ **`finance`** $\rightarrow$ `process` |
| $\$50,001$ – $\$100,000$ | **High** | Low / Normal | Any | **Manager + Finance** | 2 | `submit` $\rightarrow$ `assess` $\rightarrow$ **`manager`** $\rightarrow$ **`finance`** $\rightarrow$ `process` |
| $> \$50,000$ | **Critical** | **Urgent** | Any | **Manager + Finance + Executive** | 3 | `submit` $\rightarrow$ `assess` $\rightarrow$ **`manager`** $\rightarrow$ **`finance`** $\rightarrow$ **`final_signoff`** $\rightarrow$ `process` |

---

## 4. Safety Guardrail Implementation Details

The safety architecture operates on a **dual-gate defense-in-depth model**: pre-execution input validation and post-execution output filtering.

### A. Input Validation Gates (`input_validator.py`)
1. **Mathematical Boundary Gate**:
   - `amount <= 0`: Rejects with `"Amount must be positive"`.
   - `amount > BUDGET_CEILING` ($100,000.00): Rejects with `"Amount exceeds budget ceiling of $100,000.00"`.
2. **Cost Center Whitelist Gate**:
   - Strictly enforces department membership in `['engineering', 'marketing', 'operations', 'research', 'hr']`.
   - Unrecognized departments (e.g. `'finance'`, `'executive'`, `'sales'`) are blocked.
3. **Payload Buffer Gate**:
   - Request Title: Capped at 200 characters.
   - Request Description: Capped at 2,000 characters.
   - Business Justification: Capped at 2,000 characters.
4. **Code & Prompt Injection Sanitization**:
   - Evaluates input strings against blocklist patterns using case-insensitive substring scanning:
     - SQL Injection: `drop table`, `delete from`, `insert into`, `update set`, `union select`, `' or '1'='1`, `'; --`
     - Cross-Site Scripting (XSS): `<script>`, `javascript:`, `onclick=`, `onerror=`
     - Arbitrary Code Execution: `eval(`, `__import__`, `os.system`, `subprocess`

### B. Output Redaction & Filtering (`output_filter.py`)
1. **PII Redaction**:
   - **SSN**: Pattern `\b\d{3}-\d{2}-\d{4}\b` $\rightarrow$ replaced with `***-**-XXXX`
   - **Credit Card**: Pattern `\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b` $\rightarrow$ replaced with `****-****-****-XXXX`
   - **Email**: Pattern `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b` $\rightarrow$ replaced with `[EMAIL REDACTED]`
   - **Phone**: Pattern `\b\d{3}[-.]?\d{3}[-.]?\d{4}\b` $\rightarrow$ replaced with `***-***-XXXX`
2. **Context-Preserving Financial Masking**:
   - Dollar amounts are masked to conceal large figures while keeping cents/suffixes visible for accounting audits (e.g. `$45,000.00` $\rightarrow$ `$***.00`).
   - Bank account numbers (8+ consecutive digits) mask leading digits while preserving the last 4 (e.g. `1234567890` $\rightarrow$ `******7890`).
