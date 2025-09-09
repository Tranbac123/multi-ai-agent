"""Run comprehensive evaluation of the AIaaS platform."""

import asyncio
import argparse
import json
from datetime import datetime
from pathlib import Path
import structlog

from eval.evaluator import Evaluator
from eval.judges.llm_judge import LLMJudgeConfig
from apps.orchestrator.core.orchestrator import OrchestratorEngine
from apps.router-service.core.router import RouterEngine
from libs.clients.event_bus import EventBus, EventProducer

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def run_router_evaluation(evaluator: Evaluator, output_dir: Path):
    """Run router evaluation."""
    logger.info("Starting router evaluation")
    
    # Create router engine
    from apps.router-service.core.features import FeatureExtractor
    from apps.router-service.core.classifier import MLClassifier
    from apps.router-service.core.cost import CostCalculator
    from apps.router-service.core.judge import LLMJudge
    
    feature_extractor = FeatureExtractor()
    classifier = MLClassifier()
    cost_calculator = CostCalculator()
    llm_judge = LLMJudge()
    
    router_engine = RouterEngine(
        feature_extractor=feature_extractor,
        classifier=classifier,
        cost_calculator=cost_calculator,
        llm_judge=llm_judge
    )
    
    # Run evaluation
    report = await evaluator.evaluate_router(router_engine)
    
    # Save report
    report_path = output_dir / "router_evaluation.json"
    report.save_to_file(str(report_path))
    
    # Print summary
    print(report.get_summary())
    
    logger.info("Router evaluation completed", report_path=str(report_path))
    return report


async def run_agent_evaluation(evaluator: Evaluator, output_dir: Path):
    """Run agent evaluation."""
    logger.info("Starting agent evaluation")
    
    # Create orchestrator engine
    event_bus = EventBus()
    event_producer = EventProducer(event_bus)
    
    from apps.orchestrator.core.workflow import WorkflowEngine
    from apps.orchestrator.core.saga import SagaManager
    
    workflow_engine = WorkflowEngine()
    saga_manager = SagaManager()
    
    orchestrator_engine = OrchestratorEngine(
        event_producer=event_producer,
        workflow_engine=workflow_engine,
        saga_manager=saga_manager
    )
    
    # Run evaluation
    report = await evaluator.evaluate_agent(orchestrator_engine)
    
    # Save report
    report_path = output_dir / "agent_evaluation.json"
    report.save_to_file(str(report_path))
    
    # Print summary
    print(report.get_summary())
    
    logger.info("Agent evaluation completed", report_path=str(report_path))
    return report


async def run_e2e_evaluation(evaluator: Evaluator, output_dir: Path):
    """Run end-to-end evaluation."""
    logger.info("Starting end-to-end evaluation")
    
    # Create router engine
    from apps.router-service.core.features import FeatureExtractor
    from apps.router-service.core.classifier import MLClassifier
    from apps.router-service.core.cost import CostCalculator
    from apps.router-service.core.judge import LLMJudge
    
    feature_extractor = FeatureExtractor()
    classifier = MLClassifier()
    cost_calculator = CostCalculator()
    llm_judge = LLMJudge()
    
    router_engine = RouterEngine(
        feature_extractor=feature_extractor,
        classifier=classifier,
        cost_calculator=cost_calculator,
        llm_judge=llm_judge
    )
    
    # Create orchestrator engine
    event_bus = EventBus()
    event_producer = EventProducer(event_bus)
    
    from apps.orchestrator.core.workflow import WorkflowEngine
    from apps.orchestrator.core.saga import SagaManager
    
    workflow_engine = WorkflowEngine()
    saga_manager = SagaManager()
    
    orchestrator_engine = OrchestratorEngine(
        event_producer=event_producer,
        workflow_engine=workflow_engine,
        saga_manager=saga_manager
    )
    
    # Run evaluation
    report = await evaluator.evaluate_end_to_end(router_engine, orchestrator_engine)
    
    # Save report
    report_path = output_dir / "e2e_evaluation.json"
    report.save_to_file(str(report_path))
    
    # Print summary
    print(report.get_summary())
    
    logger.info("End-to-end evaluation completed", report_path=str(report_path))
    return report


