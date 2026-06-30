# Darius Local Model Training Plan

**Goal:** Train a custom LLM ("Darius") to replace external API dependency for agent orchestration and domain-specific tasks.

---

## Phase 1: Data Collection (Now → Q3 2026)

You're already collecting training data. Every interaction is a future training example:

| Data Source | Format | Location | Volume |
|-------------|--------|----------|--------|
| Approved proposals | task → code output | `tickets` table (status=done) | ~70 tickets |
| Darius sessions | multi-turn conversations | `darius_sessions` table | Growing daily |
| Task memory | task + decision (approved/rejected) | `task_memory` table (pgvector) | 100+ entries |
| Agent routing | task → correct agent classification | `tickets` table (agent field) | All tickets |
| OrthoFlow classifications | invoice text → category | `invoices.coded_json` | Per client usage |
| HTC interactions | caregiver queries → responses | Future (localStorage → DB) | After launch |

### Export Script (run monthly)
```python
# scripts/export_training_data.py
import psycopg2, json

conn = psycopg2.connect("postgresql://kiro:kiro_secret@postgres:5432/kiro")
cur = conn.cursor()

# Instruction-tuning pairs from approved tickets
cur.execute("SELECT task, agent, proposal FROM tickets WHERE status='done' AND proposal IS NOT NULL")
pairs = []
for task, agent, proposal in cur.fetchall():
    pairs.append({
        "instruction": task[:2000],
        "input": f"Agent: {agent}",
        "output": proposal[:4000],
    })

with open("/app/data/training/instruction_pairs.jsonl", "w") as f:
    for p in pairs:
        f.write(json.dumps(p) + "\n")

print(f"Exported {len(pairs)} training pairs")
```

---

## Phase 2: Base Model Selection (Q3 2026)

| Model | Size | VRAM Required | Strengths |
|-------|------|---------------|-----------|
| Llama 3.1 8B | 8B | 8GB (Q4) | Fast, good for routing/classification |
| Llama 3.1 70B | 70B | 40GB (Q4) | Strong reasoning, code generation |
| Mistral 7B | 7B | 6GB (Q4) | Fast, good for structured output |
| CodeLlama 34B | 34B | 20GB (Q4) | Code-focused, good for agent proposals |
| Qwen 2.5 72B | 72B | 42GB (Q4) | Multilingual, strong reasoning |

**Recommended starting point:** Llama 3.1 8B for routing + Llama 3.1 70B for generation.

**Hardware requirement:** Apple Silicon Mac Pro with 32GB can run 8B models natively via Ollama. For 70B, need 64GB+ or offload to GPU server.

---

## Phase 3: Fine-Tuning (Q4 2026)

### Task 1: Router Model (8B)
- **Purpose:** Replace keyword routing with LLM classification
- **Training data:** task text → correct agent name (from tickets table)
- **Method:** LoRA fine-tune on Llama 3.1 8B
- **Expected:** 95%+ routing accuracy, <100ms latency

### Task 2: Proposal Generation (70B)
- **Purpose:** Generate code proposals for approved tasks
- **Training data:** task + project context → approved proposal
- **Method:** LoRA fine-tune on Llama 3.1 70B or CodeLlama 34B
- **Expected:** Comparable quality to Claude Sonnet for known patterns

### Task 3: Domain-Specific (OrthoFlow/HTC)
- **Purpose:** Invoice classification, medication parsing, benefits checking
- **Training data:** OrthoFlow classification results, HTC user interactions
- **Method:** LoRA fine-tune on Llama 3.1 8B (fast inference needed)
- **Expected:** 95%+ accuracy on domain tasks, replace Ollama orthoflow-classify model

### Tools
```bash
# Fine-tuning stack
pip install unsloth transformers trl datasets peft

# LoRA training (runs on Apple Silicon)
python train.py \
  --base_model "meta-llama/Meta-Llama-3.1-8B" \
  --data_path "./data/training/instruction_pairs.jsonl" \
  --output_dir "./models/darius-router-v1" \
  --lora_r 16 --lora_alpha 32 \
  --num_epochs 3 --batch_size 4 --lr 2e-4

# Convert to Ollama format
ollama create darius-router -f Modelfile
```

---

## Phase 4: Deployment (Q1 2027)

```
Ollama (local)
├── darius-router (8B) — agent routing, <100ms
├── darius-coder (34B) — proposal generation
├── darius-domain (8B) — ortho/caregiver classification
└── nomic-embed-text — embeddings (already running)

Fallback: Anthropic API
└── Claude Sonnet — complex tasks that local can't handle
```

### Hybrid Strategy
```python
# In base_agent.py / darius agent.py
def select_provider(task: str, complexity: float) -> str:
    if complexity < 0.3:  # simple routing/classification
        return "ollama/darius-router"
    elif complexity < 0.7:  # standard code generation
        return "ollama/darius-coder"
    else:  # complex multi-step reasoning
        return "anthropic/claude-sonnet"  # fallback
```

---

## Phase 5: Continuous Improvement (Ongoing)

- Every approved proposal → added to training set
- Every rejected proposal → negative example
- Monthly re-training with accumulated data
- A/B test local vs API responses (blind comparison via Odysseus Compare feature)
- Track metrics: accuracy, latency, cost savings

---

## Cost Savings Projection

| Current (API only) | After Local Model |
|--------------------|--------------------|
| ~$100-200/mo Anthropic | ~$20-50/mo (complex tasks only) |
| 100% external dependency | 70% local, 30% API fallback |
| Rate limited | Unlimited local inference |
| Zero control over model | Full control, fine-tunable |

---

## Hardware Roadmap

| Current | Needed for 70B | Ideal |
|---------|----------------|-------|
| Mac Pro 16-core, 32GB | 64GB+ unified memory | Mac Studio Ultra 192GB or dedicated GPU server |
| Runs 8B models | Runs 70B quantized | Runs multiple 70B concurrent |

**Budget estimate:** Mac Studio Ultra M4 (~$7,000) or cloud GPU instance (~$200/mo for A100).

---

*Created: June 18, 2026*
*Owner: Melanin Technologies Inc.*
*Status: Phase 1 (data collection) active*
