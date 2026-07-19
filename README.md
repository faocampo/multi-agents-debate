# Multi-Agent Experts

A small Python framework for analyzing one decision through deliberately
conflicting expert viewpoints. It implements the framework described in
[h100envy's X article](https://x.com/h100envy/status/2077371640690672001):

1. An orchestrator dynamically chooses 3-5 roles whose interests conflict.
2. Experts analyze the same decision independently and in parallel.
3. An optional parallel debate round lets every expert answer the opposition.
4. A devil's advocate attacks apparent consensus and shared assumptions.
5. A low-temperature synthesizer preserves conflicts instead of averaging them
   into a vague answer.

The package has no runtime dependencies and supports both Ollama and
OpenAI-compatible chat endpoints.

## Quick start

Create an environment and install the package:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

With Ollama:

```bash
export MAE_MODEL=qwen2.5:32b
multi-agent-experts \
  "We want to remove the free tier and offer only a 14-day trial. Should we?"
```

With an OpenAI-compatible provider:

```bash
export MAE_ENDPOINT=https://provider.example/v1/chat/completions
export MAE_MODEL=your-model
export MAE_API_KEY=your-token
multi-agent-experts --json "Should we launch this product now?"
```

Use `--no-debate` for the shorter pipeline. Run `multi-agent-experts --help`
for role-count, worker-count, and output options.

## Python API

```python
from multi_agent_experts import HTTPChatClient, MultiAgentAnalyzer

client = HTTPChatClient(
    endpoint="http://localhost:11434/api/chat",
    model="qwen2.5:32b",
)
result = MultiAgentAnalyzer(client).analyze(
    "Should we replace the free tier with a 14-day trial?"
)

print(result.synthesis)
for opinion in result.opinions:
    print(opinion.role.name, opinion.current_analysis)
```

To use an SDK or another provider, supply any thread-safe object with this
method:

```python
def complete(self, system: str, user: str, temperature: float = 0.7) -> str:
    ...
```

## Design invariants

- The orchestrator plans roles but does not analyze the decision.
- First-round experts never receive other experts' output.
- Parallel execution preserves both independence and the planned role order.
- Debate happens only after all independent positions are complete.
- Consensus is attacked before it is synthesized.
- The merge is explicitly required to expose contradictions, costs, minority
  warnings, and conditions that would change the verdict.

## Tests

The test suite is offline and uses a deterministic fake model:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
