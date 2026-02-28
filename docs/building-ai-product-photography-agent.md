# Building an AI Product Photography Agent: From Claude Desktop to Production API

> What I learned about context engineering, multi-agent architecture, and the real bottleneck in AI image generation — it's not the model, it's the taste.

---

## Part I: Product Story

### 1. The Problem: Why AI Product Photography?

When selling handcrafted jewelry on Etsy, product photography is everything. A single listing needs 10 carefully composed images — hero shots, model wearing shots, macro details, lifestyle scenes, packaging. Professional photography costs $200–500 per product. For a small seller with 50+ SKUs, that's prohibitively expensive.

AI image generation seemed like the obvious solution. We tried feeding our best commercial advertising photos to Gemini, Claude, and ChatGPT, asking them to imitate the style. The results looked "AI-generated" — technically competent but creatively dead.

The models failed to understand **where the beauty lives**:

- **Light and shadow interaction** — how light wraps around a gemstone, the gradient of shadow on skin
- **Hand-to-light interplay** — how fingers catch and redirect light, creating organic highlights
- **Hand-to-hand composition** — the gesture language of jewelry modeling, where one hand presents while the other provides visual balance

If you simply ask an AI to "imitate this beautiful photo," it copies the surface elements — the pose, the angle, the color palette — but misses the underlying logic of *why* those elements work together. The output has no soul.

We discovered that the real bottleneck isn't the AI model's capability. It's **aesthetic tasting** — the human ability to articulate why a photo works, decompose it into reproducible techniques, and encode that knowledge into structured prompts. This is the work nobody wants to do, because it sits at the intersection of art education, commercial photography, and prompt engineering. But it's the work that matters most.

---

### 2. The Evolution: Desktop → Skills → Agent → API

This project didn't start as a product. It started as a personal workflow, and evolved through four distinct stages.

**Stage 1: Claude Desktop — Manual Prompting**

We began by chatting with Claude Desktop. A friend with formal training in Fashion Design (Parsons) and Marketing (SVA) worked with us to decompose commercial advertising photography techniques. Over 10–20 hours of deep conversation with Claude, we reverse-engineered what makes great jewelry photography work — breaking down lighting setups, composition rules, pose semantics, and mood construction into language that an AI image generator could understand.

The key insight from this stage: **you can't shortcut the aesthetic decomposition.** You need domain experts who can articulate why a photo is good, and you need extended dialogue with an AI to translate that understanding into structured, reproducible prompts.

**Stage 2: Claude Code Skills — Encoding Knowledge**

Writing the same instructions repeatedly was tedious. We started encoding our photographic knowledge into Claude Code skills — reusable instruction files that decomposed specific techniques into structured prompt templates.

The output of this encoding process had three layers:

1. **Encoded Prompt Structure** — Prompt templates optimized for Gemini's specific characteristics. We spent 10+ hours understanding how to write prompts that produce consistent, high-quality output.
2. **Technique Skills** — Skills covering specific capabilities: how to avoid the "AI look," how to render different artistic styles, how to handle macro photography without artifacts.
3. **Reference Files** — Deconstructed analyses of professional advertising photography, translated into referenceable standards for lighting, composition, and mood.

Efficiency jumped significantly over hand-written prompts. But a new problem emerged: how to systematically orchestrate the full image generation pipeline.

**Stage 3: Composite Skill → Agent — Hitting the Ceiling**

We tried wrapping multiple skills into a single composite skill — one skill calling sub-skills in sequence. This approach was **fundamentally unstable**:

- **Step skipping** — When processing multiple products, the system would skip steps or omit entire phases.
- **Quality degradation** — Generated images had strong "AI feel" with confused aesthetics.
- **Call blindness** — The wrapper skill couldn't reliably sense that it needed to invoke a sub-skill. Claude Code's nested skill architecture wasn't designed for complex multi-step orchestration.

We addressed this with two simultaneous moves:
1. **Agent decomposition** — Split the monolithic skill into a proper agent with discrete nodes.
2. **Python validation** — Introduced verifiable JSON schemas at every stage boundary, ensuring deterministic quality gates that didn't rely on the model's judgment.

