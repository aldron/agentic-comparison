# Agentic Flow Orchestration: Claude SDK vs Google ADK

A project that benchmarks and compares the orchestration capabilities of **Anthropic’s Claude SDK** and **Google’s Agent Development Kit (ADK)** for building agentic workflows.

## 📌 Goal

Run identical agentic tasks using both frameworks and compare them across key dimensions: performance, cost, complexity, and reliability.

## 🔬 Frameworks Compared

|            |Claude SDK       |Google ADK              |
|------------|-----------------|------------------------|
|**Provider**|Anthropic        |Google                  |
|**Model**   |Claude           |Gemini                  |
|**Package** |`anthropic`      |`google-adk`            |
|**Style**   |Flexible / manual|Opinionated / structured|

## 📐 Comparison Dimensions

- Tool / function calling
- Multi-agent orchestration
- Memory & state management
- Human-in-the-loop support
- Error handling & recovery
- Latency, token usage & cost

## 🗂️ Project Structure (Coming Soon)

```
agentic-comparison/
├── shared/          # Common tasks and tools
├── claude_sdk/      # Claude-based orchestrator
├── google_adk/      # Google ADK-based orchestrator
├── benchmarks/      # Benchmark runner & metrics
└── results/         # Output reports
```

## 🚀 Getting Started

```bash
pip install anthropic google-adk
```

Set your API keys:

```bash
export ANTHROPIC_API_KEY=your_key_here
export GOOGLE_API_KEY=your_key_here
```

## 📊 Benchmark Tasks

- Multi-step research
- Code generation + execution
- Sequential data pipeline
- Parallel data fetching
- Error recovery

## 🛠️ Built With

- Python 3.11+
- Anthropic Claude SDK
- Google Agent Development Kit (ADK)
- GitHub Codespaces
