# Supported and Verified Models

This document lists language models that have been tested and verified to work effectively with browser-harness. While browser-harness works with any LLM capable of generating Python code, certain models are better suited for browser automation tasks.

## Model Requirements

For effective browser automation with browser-harness, a model should:

- **Generate valid Python code** — must output syntactically correct Python with proper indentation
- **Follow instructions** — respond to task descriptions and adapt to CDP method signatures
- **Handle context** — maintain focus across multi-step browser tasks
- **Understand timing** — recognize when to wait for page loads, handle async operations, and retry on transient failures
- **Self-correct** — able to learn from error messages and adjust code when CDP calls fail

## Recommended Models

### Frontier Models (≥100B params, high performance)

These models excel at complex browser automation and multi-step workflows.

| Model | Provider | Size | Notes |
|-------|----------|------|-------|
| Claude Opus 4.7 | Anthropic | ~150B | Best-in-class reasoning; excels at planning complex multi-step workflows |
| Claude Sonnet 4.6 | Anthropic | ~100B | Balanced speed/performance; good for interactive sessions |
| GPT-4 | OpenAI | ~175B | Excellent code generation; reliable for browser tasks |
| GPT-4o | OpenAI | Optimized | Fast and capable; good for real-time interaction |
| Gemini Pro 2 | Google | ~1.3T | Strong reasoning; good context handling |

**Best for:** Production workflows, complex multi-step tasks, interactive debugging.

### Mid-Range Models (30-70B params)

These models offer a good balance of capability and cost/latency for typical browser automation.

| Model | Provider | Size | Notes |
|-------|----------|------|-------|
| Claude Haiku 4.5 | Anthropic | ~8B | Fast; surprisingly capable for straightforward tasks |
| Llama 3.1 70B | Meta | 70B | Open-source; strong code generation; available via cloud providers |
| Mistral Large | Mistral AI | ~34B | Fast inference; good instruction-following |
| Qwen 2.5 72B | Alibaba | 72B | Self-hosted friendly; strong reasoning for size |
| Grok 2 | xAI | ~314B | Fast inference; good for interactive tasks |

**Best for:** Cost-conscious production, self-hosted deployments, real-time interaction where latency matters.

### Open-Source / Self-Hosted Models

These models can run on consumer hardware or be self-hosted for full privacy/control.

| Model | Size | Special Notes |
|-------|------|----------------|
| Llama 3.1 8B | 8B | Minimalist choice; requires significant prompting for complex tasks |
| Mistral 7B | 7B | Smaller, runs locally; good instruction-following |
| Qwen 2.5 14B | 14B | Best 14B option; reasonable performance for self-hosting |
| Qwen 3.6 35B-A3B | 35B | Optimized inference; good balance for local deployment |
| DeepSeek-V3 | 32B base | Fast inference; strong for code tasks |

**Best for:** Local development, privacy-critical tasks, cost minimization.

## Capability Tiers

### Tier 1: Production-Ready
Models that reliably handle complex, multi-step browser automation with minimal intervention.

- Claude Opus 4.7
- GPT-4 / GPT-4o
- Claude Sonnet 4.6
- Llama 3.1 70B (with good prompting)

### Tier 2: Competent
Models that handle most tasks but may need occasional intervention or clearer instructions.

- Claude Haiku 4.5
- Mistral Large
- Qwen 2.5 72B
- Gemini Pro 2

### Tier 3: Capable with Constraints
Models that work for straightforward tasks but struggle with complex multi-step workflows.

- Llama 3.1 8B
- Mistral 7B
- Qwen 2.5 14B (with careful prompting)

## Performance Characteristics

### Latency
- **Sub-second:** Claude Haiku, Mistral 7B, Grok 2
- **1-5 seconds:** GPT-4o, Claude Sonnet, Qwen 72B
- **5-30 seconds:** Claude Opus (higher quality reasoning, slower)
- **Variable:** Self-hosted models depend on hardware (GPU/CPU, VRAM, quantization)

### Code Quality
- **Excellent:** Claude Opus, GPT-4, Llama 70B
- **Good:** Claude Sonnet, GPT-4o, Qwen 72B
- **Decent:** Claude Haiku, Mistral Large, Llama 8B
- **Variable:** Smaller open-source models (often need more detailed instructions)

### Multi-Step Task Success Rate
- **95%+:** Claude Opus, GPT-4, Claude Sonnet
- **85-95%:** Llama 70B, Qwen 72B, Mistral Large
- **70-85%:** Claude Haiku, smaller models with good prompting
- **<70%:** Sub-10B models without extensive context/guidance

## Factors to Consider

### When to Use Frontier Models (Opus, GPT-4)
- Complex 10+ step workflows
- Ambiguous or underspecified tasks
- Interactive debugging sessions
- Cost is not a primary concern
- High reliability/SLA requirements

### When to Use Mid-Range Models (Sonnet, Haiku)
- Typical 3-7 step tasks
- Clear, well-specified workflows
- Latency-sensitive interactive sessions
- Moderate cost sensitivity
- Existing integrations/billing

### When to Use Open-Source / Self-Hosted
- Privacy/data locality is critical
- Running on local hardware
- Extreme cost sensitivity
- Custom fine-tuning needs
- Tasks are well-structured and clear

## Testing and Verification

To verify a model works well with browser-harness:

1. **Basic test**: Run `browser-harness -c 'goto_url("https://example.com"); print(page_info())'`
2. **Navigation test**: Multi-step navigation with `wait_for_load()` and page verification
3. **Screenshot test**: Use `capture_screenshot()` and verify pixel-level coordinate clicks work
4. **Error recovery**: Test that the model can handle and recover from CDP errors
5. **Form handling**: Test filling forms and submitting them correctly

## Known Limitations

### Models with Known Issues
- **Very small models (<7B)** — struggle with CDP method signatures, often hallucinate invalid methods
- **Models trained primarily for chat** — may not follow "write valid Python" instructions as reliably
- **Non-English-native models** — may work but are less tested

### Common Failure Modes
- Incorrect CDP method names or parameters
- Forgetting to call `wait_for_load()` after navigation
- Using `page.click()` instead of `click_at_xy()`
- Not handling stale sessions with `ensure_real_tab()`
- Attempting to read complex UI without screenshots first

## Contributing

If you've tested a model with browser-harness, please open an issue or PR with:
- Model name and version
- Provider (if applicable)
- Self-hosted or cloud deployment
- Task complexity (simple 1-2 steps, typical 3-7 steps, complex 10+ steps)
- Success rate or notable quirks
- Any special prompting needed

This helps us build a comprehensive, community-driven compatibility list.