**Stage 4: API Service — Productizing the Knowledge**

The agent works well inside Claude Code, but it can't scale, can't be shared, and can't be monetized. More critically, sharing the Claude Code agent would expose our core IP — the skills and prompts that encode 20+ hours of aesthetic decomposition.

Our goal isn't a consumer app. It's an **API / MCP server / Skill-as-a-Service**:

- Users call our API with product photos
- We host the backend and handle generation
- The generation process is paid per use
- A landing page collects interest; demos show capability

This is primarily a side project for deepening my understanding of agent architecture and context engineering. But the core IP — the skills and prompts — has real commercial value, and an API is the natural way to share that value without exposing the underlying prompt engineering.

---

### 3. The Core IP: Why This Is Hard to Replicate

The moat around this project isn't the code — it's the encoded knowledge. Several compounding factors make it defensible:

**Domain expertise is rare.** Few people combine formal fashion/art education + AI prompting skill + jewelry e-commerce experience. Finding someone who can articulate why a particular hand pose makes a ring photo sell better, and translate that into a Gemini-compatible prompt, is genuinely difficult.

**The iteration cost is high.** Others would need to invest similar time (10–20 hours of expert dialogue) and API costs to discover what works. There's no shortcut — you can't read a blog post about prompt engineering and achieve this quality.

**Tacit knowledge is hard to transfer.** Even with our prompts visible, others wouldn't know how to adapt them to new product categories. The aesthetic principles are encoded in the *structure* of the skills, not just their content.

**Without skills, knowledge doesn't scale.** This is the critical insight: even if you have the aesthetic understanding, doing it manually for each product is prohibitively slow. You can't just "figure out the prompt" for every new product listing. The skill is what turns one-time human insight into repeatable, scalable capability. Without encoding knowledge into skills, every product requires re-deriving the prompts from scratch — defeating the entire purpose of using AI.

Encoding that knowledge into reusable skills is itself a hard problem. And without it, you can't guarantee consistency across products — manual execution produces variable quality every time.

---

### 4. Why Productize: Three Concrete Motivations

**Scalability.** Claude Code skills work well but can't scale. You have to manually trigger each run, you can't batch-process 50 products, and you can't schedule overnight generation. An API changes this — one HTTP call per product, parallel execution, queue management.

**Shareability without IP exposure.** The Claude Code agent can't be shared directly. We want others to experience the image generation capability, but we don't want to publish our core skill code. An API provides the capability boundary — users get results, not implementation.

**Cost reduction.** Claude Code with the Max Plan gives access to Opus-level models at a flat monthly rate. But API pricing changes the math dramatically. We needed to use cheaper models (Kimi, MiniMax) that match Claude's quality at 1/10th the price, making the unit economics work for a paid service.

---

## Part II: Technical Decisions

### Decision 1: Why LangGraph, Not Claude Code or Agent SDK Alone

**Context:** We had a working system inside Claude Code — skills calling sub-skills in sequence. Why not just keep it there?

**The problem with nested skills:** Claude Code's skill system is designed for human-triggered, single-task workflows. When we tried to compose skills into a pipeline (analyze → strategize → generate prompts → review → generate images → write listing), the system broke in ways that were hard to debug:

- The wrapping skill would skip steps, especially when processing multiple products
- Sub-skill invocations were unreliable — the model couldn't always recognize when to call another skill
- Quality degraded as the context window filled with instructions from multiple skill layers

**Why LangGraph:** We needed **deterministic orchestration** — a state machine where each step is guaranteed to execute, transitions are explicit, and failures are retryable with structured feedback. LangGraph gave us:

1. **Explicit state machine** — Every node, every transition, every retry is visible and testable
2. **Fan-out parallelism** — 10 prompt agents running simultaneously, something Claude Code can't do
3. **Review gates** — Validation checkpoints between every stage
4. **Model flexibility** — Different nodes can use different LLM providers

