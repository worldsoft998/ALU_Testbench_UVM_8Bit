# AIa-VO API Reference

## Core Module (`ai_agent.core`)

### `AgentConfig`
Top-level configuration dataclass.

```python
from ai_agent.core.config import AgentConfig

config = AgentConfig()
config.target_coverage = 95.0
config.max_iterations = 30
config.enable_llm = True
config.enable_ml = True

# Load from YAML
config = AgentConfig.from_yaml("config/default.yaml")

# Validate
warnings = config.validate()
```

**Fields:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `project_root` | str | "." | Project root directory |
| `target_coverage` | float | 100.0 | Target coverage % |
| `max_iterations` | int | 50 | Max optimization iterations |
| `convergence_threshold` | float | 0.1 | Min coverage delta for progress |
| `convergence_patience` | int | 5 | Iterations without progress before stopping |
| `enable_llm` | bool | True | Enable LLM features |
| `enable_ml` | bool | True | Enable ML optimization |
| `comparison_mode` | bool | True | Enable baseline comparison |

### `AIVerificationAgent`
Main orchestrator. Coordinates simulation, coverage parsing, and AI optimization.

```python
from ai_agent.core.agent import AIVerificationAgent

agent = AIVerificationAgent(config)
summary = agent.run()
```

**Methods:**
| Method | Returns | Description |
|--------|---------|-------------|
| `run()` | dict | Execute the full AI-guided verification loop |

**Return dict keys:**
- `status`: "success" or "error"
- `iterations`: Total iterations executed
- `final_coverage`: Final cumulative coverage %
- `elapsed_seconds`: Wall clock time
- `coverage_trend`: List of coverage % at each iteration
- `seeds_used`: List of seeds used

### `CoverageParser`
Parse VCS/URG coverage reports.

```python
from ai_agent.core.coverage_parser import CoverageParser

parser = CoverageParser(project_root=".")
report = parser.parse_vcs_log("sim.log")
report = parser.parse_urg_report("coverage_report.txt")
merged = parser.merge_reports([report1, report2])
empty = parser.create_empty_alu_report()
```

### `GapAnalyzer`
Analyze coverage gaps and suggest strategies.

```python
from ai_agent.core.gap_analyzer import GapAnalyzer

analyzer = GapAnalyzer()
analysis = analyzer.analyze(coverage_report)

# Access results
print(analysis.total_uncovered)
print(analysis.suggested_strategy)
print(analysis.stimulus_hints)

# Check trends
trend = analyzer.get_coverage_trend()
```

---

## LLM Module (`ai_agent.llm`)

### `BaseLLMClient`
Abstract base class for LLM providers.

**Methods:**
| Method | Returns | Description |
|--------|---------|-------------|
| `get_seed_strategy(data)` | dict | Get seed/strategy suggestion |
| `analyze_coverage_gaps(gaps)` | str | Analyze coverage gaps |
| `suggest_constraint_adjustment(state)` | dict | Suggest constraint changes |
| `get_stats()` | dict | Get usage statistics |

### `OpenAIClient` / `GeminiClient` / `ClaudeClient`
Concrete LLM implementations.

```python
from ai_agent.llm.openai_client import OpenAIClient
from ai_agent.core.config import LLMConfig

config = LLMConfig(provider="openai", model="gpt-4o-mini")
client = OpenAIClient(config)
result = client.get_seed_strategy({"coverage": 75.0, "uncovered_bins": [...]})
```

---

## ML Module (`ai_agent.ml`)

### `BayesianSeedOptimizer`
Bayesian optimization with Gaussian Process.

```python
from ai_agent.ml.bayesian_opt import BayesianSeedOptimizer
optimizer = BayesianSeedOptimizer(ml_config)
seed = optimizer.suggest_seed()
optimizer.update(seed, coverage_delta)
optimizer.incorporate_llm_hint({"seeds": [42, 1000]})
```

### `RLSeedAgent`
Reinforcement learning (Q-learning) agent.

```python
from ai_agent.ml.rl_agent import RLSeedAgent
agent = RLSeedAgent(ml_config)
seed = agent.suggest_seed()
agent.update(seed, coverage_delta, analysis)
```

### `SeedPredictor`
Random Forest-based seed predictor.

### `EnsembleOptimizer`
Combines RL, Bayesian, and RF with weighted voting.

### `CoveragePredictor`
Neural network for coverage prediction.

```python
from ai_agent.ml.coverage_model import CoveragePredictor
predictor = CoveragePredictor(ml_config)
pred = predictor.predict(seed=42, current_coverage=50.0, num_items=5000)
predictor.train_step(42, 50.0, 5000, actual_delta=2.5)
```

---

## Simulation Module (`ai_agent.simulation`)

### `VCSRunner`
Interface to Synopsys VCS.

```python
from ai_agent.simulation.vcs_runner import VCSRunner
runner = VCSRunner(agent_config)
ok = runner.compile()
result = runner.run_simulation(seed=42, num_items=5000)
runner.merge_coverage(coverage_dirs, output_dir)
```

### `SeedManager`
Intelligent seed generation.

```python
from ai_agent.simulation.seed_manager import SeedManager
mgr = SeedManager(agent_config)
seed = mgr.generate_smart_seed(used_seeds=[1, 2, 3])
seeds = mgr.generate_sequential_seeds(n=10)
```

### `LogMonitor`
Real-time simulation log monitoring.

```python
from ai_agent.simulation.log_monitor import LogMonitor
monitor = LogMonitor(agent_config)
events = monitor.parse_log_file("simulation.log")
summary = monitor.get_summary()
```

### `ResultsDB`
Results storage and retrieval.

```python
from ai_agent.simulation.results_db import ResultsDB
db = ResultsDB(agent_config)
db.save_iteration(iteration, seed, report, analysis)
db.save_summary(summary_dict)
sessions = db.list_sessions()
```

---

## Comparison Module (`ai_agent.comparison`)

### `MetricsCollector`
Collect and compare verification metrics.

```python
from ai_agent.comparison.metrics import MetricsCollector
metrics = MetricsCollector()
metrics.record_iteration(1, seed=42, phase="ai", coverage=50.0, gap_count=10, wall_time=1.0)
trend = metrics.get_coverage_trend()
comparison = metrics.compute_comparison(baseline_metrics)
```

### `ReportGenerator`
Generate markdown, text, and JSON reports.

```python
from ai_agent.comparison.report_gen import ReportGenerator
gen = ReportGenerator(agent_config)
gen.generate_final_report(summary)
gen.generate_comparison_report(ai_summary, baseline_summary)
```

---

## CLI Usage

```bash
python -m ai_agent.cli [options]

Options:
  --config PATH           YAML config file (default: config/default.yaml)
  --llm-provider NAME     openai, gemini, claude
  --ml-algorithm NAME     bayesian, rl, random_forest, ensemble
  --target-coverage PCT   Target coverage % (default: 100.0)
  --max-iterations N      Max iterations (default: 50)
  --num-items N           Transactions per run (default: 5000)
  --no-llm                Disable LLM
  --no-ml                 Disable ML
  --comparison            Enable comparison
  --no-comparison         Disable comparison
  --report-only           Generate reports from existing results
  --log-level LEVEL       DEBUG, INFO, WARNING, ERROR
```
