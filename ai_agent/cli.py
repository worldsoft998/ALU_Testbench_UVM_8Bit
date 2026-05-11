"""
AIa-VO Command-Line Interface.
Entry point for running AI-guided verification acceleration.
"""

import os
import sys
import argparse
import logging
from .core.config import AgentConfig
from .core.agent import AIVerificationAgent


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="AIa-VO: AI Agent Supported Verification Optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings
  python -m ai_agent.cli

  # Use specific LLM and ML algorithm
  python -m ai_agent.cli --llm-provider claude --ml-algorithm rl

  # Quick run with low iteration count
  python -m ai_agent.cli --max-iterations 10 --num-items 1000

  # Run with comparison mode disabled
  python -m ai_agent.cli --no-comparison

  # Use custom config file
  python -m ai_agent.cli --config config/advanced.yaml
        """,
    )

    parser.add_argument(
        "--config", "-c",
        default="config/default.yaml",
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current directory)",
    )

    # LLM options
    llm_group = parser.add_argument_group("LLM Configuration")
    llm_group.add_argument(
        "--llm-provider",
        choices=["openai", "gemini", "claude"],
        default=None,
        help="LLM provider (overrides config)",
    )
    llm_group.add_argument(
        "--llm-model",
        default=None,
        help="LLM model name (overrides config)",
    )
    llm_group.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM features",
    )

    # ML options
    ml_group = parser.add_argument_group("ML Configuration")
    ml_group.add_argument(
        "--ml-algorithm",
        choices=["bayesian", "rl", "random_forest", "ensemble"],
        default=None,
        help="ML algorithm for seed optimization (overrides config)",
    )
    ml_group.add_argument(
        "--no-ml",
        action="store_true",
        help="Disable ML features (pure random with coverage tracking)",
    )

    # Simulation options
    sim_group = parser.add_argument_group("Simulation Configuration")
    sim_group.add_argument(
        "--target-coverage",
        type=float,
        default=None,
        help="Target coverage percentage (default: 100.0)",
    )
    sim_group.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of iterations (default: 50)",
    )
    sim_group.add_argument(
        "--num-items",
        type=int,
        default=None,
        help="Transactions per simulation run (default: 5000)",
    )

    # Comparison options
    cmp_group = parser.add_argument_group("Comparison")
    cmp_group.add_argument(
        "--comparison",
        action="store_true",
        default=None,
        help="Enable comparison with baseline",
    )
    cmp_group.add_argument(
        "--no-comparison",
        action="store_true",
        help="Disable comparison with baseline",
    )

    # Misc
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Only generate reports from existing results",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger("aivo")

    # Load configuration
    config_path = args.config
    if os.path.exists(config_path):
        logger.info(f"Loading config from: {config_path}")
        config = AgentConfig.from_yaml(config_path)
    else:
        logger.info("Using default configuration")
        config = AgentConfig()

    # Apply CLI overrides
    config.project_root = os.path.abspath(args.project_root)

    if args.llm_provider:
        config.llm.provider = args.llm_provider
    if args.llm_model:
        config.llm.model = args.llm_model
    if args.no_llm:
        config.enable_llm = False

    if args.ml_algorithm:
        config.ml.algorithm = args.ml_algorithm
    if args.no_ml:
        config.enable_ml = False

    if args.target_coverage is not None:
        config.target_coverage = args.target_coverage
    if args.max_iterations is not None:
        config.max_iterations = args.max_iterations
    if args.num_items is not None:
        config.simulation.default_num_items = args.num_items

    if args.no_comparison:
        config.comparison_mode = False
    elif args.comparison:
        config.comparison_mode = True

    # Validate
    warnings = config.validate()
    for w in warnings:
        logger.warning(f"Config: {w}")

    # Report-only mode
    if args.report_only:
        logger.info("Report-only mode. Generating from existing results...")
        from .comparison.report_gen import ReportGenerator
        from .simulation.results_db import ResultsDB
        rdb = ResultsDB(config)
        sessions = rdb.list_sessions()
        if sessions:
            latest = sessions[-1]
            data = rdb.load_session(latest["session_id"])
            rgen = ReportGenerator(config)
            rgen.generate_final_report(data)
            logger.info("Report generated.")
        else:
            logger.error("No previous sessions found.")
        return

    # Print configuration summary
    logger.info("=" * 60)
    logger.info("AIa-VO Configuration Summary:")
    logger.info(f"  Project Root:    {config.project_root}")
    logger.info(f"  LLM Provider:    {config.llm.provider if config.enable_llm else 'disabled'}")
    logger.info(f"  ML Algorithm:    {config.ml.algorithm if config.enable_ml else 'disabled'}")
    logger.info(f"  Target Coverage: {config.target_coverage}%")
    logger.info(f"  Max Iterations:  {config.max_iterations}")
    logger.info(f"  Items/Run:       {config.simulation.default_num_items}")
    logger.info(f"  Comparison:      {config.comparison_mode}")
    logger.info("=" * 60)

    # Run the agent
    agent = AIVerificationAgent(config)
    summary = agent.run()

    # Print results
    logger.info("")
    logger.info("=" * 60)
    logger.info("FINAL RESULTS:")
    logger.info(f"  Status:          {summary.get('status')}")
    logger.info(f"  Final Coverage:  {summary.get('final_coverage', 0):.2f}%")
    logger.info(f"  Iterations:      {summary.get('iterations', 0)}")
    logger.info(f"  Elapsed:         {summary.get('elapsed_seconds', 0):.1f}s")
    logger.info("=" * 60)

    if summary.get("status") != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
