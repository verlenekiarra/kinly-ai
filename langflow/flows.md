# SilverCare Concierge — Langflow Flow Definitions

> These flows are used as MCP tools exposed to IBM Bob. Each flow = one tool callable via MCP protocol.
> All flows use **Gemini API** as LLM and **Astra DB** as vector store.

---

## Tool 1: `check_medication_schedule`

**Purpose:** Answer "when should I take my medicine?" using uploaded prescription data (RAG).

### Node-by-Node

```
[Chat Input]
    │  fields: elderly_name (str), current_time (str), question (str)
    ▼
[Astra DB Retriever]
    │  collection: prescriptions
    │  embedding: text-embedding-004 (Gemini)
    │  search_query: {elderly_name} + {question}
    │  top_k: 5
    ▼
[Prompt Template]  ← see prompts.md → MEDICATION_SCHEDULE_PROMPT
    │  variables: {context}, {elderly_name}, {current_time}, {question}
    ▼
[Gemini LLM]
    │  model: gemini-1.5-flash
    │  temperature: 0.1   ← low temp for factual answers
    ▼
[Output Parser / Chat Output]
    │  format: plain text (simple language)
```

### Input Schema (MCP)
```json
{
  "elderly_name": "string",
  "current_time": "string (ISO 8601 or natural: '08:00 pagi')",
  "question": "string"
}
```

### Output
```json
{
  "schedule": "string",
  "next_dose_time": "string",
  "source": "prescription_rag | not_found"
}
```

---

## Tool 2: `check_drug_interaction`

**Purpose:** Cross-check if 2+ drugs are safe to take together.

### Node-by-Node

```
[Chat Input]
    │  fields: drug_list (list[str])
    ▼
[Astra DB Retriever]
    │  collection: drug_interactions
    │  embedding: text-embedding-004
    │  search_query: join(drug_list, " + ")
    │  top_k: 10
    ▼
[Prompt Template]  ← DRUG_INTERACTION_PROMPT
    │  variables: {context}, {drug_list}
    ▼
[Gemini LLM]
    │  model: gemini-1.5-flash
    │  temperature: 0.0   ← strictly factual
    ▼
[Structured Output Parser]
    │  fields: status (safe|warning|danger), explanation, recommendation
    ▼
[Chat Output]
```

### Input Schema (MCP)
```json
{
  "drug_list": ["string", "string", "..."]
}
```

### Output
```json
{
  "status": "safe | warning | danger",
  "explanation": "string",
  "recommendation": "string",
  "source": "interaction_db | not_found"
}
```

---

## Tool 3: `report_health_symptom`

**Purpose:** Analyze reported symptoms and score urgency level.

### Node-by-Node

```
[Chat Input]
    │  fields: symptom_description (str), last_medication_taken (str)
    ▼
[Astra DB Retriever]
    │  collection: drug_side_effects
    │  embedding: text-embedding-004
    │  search_query: {symptom_description} + {last_medication_taken}
    │  top_k: 5
    ▼
[Prompt Template]  ← SYMPTOM_ANALYSIS_PROMPT
    │  variables: {context}, {symptom_description}, {last_medication_taken}
    ▼
[Gemini LLM]
    │  model: gemini-1.5-pro   ← higher reasoning for medical context
    │  temperature: 0.1
    ▼
[Structured Output Parser]
    │  fields: urgency_level (1-5), possible_cause, action_required
    ▼
[Conditional Router]
    │  if urgency_level >= 4 → append "Segera hubungi 119 / dokter"
    │  if urgency_level <= 3 → standard recommendation
    ▼
[Chat Output]
```

### Input Schema (MCP)
```json
{
  "symptom_description": "string",
  "last_medication_taken": "string"
}
```

### Output
```json
{
  "urgency_level": 1,
  "possible_cause": "string",
  "action_required": "string",
  "emergency_flag": false
}
```

---

## Tool 4: `generate_caregiver_leave_request`

**Purpose:** Draft a formal caregiver leave request letter for HR submission.

### Node-by-Node

```
[Chat Input]
    │  fields: employee_name (str), medical_reason (str),
    │          duration_days (int), parent_name (str), relationship (str)
    ▼
[Prompt Template]  ← CAREGIVER_LEAVE_PROMPT
    │  variables: all input fields + today's date
    │  NOTE: No RAG needed — purely generative with template
    ▼
[Gemini LLM]
    │  model: gemini-1.5-flash
    │  temperature: 0.3
    ▼
[Output Parser]
    │  format: formal letter (plain text)
    ▼
[Chat Output]
```

### Input Schema (MCP)
```json
{
  "employee_name": "string",
  "medical_reason": "string",
  "duration_days": "integer",
  "parent_name": "string",
  "relationship": "string (e.g. Ibu, Ayah)"
}
```

### Output
```json
{
  "draft_letter": "string (formal Indonesian HR letter)",
  "summary": "string"
}
```

---

## Astra DB Collections Required

| Collection | Content | Embedding Field |
|---|---|---|
| `prescriptions` | Resep dokter per pasien (PDF parsed) | `prescription_text` |
| `drug_interactions` | Database interaksi obat (e.g. Drugs@FDA) | `interaction_text` |
| `drug_side_effects` | Efek samping per obat | `side_effect_text` |

---

## Notes
- All flows must have a **Safety Gate node** before LLM: reject inputs containing requests to change dosage or diagnosis.
- Each flow exposes a `/api/v1/run/{flow_id}` endpoint that mcp-proxy wraps as an MCP tool.
- See `prompts.md` for all system prompt templates.
