# HR Policy RAG Assistant - Project Metrics & Impact

## 🚀 Overview

Developed a Retrieval-Augmented Generation (RAG) assistant for querying internal HR policies, with emphasis on reliable retrieval, grounded responses, automated evaluation, observability, API resilience, and guardrails.

The system uses LangChain for orchestration, Jina embeddings for semantic representation, Qdrant Cloud for vector search, Groq for LLM inference, Portkey as an AI gateway, and LangSmith for tracing and evaluation.

---

## 📊 Current Baseline Evaluation — LangSmith

The latest evaluation uses a **32-case evaluation dataset** covering:

* Direct factual questions
* Numeric and limit-based questions
* Conditional questions
* Multi-fact questions
* Tricky/ambiguous questions
* Unsupported questions
* Out-of-domain questions

Evaluation is performed using automated **LLM-as-a-judge** evaluators for correctness and groundedness.

### Baseline Results

| Metric           |     Result |
| ---------------- | ---------: |
| Evaluation cases |     **32** |
| Correctness      |    **96%** |
| Groundedness     |    **84%** |
| Error rate       |     **3%** |
| P50 latency      | **14.15s** |
| P99 latency      | **21.98s** |

### Interpretation

* **96% correctness** indicates that the assistant generally produces answers matching the expected responses across the evaluation dataset.
* **84% groundedness** identifies a clear improvement opportunity around ensuring generated answers remain fully supported by retrieved policy context.
* **3% error rate** indicates that some evaluation requests still fail and require reliability investigation.
* **14.15s P50 / 21.98s P99** provide a baseline for subsequent latency optimization.
* The 32-case dataset provides broader regression coverage than the original 10-case evaluation.

> **Important:** These are baseline measurements. They should be treated as the starting point for subsequent engineering improvements rather than final performance claims.

---

## 🧪 Evaluation Strategy

The evaluation pipeline is designed to support regression testing after changes to prompts, retrieval, models, guardrails, or other RAG components.

### Evaluation flow

```text
32-case HR Policy Dataset
          ↓
      RAG Assistant
          ↓
   ┌──────┴──────┐
   ↓             ↓
Correctness   Groundedness
   ↓             ↓
   └──────┬──────┘
          ↓
       LangSmith
```

The dataset intentionally includes both answerable and unsupported questions so that the system is evaluated not only on whether it produces the expected answer, but also on whether it avoids generating unsupported information.

---

## 🏗️ Technical Architecture

### 1. Document Processing & Retrieval — Jina + Qdrant

HR policy documents are chunked and transformed into embeddings using `jina-embeddings-v2-base-en`.

The resulting vectors are stored in a Qdrant Cloud collection and retrieved using semantic similarity.

The application separates vector-store creation from retrieval:

* `build_vector_store()` creates/uploads embeddings.
* `load_vector_store()` connects to the existing Qdrant collection.
* Evaluation runs reuse the existing collection rather than rebuilding the vector store.

### 2. LLM Engine — Groq

Uses `openai/gpt-oss-20b` through Groq for response generation.

### 3. API Gateway & Reliability — Portkey

LLM requests are routed through Portkey to provide an additional gateway layer for provider interaction and resilience.

Transient API failures such as `429 Too Many Requests` are handled through retry/backoff behavior.

The current evaluation still reports a **3% error rate**, so reliability remains an active improvement area rather than a completed 0%-error claim.

### 4. Evaluation & Observability — LangSmith

LangSmith is used for:

* Request tracing
* Evaluation datasets
* LLM-as-a-judge evaluation
* Correctness scoring
* Groundedness scoring
* Latency monitoring
* Experiment comparison

The evaluation dataset can be reused across experiments, allowing baseline and improved versions of the system to be compared using the same test cases.

### 5. Guardrails

Input/output validation is used to handle:

* Prompt injection attempts
* Unsupported questions
* Out-of-domain queries
* Responses that should remain constrained to retrieved policy information

The effectiveness of these guardrails will be quantified through the evaluation suite as improvements are made.

### 6. Containerization

The application environment is containerized using Docker to provide reproducible execution across development and deployment environments.

---

# 🔬 Current Engineering Findings

