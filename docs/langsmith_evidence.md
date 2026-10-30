# LangSmith Observability & Production Evidence

**Project Name:** `financial-approval-system`  
**Dataset Name:** `financial-approval-eval` (ID: `b021c994-abf2-492a-9ffe-7fa0aa564835`)  
**Student:** Bhavesh  
**Course:** UCLA Extension — Agentic AI (Week 5)  

---

## Overview

This document presents the visual evidence and operational telemetry captured from our live LangSmith dashboard during production runs of the Financial Approval System. It covers:
1. **Full Workflow Execution Trace** (visualizing the end-to-end LangGraph traversal)
2. **Annotated Interrupt Points** (demonstrating human-in-the-loop state pausing and resumption)
3. **Evaluation Dataset & Testing Dashboard** (the 12 benchmark evaluation test cases)
4. **Production Run & Latency Metrics** (p50/p99 execution performance)
5. **Token Consumption & Cost Analysis** (production usage economics)

---

## 1. Full Workflow Execution Trace

When a request is processed (in this example, the **"Vacation"** expense for $20,000 in the Engineering department), LangGraph executes the entire chain of nodes under a unified root run.

As shown in the trace below:
- **`submit_request`**: Validates input boundaries and applies text sanitization.
- **`assess_risk`**: Invokes the LLM (`gemini-3.8-flash`) to categorize risk as **Medium** based on the $20,000 amount.
- **`manager_review`**: Triggers a human-in-the-loop interrupt, pausing the workflow in SQLite checkpoints until the manager approves.
- **`validate_budget`**: Confirms that $20,000 fits within the $50,000 Engineering budget ($30,000 remaining).
- **`process_request`**: Formats the final approval and applies output filtering before returning to the user.

![Full Workflow Trace](images/vacation.png)

---

## 2. Annotated Interrupt Point (Human-in-the-Loop in Action)

This screenshot captures the exact moment the graph pauses for human intervention at the **`manager_review`** node.

Key observations from the trace:
- The node initiates an `interrupt()` payload containing the request metadata (`amount: $20,000`, `risk_level: medium`, `department: engineering`).
- The graph transitions to a paused state, serializing execution state to `checkpoints.db`.
- When the human reviewer approves the request in the CopilotKit `ApprovalPanel` modal, a resume command is dispatched.
- The node resumes execution, appends the decision object (`{"approved": true, "reviewer": "Manager", "stage": "manager_review"}`) to the `decisions` list, and proceeds to budget validation.

![Annotated Interrupt Point](images/interrupt.png)

---

## 3. Evaluation Results Dashboard & Testing Dataset

In Part 5, we uploaded our 12-case evaluation benchmark to LangSmith via `upload_to_langsmith()`.

Below is the live view from the **Datasets & Testing** tab for **`financial-approval-eval`**:
- All 12 test cases are registered with their respective input parameters (amounts, departments, descriptions) and expected outputs (approval status, risk level, required review stages).
- This dataset serves as our reproducible ground-truth benchmark for evaluating the Three-Layer Evaluation framework (scoring 0.99 overall).

![Evaluation Dataset Dashboard](images/dataset.png)

---

## 4. Performance & Latency Analysis

From the LangSmith project monitoring dashboard, we tracked response latencies across our live interaction sessions and evaluation runs:

Key metrics:
- **Autonomous Path (Low Risk)**: Completes in ~1.0 to 1.2 seconds (dominated by the single `assess_risk` LLM call; deterministic nodes like validation and budget arithmetic execute in < 3ms).
- **Human-in-the-Loop Path (Medium / High / Critical)**: Latency is governed by human response time. The system safely stays paused indefinitely in SQLite without holding open active threads or consuming server resources.
- The chart below illustrates the run volume and latency distributions captured during our testing sessions.

![Production Runs and Latency](images/runs_and_latency.png)

---

## 5. Cost Analysis

Because our system implements **strict input validation before the first LLM call**, invalid requests (such as negative amounts, over-ceiling $100k requests, and invalid departments) are rejected immediately at `submit_request` with **zero LLM cost**.

For valid requests:
- Each risk assessment averages ~140 prompt tokens and ~35 completion tokens.
- With modern Flash models (`gemini-3.8-flash` / `gpt-4o-mini`), each request costs a fraction of a cent (~$0.00004).
- The full 12-case Three-Layer Evaluation suite (which executes over 100 LLM calls across RAGAS and LLM judges) ran for approximately **$0.02 total**.

Below is the cumulative cost tracking recorded in the LangSmith dashboard:

![Total Cost Analysis](images/total_cost.png)
