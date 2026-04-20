import logging
from typing import Dict, Any, Optional

from .sandbox_manager import SandboxManager
from .experiment_planner import ExperimentPlanner
from .experiment_runner import ExperimentRunner
from .validator import Validator
from .report_generator import ReportGenerator
from .decision_engine import DecisionEngine
from .approval_system import ApprovalSystem
from .memory_store import MemoryStore

logger = logging.getLogger(__name__)

class RnDLabManager:
    """
    Orchestrates the entire Research and Development Lab.
    Integrates the Execution Pipeline.
    """

    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider
        self.sandbox = SandboxManager()
        self.planner = ExperimentPlanner(ai_provider=ai_provider)
        self.runner = ExperimentRunner(sandbox_manager=self.sandbox)
        self.validator = Validator(ai_provider=ai_provider)
        self.reporter = ReportGenerator()
        self.decision = DecisionEngine(ai_provider=ai_provider)
        self.approval = ApprovalSystem()
        self.memory = MemoryStore()

    def run_rnd_task(self, intent: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        The main pipeline to execute an R&D Task from intent to report.
        """
        logger.info(f"Starting R&D task: {intent}")
        retry_count = 0
        
        while retry_count < max_retries:
            logger.info(f"R&D Pipeline Iteration {retry_count + 1}/{max_retries}")
            
            # 1. GENERATE PLAN
            plan = self.planner.generate_plan(intent)
            if not plan:
                logger.error("Failed to generate an experiment plan.")
                return {"status": "error", "message": "Planning failed."}

            logger.info(f"Plan generated: {plan.get('goal')}")

            # 2. RUN IN SANDBOX
            logger.info("Running experiment in Sandbox...")
            results = self.runner.run_plan(plan)

            # 3. VALIDATE RESULTS
            logger.info("Validating experiment results...")
            validation = self.validator.validate(plan, results)

            # 4. REPORT & DASHBOARD
            logger.info("Generating Report and Dashboard...")
            report_path = self.reporter.generate_report(plan, results, validation)
            dash_path = self.reporter.generate_dashboard(plan, validation)
            
            logger.info(f"Report: {report_path}")
            logger.info(f"Dashboard: {dash_path}")

            # 5. SAVE LEARNINGS
            self.memory.save_learning(plan, validation)

            # 6. DECISION ENGINE
            decision = self.decision.decide(plan, validation, retry_count)
            logger.info(f"Decision logic determined: {decision['action']}")
            
            action = decision.get("action")
            reason = decision.get("reason")

            if action == "integrate":
                # Recommend integration but ASK first
                approved = self.approval.request_approval(
                    reason=f"Integration recommended for goal '{intent}'.\nReport available at {report_path}.\nReason: {reason}"
                )
                if approved:
                    logger.info("Integration approved! Proceeding with real integration...")
                    # Implementation for integration into core logic would go here
                    return {"status": "success", "message": "Experiment and integration completed.", "report": report_path}
                else:
                    logger.info("Integration denied by user.")
                    return {"status": "denied", "message": "Integration aborted by user.", "report": report_path}
            elif action == "retry":
                logger.info(f"Retrying experiment. Reason: {reason}")
                retry_count += 1
                # Here we could modify intent based on the failure reasoning.
                # intent = f"{intent}. Previous attempt failed with: {validation['reasoning']}"
            elif action == "discard":
                logger.info("Experiment discarded. Reason: " + reason)
                return {"status": "discarded", "message": reason, "report": report_path}
            elif action == "escalate":
                logger.info("Requiring manual intervention (escalation).")
                approved = self.approval.request_approval(reason=reason + "\nDo you wish to forcefully integrate despite failures?")
                if approved:
                    logger.info("Forced integration approved via escalation.")
                    return {"status": "success", "message": "Forced integration approved via escalation.", "report": report_path}
                else:
                    logger.info("Escalation denied by user.")
                    return {"status": "denied", "message": "Escalation denied by user.", "report": report_path}

        return {"status": "timeout", "message": "Max retries reached."}
