import logging
import os
import json
from typing import Dict, Any, List
import datetime

logger = logging.getLogger(__name__)

class ReportGenerator:
    """
    Generates summary text, markdown report, and dashboard using Chart.js or HTML.
    """

    def __init__(self, output_dir: str = "workspace/reports"):
        self.output_dir = os.path.abspath(os.path.join(os.getcwd(), output_dir))
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_report(self, plan: Dict[str, Any], results: List[Dict[str, Any]], validation: Dict[str, Any]) -> str:
        """
        Generates and writes a markdown report for the entire lab run.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_title = f"R&D Report: {plan.get('goal', 'Unknown Goal')} - {timestamp}"
        
        # Build Markdown
        md = f"# {report_title}\n\n"
        md += f"**Timestamp:** {timestamp}\n"
        md += f"**Goal:** {plan.get('goal')}\n"
        md += f"**Method:** {plan.get('method')}\n"
        md += f"**Criteria:** {plan.get('success_criteria')}\n"
        md += f"**Overall Success:** {'Yes' if validation.get('success') else 'No'}\n"
        md += f"**Validation Reasoning:** {validation.get('reasoning')}\n\n"
        
        md += "## Execution Logs\n\n"
        for idx, result in enumerate(results):
            md += f"### Step {result.get('step_id', idx+1)}: {result.get('action')}\n"
            md += f"**Command:** `{result.get('command')}`\n"
            output = result.get('output', {})
            md += f"**Exit Code:** {output.get('exit_code')}\n"
            md += f"**Execution Time:** {output.get('execution_time'):.2f}s\n"
            
            md += "#### stdout\n```\n"
            md += output.get('stdout', '') + "\n```\n"

            if output.get('stderr'):
                md += "#### stderr\n```\n"
                md += output.get('stderr', '') + "\n```\n"
        
        md += "## Insights & Recommendation\n\n"
        if validation.get("success"):
            md += "The experiment was successful. The system recommends integrating or proceeding with the changes proposed.\n"
        else:
            md += "The experiment failed. The system recommends reviewing the errors and attempting a revised experiment.\n"
            
        report_path = os.path.join(self.output_dir, f"report_{timestamp}.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md)
            
        logger.info(f"Generated report at {report_path}")
        return report_path

    def generate_dashboard(self, plan: Dict[str, Any], validation: Dict[str, Any]) -> str:
        """
        Generates a simplified HTML dashboard using Chart.js or just basic metrics.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        metrics = validation.get("metrics", {})
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>S.A.I. R&D Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        .metric-card {{ border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 10px; width: 30%; display: inline-block; text-align: center; }}
        .success {{ color: green; }}
        .failure {{ color: red; }}
    </style>
</head>
<body>
    <h1>S.A.I. R&D Dashboard</h1>
    <h2>Goal: {plan.get('goal', 'N/A')}</h2>
    
    <div class="metric-card">
        <h3>Status</h3>
        <p class="{'success' if validation.get('success') else 'failure'}">
            <strong>{'SUCCESS' if validation.get('success') else 'FAILURE'}</strong>
        </p>
    </div>
    <div class="metric-card">
        <h3>Metrics</h3>
        <pre>{json.dumps(metrics, indent=2)}</pre>
    </div>

    <!-- Chart Example -->
    <div style="width: 50%; margin-top: 20px;">
        <canvas id="metricsChart"></canvas>
    </div>
    
    <script>
        var ctx = document.getElementById('metricsChart').getContext('2d');
        var chart = new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: ['Total Steps', 'Failed Steps'],
                datasets: [{{
                    label: 'Experiment Execution Stats',
                    data: [{metrics.get('total_steps', 0)}, {metrics.get('failed_steps', 0)}],
                    backgroundColor: ['rgba(54, 162, 235, 0.2)', 'rgba(255, 99, 132, 0.2)'],
                    borderColor: ['rgba(54, 162, 235, 1)', 'rgba(255, 99, 132, 1)'],
                    borderWidth: 1
                }}]
            }},
            options: {{
                scales: {{
                    y: {{ beginAtZero: true }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
        dash_path = os.path.join(self.output_dir, f"dashboard_{timestamp}.html")
        with open(dash_path, "w", encoding="utf-8") as f:
            f.write(html)
            
        logger.info(f"Generated dashboard at {dash_path}")
        return dash_path