**Agentic behavior inside nodes:** Inside individual nodes (especially the prompt generation sub-agents), we built a custom multi-turn tool-use loop on the Anthropic Messages API. Each sub-agent reads its configuration instructions, generates a draft, calls validation tools to self-check, and iterates until the output passes — all within a single node's execution. MiniMax exposes an Anthropic-compatible API endpoint, so the same agentic loop code works across both Claude and MiniMax without provider-specific adapters.

**The final architecture:** LangGraph for orchestration (the "pipeline bones"), custom agentic loops on the Anthropic Messages API for individual node intelligence (the "agent brains"), LangSmith for observability (the "monitoring eyes").

---

### Decision 2: Model Selection — Why Kimi + MiniMax, Not Claude API

**Context:** When you use Claude Code with a Max Plan ($100/month), you get Opus-level models at effectively unlimited usage. But the moment you switch to API calls, pricing changes everything.

**The cost reality:** In agentic mode — where the model makes multiple tool calls, reads lengthy skill files and reference documents, and self-validates across several turns — costs add up quickly. In our early multi-turn agent setup with extensive reference loading, a single Sonnet conversation could reach ~$1. Multiply that by 10 parallel prompt agents, plus preprocessing, strategy, and listing generation, and the per-product cost becomes unsustainable for a paid service.

**Our model selection after benchmarking on OpenRouter:**

| Task | Model | Why This Model | Cost vs Claude |
|------|-------|---------------|---------------|
| Preprocessing | Claude Sonnet (vision) | Only model in our stack that can see product photos. Extracts structured product data + writes the reference anchor. | Baseline |
| Strategy Analysis | Kimi (K2.5), Claude fallback | Strong reasoning for marketing analysis. Text-only — reads the structured `product_data.json` from preprocessing, not raw photos. | ~1/10th Opus |
| Prompt Generation (×10) | MiniMax | Exposes an Anthropic-compatible API, so our agentic loop works without code changes. Strong at structured text generation following skill instructions. | ~1/10th Sonnet |
| Image Generation | Gemini 3.1 Flash (`gemini-3.1-flash-image-preview`) | Pro-level quality at Flash speed, ~50% cheaper than Pro. Supports reference images and up to 4K resolution. | N/A (different capability) |
| Reviews (L3 semantic) | Claude | When semantic quality judgment is needed, Claude's reasoning is still the best. Used sparingly. | Full price, but rare |

**Why this works:** Our skills do the heavy lifting. When the prompt template is well-structured and the reference files are detailed, the model's job is execution, not reasoning. A cheaper model following excellent instructions produces results comparable to an expensive model with mediocre instructions.

**Technical constraint driving the split:** MiniMax is a text-only model — it can't read images. Only Claude has the vision capabilities we need for preprocessing. This forces a natural pipeline split: Claude Vision handles image-dependent stages (preprocessing, reference anchor writing), Kimi handles text-based reasoning (strategy analysis), and MiniMax handles text-only generation (prompts, listing). The model limitations actually reinforced good architecture — they forced us to decouple image understanding from text generation, which is the correct separation of concerns anyway.

---

### Decision 3: Workflow Mode + Agentic Nodes

**Context:** The AI agent landscape presents a spectrum from "fully autonomous agent" to "fully deterministic pipeline." Where should we sit?

**Our position: Workflow orchestration with agentic nodes.**

The overall pipeline is a fixed, deterministic workflow:

```
preprocess → review → strategy → review
    → fan-out: [10× prompt agents + listing agent in parallel]
    → aggregate → image_gen (optional) → listing_review → done
```

This sequence never changes. There's no "agent deciding what to do next." The state machine guarantees every step executes, every review gate fires, every failure triggers a retry with structured feedback. An important optimization: the listing agent runs **in parallel** with the 10 prompt agents during fan-out, since it only needs `product_data.json` (available after preprocessing) — it doesn't wait for prompts or images.

But *inside* each node, the behavior is agentic. The prompt generation sub-agents use a custom multi-turn tool-use loop to:
1. Read their assigned skill instructions
2. Generate a prompt draft
3. Call a validation tool to check their own output
4. Self-correct if validation fails
5. Return the final result