The baseline evaluation identified three areas for improvement:

### 1. Grounding

**Current:** 84%

The largest quality gap is between correctness and groundedness.

Next investigation:

* Inspect low-groundedness examples.
* Analyze retrieved chunks.
* Determine whether failures originate from retrieval, context selection, prompting, or unsupported-query handling.
* Apply one controlled improvement.
* Re-run the same 32-case dataset.

Target evidence:

```text
Baseline groundedness → Improved groundedness
84%                    → X%
```

---

### 2. Reliability

**Current error rate:** 3%

The failed evaluation run should be inspected to determine whether the failure originated from:

* API rate limiting
* Retry configuration
* LLM provider failure
* Timeout
* Application exception
* Evaluation/judge failure

After identifying the cause, make a targeted reliability improvement and rerun the same dataset.

Target evidence:

```text
Baseline error rate → Improved error rate
3%                  → X%
```

---

### 3. Latency

**Current baseline:**

```text
P50: 14.15s
P99: 21.98s
```

Latency should be profiled before optimization rather than optimizing blindly.

Potential areas to investigate:

* Embedding latency
* Qdrant retrieval latency
* LLM generation latency
* Portkey overhead/retries
* Evaluation/judge latency
* Repeated model initialization
* Unnecessary retrieval or processing

Target evidence:

```text
Baseline P50 → Improved P50
14.15s        → Xs
```

---

# 🎯 Planned Improvement Experiments

## Experiment 1 — Groundedness Improvement

**Baseline:** 84% groundedness

Investigate low-groundedness cases and improve context-constrained answering/retrieval behavior.

Measure the same 32 cases before and after the change.

---

## Experiment 2 — Reliability Improvement

**Baseline:** 3% error rate

Identify the failed evaluation request and improve the relevant retry/error-handling mechanism.

Measure successful completion across the same evaluation dataset.

---

## Experiment 3 — Latency Optimization

**Baseline:**

* P50: 14.15s
* P99: 21.98s

Profile the application trace and optimize the actual bottleneck.

Measure latency using the same workload after the change.

---

# 💼 Resume Bullet Candidates

## Current Baseline Version

### AI / GenAI Engineering

* **Built** a RAG-based HR Policy Assistant using LangChain, Jina embeddings, Qdrant Cloud, and Groq, and developed a **32-case evaluation suite** spanning factual, numeric, conditional, multi-fact, unsupported, and out-of-domain queries.

* **Engineered** an automated LangSmith evaluation pipeline using LLM-as-a-judge scoring, establishing a **96% correctness and 84% groundedness baseline** for regression testing of RAG responses.

### Reliability / Backend

* **Hardened** LLM inference with Portkey as an API gateway and retry layer, while using LangSmith tracing to identify failures and establish a **3% baseline error rate** for subsequent reliability improvements.

### Evaluation / Observability

* **Implemented** evaluation-driven observability with LangSmith, tracking correctness, groundedness, failures, and latency across **32 test cases**, establishing **14.15s P50 and 21.98s P99 latency baselines** for optimization.

---

# ⭐ Target Resume Bullets After Improvement

These should only be used **after the improvements are actually measured**.

* **Improved** RAG response groundedness from **84% to X%** across a 32-case evaluation suite by analyzing retrieval failures and strengthening context-constrained response generation.

* **Reduced** evaluation error rate from **3% to X%** by diagnosing transient LLM/API failures and improving gateway retry and failure-handling behavior with Portkey.

* **Optimized** RAG response latency from **14.15s to Xs P50** by profiling the retrieval and generation pipeline and eliminating the identified performance bottleneck.

* **Built** an evaluation-driven RAG testing framework in LangSmith covering **32 cases across seven query categories**, enabling repeatable regression testing after changes to retrieval, prompts, models, and guardrails.

---

# 📌 Current Project Status

**Baseline established — improvement experiments pending.**

Current evidence:

```text
Evaluation cases       32
Correctness            96%
Groundedness           84%
Error rate              3%
P50 latency            14.15s
P99 latency            21.98s
```

The next objective is **not to artificially increase the scores**.

The next objective is to identify the actual failure modes, make controlled engineering changes, and measure the resulting improvement against the same baseline.
