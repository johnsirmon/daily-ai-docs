# Self-Learning Loops & Orchestration Frameworks — Guide & Gap Analysis

> **Audience:** AI engineers and architects building autonomous agent systems with
> orchestrated, self-improving loops and coordinated local-agent handoff.
> **Last updated:** 2026-02
> **Review cadence:** Monthly (frameworks evolve rapidly; check release notes of
> AutoGen, LangGraph, CrewAI, and Semantic Kernel at least monthly)

## Guidance Obsolescence

| Section | Review trigger | Last validated |
|---------|----------------|----------------|
| Framework comparison | Major framework release | 2026-02 |
| Self-learning loop patterns | New RLHF / self-critique research | 2026-02 |
| Agent handoff patterns | LangGraph / AutoGen API change | 2026-02 |
| Adoption path | New orchestration framework GA | 2026-02 |
| Governance implications | Team AI policy change | 2026-02 |

---

## Why this guide exists

Agentic AI systems are moving beyond single-agent, single-turn designs. Two orthogonal
advances are now converging:

1. **Self-learning loops** — agents that collect feedback, critique their own outputs,
   or run reward models to iteratively improve without manual retraining.
2. **Orchestration frameworks with built-in coordination** — graph-based or
   role-based runtimes (LangGraph, AutoGen, CrewAI) that handle state, routing, and
   **coordinated handoff** between specialised local agents.

Teams that ignore this shift pay a compounding cost:

- Agents plateau at their initial capability with no mechanism to improve.
- Pipelines are brittle: one agent's failure is not recoverable by a peer agent.
- No clear ownership when a subtask crosses agent boundaries.
- Governance gaps: no audit trail for which agent produced which output and why.

---

## Self-learning loop patterns

### Pattern 1 — Critic-Actor loop

```text
┌──────────┐  attempt   ┌──────────┐
│  Actor   │──────────▶│  Critic  │
│  Agent   │◀──────────│  Agent   │
└──────────┘  feedback  └──────────┘
     │  refined output
     ▼
  Downstream
```

The **Actor** produces an initial output. The **Critic** scores or annotates it
against a rubric. The Actor refines until the critic score exceeds a threshold.

**Frameworks:** AutoGen `AssistantAgent + CriticAgent`, LangGraph conditional edges.

### Pattern 2 — Reflective loop with memory

The agent stores past attempts in a short-term scratchpad and a long-term vector
store. On each iteration it retrieves relevant past failures to condition its next
attempt (self-RAG style).

**Frameworks:** LangGraph persistent checkpointing, AutoGen `TeachableAgent`.

### Pattern 3 — RLHF-lite online loop

Human or automated preference data is collected after each agent run. A lightweight
reward model is fine-tuned periodically (nightly or weekly) and swapped into the
pipeline. No full retraining is required.

**Frameworks:** Hugging Face `trl`, liteLLM proxy reward scoring.

---

## Orchestration frameworks — feature comparison

| Capability | LangGraph | AutoGen | CrewAI | Semantic Kernel |
|------------|-----------|---------|--------|-----------------|
| Built-in state machine / graph | ✅ first-class | ⚙️ via FSM helpers | ❌ sequential only | ⚙️ via Planner |
| Coordinated agent handoff | ✅ typed edges | ✅ `GroupChat` router | ✅ task delegation | ✅ `FunctionChoiceBehavior` |
| Persistent checkpointing | ✅ (LangGraph Cloud) | ⚙️ external | ❌ | ❌ |
| Local-first execution | ✅ | ✅ | ✅ | ✅ |
| MCP tool integration | ⚙️ custom node | ⚙️ custom tool | ⚙️ custom tool | ✅ native plugins |
| Self-learning / critic loop | ⚙️ via nodes | ✅ `CriticAgent` | ⚙️ via task feedback | ❌ |
| Streaming handoff events | ✅ | ✅ | ❌ | ✅ |
| Multi-modal agents | ⚙️ via LangChain | ✅ | ❌ | ✅ |

✅ = native support  ⚙️ = achievable with configuration  ❌ = not currently supported

---

## Agent handoff patterns

### Supervised handoff

A **Supervisor** agent receives a task, decomposes it, and delegates subtasks to
specialist agents. Each specialist returns a structured result; the Supervisor
assembles the final response.

```text
User ──▶ Supervisor ──▶ Researcher
                    ──▶ Coder
                    ──▶ Reviewer
                    ◀── assembled result
```

**Implementation:** AutoGen `GroupChat` with a custom speaker-selection function;
LangGraph `StateGraph` with conditional routing edges.

### Peer handoff (swarm)

Agents hand off directly to each other without a central supervisor. Each agent
decides whether to forward a task to a peer based on its own capability check.

```text
Agent-A ──▶ Agent-B ──▶ Agent-C
        ◀──────────────────────
```

**Implementation:** LangGraph typed edges; OpenAI Swarm (experimental).

### Capability-negotiated handoff

Before passing a task, the sending agent queries a **capability registry** to find
the best local agent for the next step. Useful in large deployments where agents are
dynamically registered.

**Implementation:** Custom MCP server acting as a registry; AutoGen runtime with
a custom agent selector.

---

## Gap analysis for this repository

| Gap | Current state | Recommended action |
|-----|---------------|--------------------|
| Self-learning loop tracking | Partial — `self-improving-agents` topic exists but lacks loop-specific keywords | New `self-learning-loops` topic added to `topics/topics.yaml` |
| Orchestration framework tracking | Partial — `agentic-workflows` topic; no AutoGen, LangGraph, CrewAI sources | New `local-agent-orchestration` topic + three new GitHub sources added |
| Agent handoff documentation | None | This guide + future pipeline-generated daily summaries |
| Local agent eval coverage | None | Add agent-handoff eval to the `agent-evals` topic sources |

---

## Adoption path

1. **Day 1** — Pull the latest daily report and scan the `local-agent-orchestration`
   and `self-learning-loops` sections for breaking changes.
2. **Week 1** — Prototype a Critic-Actor loop in LangGraph or AutoGen on a
   low-stakes subtask in your current project.
3. **Month 1** — Instrument the loop: record actor attempts, critic scores, and
   final outputs. Store in a vector DB for future retrieval.
4. **Month 2** — Add a supervised handoff between at least two specialised agents;
   use the comparison table above to choose the right framework for your topology.
5. **Quarter 1** — Evaluate RLHF-lite: collect preference pairs from the critic loop
   and train a lightweight reward model on `trl`.

---

## Governance implications

| Concern | Mitigation |
|---------|-----------|
| Runaway self-improvement | Cap iteration count; require human approval beyond N refinements |
| Audit trail loss during handoff | Emit structured handoff events to a log; tag each step with agent ID and timestamp |
| Model drift from online learning | Pin reward model version; require A/B test before deploying updated model |
| Data privacy in feedback loops | Scrub PII before storing critic annotations in vector stores |
| Agent impersonation | Sign handoff tokens; validate sender identity at each agent boundary |