**Why not fully agentic?** One critical question drove this decision: **Can an agent autonomously spawn parallel sub-agents?** The answer, practically, is no. If we had a single agent responsible for generating 10 prompts, it would process them sequentially. Worse, the context from Prompt 1 would bleed into Prompt 2's generation — there's no context isolation within a single agent's conversation.

This is fundamentally a **context engineering problem**: Prompt 1 and Prompt 2 have no meaningful relationship. Including Prompt 1's context in Prompt 2's generation environment creates interference and pollution. A workflow's fan-out pattern solves this by design — each sub-agent gets its own fresh, isolated context.

**Evolution of the review system:** We started with fully deterministic reviews (Python-only L1/L2 validation). Later, we gave the L1 validation functions to the sub-agents as tools, letting them self-validate during generation. The results were better — the agent would generate a prompt, validate it, notice an issue, and fix it before returning. This is agentic behavior within a workflow-controlled boundary.

---

### Decision 4: When to Use Multi-Agent

We developed four criteria for deciding whether a task should be its own agent:

**1. Context Isolation.**
If an agent doesn't need another agent's context, separate them. This saves tokens, prevents pollution, and ensures information appears at the *right position* in the context window. In agent design, putting the right information in the right place is critical.

**2. Parallelism.**
If tasks are independent, they can run as parallel agents. We don't need a single massive agent doing everything sequentially. Our 10 prompt agents run simultaneously, cutting generation time from ~10 minutes to ~1 minute.

**3. Trackability.**
Separate agents produce separate traces in LangSmith. When something goes wrong with Prompt 7, you can inspect that specific agent's execution without wading through the full pipeline's logs.

**4. Model Flexibility.**
Different tasks may require different models. Vision tasks need Claude; text generation works best with MiniMax; semantic review needs Claude. A modular architecture lets you assign the right model to each task.

The mental model: **if a human team would assign this to different people, it should be different agents.** A marketing strategist doesn't generate photography prompts; a photographer doesn't write SEO copy. Different expertise, different context, different outputs.

---

### Decision 5: Context Engineering — Imitating Human Organizations

**The core insight:** Our context engineering strategy is borrowed from how human organizations already work.

When a company creates product photography:
1. **Marketing** analyzes the brand, defines the strategy, specifies what kinds of images are needed
2. **Marketing hands a brief to the photographer** — not the full brand strategy, just the distilled requirements
3. **The photographer executes** — they don't need to know *why* marketing chose this strategy, just *what* to shoot

This handoff is natural context isolation. The photographer receives a **compact brief**, not the full marketing analysis. This is exactly what our pipeline does:

- The **Strategy Agent** (marketing) analyzes the product and creates a 10-slot image plan
- Each **Prompt Agent** (photographer) receives only its assigned slot — the description, rationale, and creative direction — not the full strategy analysis or other slots' information
- The **Skill** serves as the **SOP** — defining *how* to execute the task and *where* to find reference materials

Skills accomplish two things:
1. **Define the process** — step-by-step instructions for how to approach the task
2. **Provide reference pointers** — where to look if the agent needs additional information (reference files, style guides, examples)

This is **context as organizational design** — each agent knows exactly what it needs, nothing more. The skill defines the boundary of each agent's knowledge.

---

### Decision 6: Why Observability Matters — LangSmith

**Cost comparison across model changes.** When we switched from Claude Sonnet to Kimi for strategy analysis, we needed to verify the cost actually dropped. LangSmith tracks token usage and cost per trace, making model migration decisions data-driven rather than guesswork.

**Execution transparency.** When you define your pipeline well, LangSmith shows you exactly how many tool calls each agent made, which tools it called, and which references it read. Without this visibility, you have no idea whether your agents are following instructions or going off-script. This is especially important during development — you need to verify that new skill instructions actually change agent behavior.

**Structured dashboard vs reading logs.** Raw logs are not human-friendly. LangSmith provides structured, visual representations of agent execution traces. When an image prompt is bad, you can click into the specific sub-agent's trace and see exactly what context it received, what tools it called, and where the reasoning went wrong.