async def run_filtered_evaluation(evaluator: Evaluator, output_dir: Path, filter_criteria: dict):
    """Run evaluation with specific filter criteria."""
    logger.info("Starting filtered evaluation", filter_criteria=filter_criteria)
    
    # Create engines
    from apps.router-service.core.features import FeatureExtractor
    from apps.router-service.core.classifier import MLClassifier
    from apps.router-service.core.cost import CostCalculator
    from apps.router-service.core.judge import LLMJudge
    
    feature_extractor = FeatureExtractor()
    classifier = MLClassifier()
    cost_calculator = CostCalculator()
    llm_judge = LLMJudge()
    
    router_engine = RouterEngine(
        feature_extractor=feature_extractor,
        classifier=classifier,
        cost_calculator=cost_calculator,
        llm_judge=llm_judge
    )
    
    event_bus = EventBus()
    event_producer = EventProducer(event_bus)
    
    from apps.orchestrator.core.workflow import WorkflowEngine
    from apps.orchestrator.core.saga import SagaManager
    
    workflow_engine = WorkflowEngine()
    saga_manager = SagaManager()
    
    orchestrator_engine = OrchestratorEngine(
        event_producer=event_producer,
        workflow_engine=workflow_engine,
        saga_manager=saga_manager
    )
    
    # Run evaluations with filter
    router_report = await evaluator.evaluate_router(router_engine, filter_criteria)
    agent_report = await evaluator.evaluate_agent(orchestrator_engine, filter_criteria)
    e2e_report = await evaluator.evaluate_end_to_end(router_engine, orchestrator_engine, filter_criteria)
    
    # Save reports
    filter_suffix = "_".join([f"{k}_{v}" for k, v in filter_criteria.items()])
    
    router_path = output_dir / f"router_evaluation_{filter_suffix}.json"
    agent_path = output_dir / f"agent_evaluation_{filter_suffix}.json"
    e2e_path = output_dir / f"e2e_evaluation_{filter_suffix}.json"
    
    router_report.save_to_file(str(router_path))
    agent_report.save_to_file(str(agent_path))
    e2e_report.save_to_file(str(e2e_path))
    
    # Print summaries
    print("Router Evaluation:")
    print(router_report.get_summary())
    print("\nAgent Evaluation:")
    print(agent_report.get_summary())
    print("\nEnd-to-End Evaluation:")
    print(e2e_report.get_summary())
    
    logger.info("Filtered evaluation completed", filter_criteria=filter_criteria)
    return router_report, agent_report, e2e_report


async def main():
    """Main evaluation function."""
    parser = argparse.ArgumentParser(description="Run AIaaS platform evaluation")
    parser.add_argument("--type", choices=["router", "agent", "e2e", "all"], default="all",
                       help="Type of evaluation to run")
    parser.add_argument("--output-dir", default="eval_results",
                       help="Output directory for evaluation results")
    parser.add_argument("--filter-difficulty", choices=["easy", "medium", "hard"],
                       help="Filter tasks by difficulty")
    parser.add_argument("--filter-domain", choices=["general", "ecommerce", "technical", "finance"],
                       help="Filter tasks by domain")
    parser.add_argument("--filter-category", 
                       help="Filter tasks by category")
    parser.add_argument("--judge-model", default="gpt-3.5-turbo",
                       help="LLM model for judge")
    parser.add_argument("--judge-temperature", type=float, default=0.1,
                       help="Temperature for judge")
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Create evaluator
    judge_config = LLMJudgeConfig(
        model_name=args.judge_model,
        temperature=args.judge_temperature
    )
    
    evaluator = Evaluator(judge_config)
    await evaluator.initialize()
    
    # Prepare filter criteria
    filter_criteria = {}
    if args.filter_difficulty:
        filter_criteria["difficulty"] = args.filter_difficulty
    if args.filter_domain:
        filter_criteria["domain"] = args.filter_domain
    if args.filter_category:
        filter_criteria["category"] = args.filter_category
    
    # Run evaluations
    if args.type == "router":
        await run_router_evaluation(evaluator, output_dir)
    elif args.type == "agent":
        await run_agent_evaluation(evaluator, output_dir)
    elif args.type == "e2e":
        await run_e2e_evaluation(evaluator, output_dir)
    elif args.type == "all":
        if filter_criteria:
            await run_filtered_evaluation(evaluator, output_dir, filter_criteria)
        else:
            await run_router_evaluation(evaluator, output_dir)
            await run_agent_evaluation(evaluator, output_dir)
            await run_e2e_evaluation(evaluator, output_dir)
    
    logger.info("Evaluation completed", output_dir=str(output_dir))


if __name__ == "__main__":
    asyncio.run(main())
