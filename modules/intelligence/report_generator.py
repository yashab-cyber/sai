import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger("SAI.Intelligence.ReportGenerator")

RESEARCH_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "workspace", "research")


class ReportGenerator:
    """Generates comprehensive Markdown research reports from InsightReports."""

    def __init__(self, output_dir: str = RESEARCH_DIR):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate(self, report: Dict[str, Any]) -> str:
        """Generates a deep synthesis Markdown report.

        Args:
            report: InsightReport dict from InsightAnalyzer

        Returns:
            Absolute path to the generated .md file
        """
        query = report.get("query", "analysis")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in query.lower())[:30]
        filename = f"Research_{safe_name}_{timestamp}.md"
        filepath = os.path.join(self.output_dir, filename)

        markdown_content = self._build_markdown(report)

        with open(filepath, "w") as f:
            f.write(markdown_content)

        logger.info("Research report generated: %s", filepath)
        return os.path.abspath(filepath)

    def _build_markdown(self, report: Dict[str, Any]) -> str:
        """Constructs the structured Markdown document."""
        query = report.get("query", "Intelligence Report")
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        lines = [
            f"# Research Synthesis Report: {query}",
            f"**Prepared by:** S.A.I. Research & Development Engine",
            f"**Date:** {generated_at}",
            "---",
            "",
            "## 1. Executive Summary",
            report.get("summary", "No summary available."),
            "",
            "## 2. Core Themes Identified",
        ]

        themes = report.get("themes", [])
        if themes:
            for t in themes:
                lines.append(f"- **{t['name']}** (Confidence: {t.get('strength', '?')}/10): {t.get('description', '')}")
        else:
            lines.append("*No distinct themes identified.*")
            
        lines.extend([
            "",
            "## 3. Key Findings & Data Points",
        ])

        key_points = report.get("key_data_points", [])
        if key_points:
            for pt in key_points:
                lines.append(f"- {pt}")
        else:
            lines.append("*No specific data points extracted.*")

        lines.extend([
            "",
            "## 4. Trend Analysis",
        ])

        trends = report.get("trends", [])
        if trends:
            for t in trends:
                icon = "↗️" if t.get("direction") == "rising" else "↘️" if t.get("direction") == "falling" else "➡️"
                lines.append(f"- {icon} **{t['name']}** (Significance: {t.get('significance', '?')}/10)")
        else:
            lines.append("*No notable trends identified.*")

        lines.extend([
            "",
            "## 5. Strategic Intelligence",
            "### Known Risks & Limitations",
        ])
        
        for r in report.get("risks", ["None documented."]):
            lines.append(f"- {r}")

        lines.extend([
            "",
            "### Theoretical Opportunities",
        ])
        for o in report.get("opportunities", ["None documented."]):
            lines.append(f"- {o}")

        lines.extend([
            "",
            "---",
            "## 6. Sourcing & Metadata",
            f"- **Total Data Points Analyzed:** {report.get('data_point_count', 'Unknown')}",
            f"- **Sources Tracked:** {', '.join(report.get('sources', []))}",
            f"- **Data Types:** {', '.join(report.get('data_types', []))}",
            ""
        ])

        return "\n".join(lines)