**What we haven't done yet (but want to):** Systematic evaluation. We want to build golden-label datasets — recording which tool calls are correct, which outputs are high quality — and use them for automated regression testing. Time constraints have prevented this, but I believe rigorous evaluation is what separates toy agent demos from production-quality systems.

---

### Decision 7: AI Reasoning vs Human-Defined Rules

**The core principle: speed and cost determine the approach.**

We decompose validation into three tiers:

| Tier | Method | Cost | Speed | When to Use |
|------|--------|------|-------|-------------|
| **L1: Schema** | Python code | $0.000 | <1ms | Always — catches structural errors |
| **L2: Rules** | Python code | $0.000 | <1ms | Always — catches business logic violations |
| **L3: Semantic** | Claude API | ~$0.01/call (~$0.04–0.08/product) | ~2s | Only after L1+L2 pass — catches quality/reasoning issues |

If a problem is verifiable by deterministic rules, don't waste an API call on it. L1 and L2 catch 90%+ of issues for free. L3 is reserved for the questions that require judgment — tone, factual accuracy, creative quality.

**Why review must be context-isolated from generation:** This is a subtle but important architectural decision. The L3 reviewer is a separate LLM call with its own REVIEW.md instructions. It does *not* see the generation skill's instructions — only the output and its review criteria.

This matters because a reviewer who has seen the generation instructions might be biased — "the generator was told to create X, so the output must be X." An isolated reviewer evaluates the output on its own merits, just like a QA engineer who tests functionality without reading the developer's code comments.

If generation and review happened within a single agent's conversation, the review skill and generation skill would mix in the context window. The reviewer would effectively be grading its own work — which defeats the purpose of review.

---

## Conclusion: What I Learned

Building this system taught me that the "agentic" in "agentic AI" is less about autonomy and more about **architecture** — how you decompose problems, route information, and verify outputs.

The most impactful lessons:

1. **The bottleneck is human knowledge encoding, not AI capability.** The 10–20 hours of aesthetic decomposition with domain experts created more value than any model upgrade. Skills are the product; the agent is just the delivery mechanism.

2. **Context engineering IS the architecture.** Deciding what each agent sees — and crucially, what it *doesn't* see — determines the quality of the entire pipeline. Imitate how human organizations naturally isolate and distribute information.

3. **Workflow for orchestration, agentic for execution.** Don't choose between workflow and agentic — use workflow to guarantee the pipeline runs correctly, and agentic behavior within nodes for intelligent execution.

4. **Match models to tasks, not tasks to models.** Use the most expensive model only where its unique capabilities are needed. For structured tasks with good instructions, cheaper models perform equally well.

5. **Deterministic validation before semantic review.** Python code at $0.00 catches 90% of issues. Reserve AI-powered review for the remaining 10% that requires judgment.

6. **Build for observability from day one.** If you can't see what your agents are doing, you can't improve them. Structured tracing (LangSmith) is not optional — it's how you turn a prototype into a product.

### What's Next

If I were starting over, I'd invest in **systematic evaluation** earlier. We have the tracing infrastructure (LangSmith) but haven't built golden-label datasets for automated regression testing — which means quality assessment is still manual. The next evolution is closing that loop: use traces to build evaluation sets, use evaluation sets to catch regressions automatically, and use regression data to improve skills.

The other open question: **can the aesthetic knowledge transfer to other product categories?** Our skills are optimized for jewelry. Whether the same decomposition framework works for clothing, ceramics, or electronics is an experiment we haven't run yet — but the architecture is designed to support it. Each product category would get its own skill library while sharing the same pipeline infrastructure.

---

*This project is a side project built to deepen my understanding of agent architecture and context engineering. The core value isn't the code — it's the aesthetic knowledge encoded in the skills, and the architectural decisions that make it work at scale.*

*Built with LangGraph, LangSmith, and custom agentic loops on the Anthropic Messages API. Preprocessing by Claude Vision, strategy by Kimi, prompts by MiniMax, images by Gemini, reviews by Claude.*
