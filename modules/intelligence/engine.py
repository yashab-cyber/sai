"""
Intelligence Engine — Orchestrator for the full intelligence pipeline.

Ties together DataCollector, InsightAnalyzer, CodeGenerator,
DashboardRunner, and VoiceExplainer into a single analyze() call.
"""

import logging
from typing import Dict, Any, List, Optional

from modules.intelligence.data_collector import DataCollector
from modules.intelligence.insight_analyzer import InsightAnalyzer
from modules.intelligence.code_generator import CodeGenerator
from modules.intelligence.dashboard_runner import DashboardRunner
from modules.intelligence.voice_explainer import VoiceExplainer
from modules.intelligence.report_generator import ReportGenerator

logger = logging.getLogger("SAI.Intelligence.Engine")


class IntelligenceEngine:
    """Orchestrates the full intelligence pipeline.

    Usage:
        engine = IntelligenceEngine(sai_instance)
        result = engine.analyze("AI trends")
        # → collects data, analyzes, generates dashboard, runs it, narrates
    """

    def __init__(self, sai):
        """
        Args:
            sai: The main SAI instance (provides brain, voice, config)
        """
        self.sai = sai
        self.collector = DataCollector()
        self.analyzer = InsightAnalyzer(sai.brain)
        self.generator = CodeGenerator(coder=sai.coder)
        self.report_generator = ReportGenerator()
        self.runner = DashboardRunner()
        self.explainer = VoiceExplainer(sai.voice if hasattr(sai, 'voice') else None)

        logger.info("Intelligence Engine initialized, sir. All sub-systems operational.")

    def analyze(self, query: str, sources: Optional[List[str]] = None,
                narrate: bool = True) -> Dict[str, Any]:
        """Full intelligence pipeline: collect → analyze → generate → run → narrate.

        Args:
            query: The intelligence query (e.g. "AI trends", "crypto market")
            sources: Data sources to use ("rss", "news", "trends", "scrape")
            narrate: Whether to speak the insights via voice

        Returns:
            Dict with status, report, dashboard_url, narration
        """
        logger.info("Intelligence Engine engaged, sir. Query: %s", query)

        # ── Step 1: Collect Data ──
        logger.info("Step 1/5: Collecting world data...")
        try:
            data_points = self.collector.collect(query, sources=sources)
        except Exception as e:
            logger.error("Data collection failed: %s", e)
            return {"status": "failed", "error": f"Data collection failed: {e}",
                    "stage": "collect"}

        if not data_points:
            msg = f"No data found for '{query}', sir. Please check your connection or try a broader query."
            logger.warning(msg)
            return {"status": "failed", "error": msg, "stage": "collect",
                    "data_points": 0}

        logger.info("Collected %d data points.", len(data_points))

        # ── Step 2: Analyze with LLM ──
        logger.info("Step 2/5: Analyzing data with LLM...")
        try:
            report = self.analyzer.analyze(data_points, query)
        except Exception as e:
            logger.error("Insight analysis failed: %s", e)
            return {"status": "partial", "error": f"Analysis failed: {e}",
                    "stage": "analyze", "data_points": len(data_points)}

        # ── Step 3: Generate Dashboard ──
        logger.info("Step 3/5: Generating Streamlit dashboard...")
        dashboard_path = None
        try:
            dashboard_path = self.generator.generate(report)
            logger.info("Dashboard script generated: %s", dashboard_path)
        except Exception as e:
            logger.error("Dashboard generation failed: %s", e)
            # Non-fatal — we still have the report

        # ── Step 4: Launch Dashboard ──
        dashboard_url = None
        dashboard_result = None
        if dashboard_path:
            logger.info("Step 4/5: Launching dashboard...")
            try:
                dashboard_result = self.runner.launch(dashboard_path)
                if dashboard_result.get("status") == "success":
                    dashboard_url = dashboard_result["url"]
                    logger.info("Dashboard live at %s", dashboard_url)
                else:
                    logger.warning("Dashboard launch failed: %s",
                                   dashboard_result.get("error", "unknown"))
            except Exception as e:
                logger.error("Dashboard launch error: %s", e)

        # ── Step 5: Voice Narration ──
        narration_text = None
        if narrate:
            logger.info("Step 5/5: Narrating intelligence briefing...")
            try:
                narration_text = self.explainer.narrate(report)
            except Exception as e:
                logger.warning("Voice narration failed: %s", e)

        # ── Final Result ──
        result = {
            "status": "success",
            "query": query,
            "data_points": len(data_points),
            "report": report,
            "dashboard_url": dashboard_url,
            "dashboard_script": dashboard_path,
            "narration": narration_text,
            "message": (
                f"Intelligence analysis complete, sir. "
                f"Analyzed {len(data_points)} data points. "
                f"{'Dashboard live at ' + dashboard_url if dashboard_url else 'Dashboard generation skipped.'}"
            ),
        }

        logger.info("Intelligence Engine complete. Status: %s", result["status"])
        return result

    def collect_only(self, query: str, sources: Optional[List[str]] = None,
                     max_items: int = 30) -> Dict[str, Any]:
        """Collects data without analysis or dashboard.

        Args:
            query: Search query
            sources: Data sources to use
            max_items: Maximum items to collect

        Returns:
            Dict with status and collected data points
        """
        try:
            data_points = self.collector.collect(query, sources=sources, max_items=max_items)
            return {
                "status": "success",
                "query": query,
                "data_points": data_points,
                "count": len(data_points),
                "message": f"Collected {len(data_points)} data points for '{query}', sir.",
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def stop_dashboard(self) -> Dict[str, Any]:
        """Stops the currently running intelligence dashboard."""
        return self.runner.stop()

    def dashboard_status(self) -> Dict[str, Any]:
        """Returns the current dashboard status."""
        return self.runner.status()

    def deep_research(self, query: str, narrate: bool = True) -> Dict[str, Any]:
        """Orchestrates an intensive R&D deep dive using academic sources.

        Args:
            query: The research topic
            narrate: Whether to voice-narrate the outcome

        Returns:
            Dict containing the status and the markdown report path.
        """
        logger.info("Initializing multi-disciplinary Deep Research on: %s", query)
        
        sources = ["arxiv", "pubmed", "wikipedia", "news", "scrape"]

        logger.info("Step 1/3: Collecting academic and public data...")
        try:
            data_points = self.collector.collect(query, sources=sources, max_items=50)
        except Exception as e:
            logger.error("Deep search failed: %s", e)
            return {"status": "failed", "error": str(e)}

        if not data_points:
            return {"status": "failed", "error": f"No data found for {query}"}

        logger.info("Step 2/3: Synthesizing analytical report...")
        try:
            report = self.analyzer.analyze(data_points, query)
        except Exception as e:
            logger.error("Synthesis failed: %s", e)
            return {"status": "failed", "error": str(e)}

        logger.info("Step 3/3: Generating massive Markdown document...")
        report_path = None
        try:
            report_path = self.report_generator.generate(report)
        except Exception as e:
            logger.error("Report generation failed: %s", e)

        narration_text = None
        if narrate:
            try:
                narration_text = self.explainer.narrate(report)
            except Exception as e:
                pass

        return {
            "status": "success",
            "query": query,
            "data_points_analyzed": len(data_points),
            "report_path": report_path,
            "narration": narration_text,
            "message": f"Deep Research Synthesized. Total sources: {len(data_points)}. Report accessible at: {report_path}"
        }
