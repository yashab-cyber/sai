"""
Code Generator — Generates self-contained Streamlit dashboard scripts.

Takes an InsightReport and produces a runnable Streamlit Python file
with embedded data, charts, and insights. No external data files needed.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger("SAI.Intelligence.CodeGenerator")

DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "workspace", "dashboards")


class CodeGenerator:
    """Generates Streamlit dashboard scripts from InsightReports."""

    def __init__(self, coder=None, output_dir: str = DASHBOARD_DIR):
        self.coder = coder
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate(self, report: Dict[str, Any]) -> str:
        """Generates a self-contained Streamlit script from an InsightReport.

        Args:
            report: InsightReport dict from InsightAnalyzer

        Returns:
            Absolute path to the generated .py file
        """
        query = report.get("query", "analysis")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in query.lower())[:30]
        filename = f"intel_{safe_name}_{timestamp}.py"
        filepath = os.path.join(self.output_dir, filename)

        code = self._build_dashboard_code(report)

        if self.coder:
            self.coder.write_module(filepath, code)
        else:
            with open(filepath, "w") as f:
                f.write(code)

        logger.info("Dashboard generated: %s", filepath)
        return os.path.abspath(filepath)

    def _build_dashboard_code(self, report: Dict[str, Any]) -> str:
        """Builds dashboard code line-by-line to avoid quote-nesting issues."""
        report_json = json.dumps(report, indent=2, default=str)
        query = report.get("query", "Intelligence Report")
        generated_at = datetime.now().isoformat()

        L = []
        a = L.append

        # ── Header & imports ──
        a('"""')
        a('S.A.I. Intelligence Dashboard')
        a('Query: ' + query)
        a('Generated: ' + generated_at)
        a('"""')
        a('import streamlit as st')
        a('import json')
        a('')
        a('# Page Config')
        a('st.set_page_config(')
        a('    page_title="S.A.I. Intelligence — ' + query + '",')
        a('    page_icon="\\U0001f9e0",')
        a('    layout="wide",')
        a('    initial_sidebar_state="collapsed"')
        a(')')
        a('')

        # ── Embedded data ──
        a('# Embedded Data')
        a("REPORT = json.loads('''")
        a(report_json)
        a("''')")
        a('')

        # ── CSS ──
        a('# Custom CSS')
        a('_CSS = """')
        a('<style>')
        a('.stApp {')
        a('    background: linear-gradient(135deg, #0a0e1a 0%, #0d1b2a 50%, #1b263b 100%);')
        a('    color: #c8d6df;')
        a('}')
        a('.metric-card {')
        a('    background: rgba(255,255,255,0.03);')
        a('    border: 1px solid rgba(0,229,255,0.1);')
        a('    border-radius: 16px;')
        a('    padding: 24px;')
        a('    text-align: center;')
        a('}')
        a('.metric-value {')
        a('    font-size: 2.2em;')
        a('    font-weight: 800;')
        a('    color: #00e5ff;')
        a('}')
        a('.metric-label {')
        a('    font-size: 0.85em;')
        a('    text-transform: uppercase;')
        a('    letter-spacing: 2px;')
        a('    color: #3d6b7f;')
        a('    margin-top: 8px;')
        a('}')
        a('.theme-tag {')
        a('    display: inline-block;')
        a('    background: rgba(0,229,255,0.08);')
        a('    border: 1px solid rgba(0,229,255,0.2);')
        a('    border-radius: 20px;')
        a('    padding: 6px 16px;')
        a('    margin: 4px;')
        a('    color: #00e5ff;')
        a('    font-weight: 600;')
        a('}')
        a('.risk-tag {')
        a('    display: inline-block;')
        a('    background: rgba(255,61,113,0.08);')
        a('    border: 1px solid rgba(255,61,113,0.2);')
        a('    border-radius: 20px;')
        a('    padding: 6px 16px;')
        a('    margin: 4px;')
        a('    color: #ff3d71;')
        a('}')
        a('.opp-tag {')
        a('    display: inline-block;')
        a('    background: rgba(0,255,136,0.08);')
        a('    border: 1px solid rgba(0,255,136,0.2);')
        a('    border-radius: 20px;')
        a('    padding: 6px 16px;')
        a('    margin: 4px;')
        a('    color: #00ff88;')
        a('}')
        a('h1, h2, h3 { color: #e0e8ef !important; }')
        a('.stMarkdown p { color: #8899a6; }')
        a('</style>')
        a('"""')
        a('st.markdown(_CSS, unsafe_allow_html=True)')
        a('')

        # ── Dashboard body (static template — no f-strings in generator) ──
        # These lines are written as literal Python source code.
        body_lines = [
            '# Header',
            'st.markdown("# \\U0001f9e0 S.A.I. Intelligence Dashboard")',
            'st.markdown(f"### Query: *{REPORT.get(\'query\', \'N/A\')}*")',
            'st.markdown("---")',
            '',
            '# Metrics Row',
            'col1, col2, col3, col4 = st.columns(4)',
            'sentiment = REPORT.get("sentiment", {})',
            'with col1:',
            '    v = REPORT.get("data_point_count", 0)',
            '    st.markdown(f\'<div class="metric-card"><div class="metric-value">{v}</div><div class="metric-label">Data Points</div></div>\', unsafe_allow_html=True)',
            'with col2:',
            '    v = len(REPORT.get("themes", []))',
            '    st.markdown(f\'<div class="metric-card"><div class="metric-value">{v}</div><div class="metric-label">Themes</div></div>\', unsafe_allow_html=True)',
            'with col3:',
            '    v = sentiment.get("overall", "N/A").upper()',
            '    st.markdown(f\'<div class="metric-card"><div class="metric-value">{v}</div><div class="metric-label">Sentiment</div></div>\', unsafe_allow_html=True)',
            'with col4:',
            '    v = len(REPORT.get("sources", []))',
            '    st.markdown(f\'<div class="metric-card"><div class="metric-value">{v}</div><div class="metric-label">Sources</div></div>\', unsafe_allow_html=True)',
            '',
            'st.markdown("")',
            '',
            '# Executive Summary',
            'st.markdown("## \\U0001f4cb Executive Summary")',
            'st.info(REPORT.get("summary", "No summary available."))',
            '',
            '# Two-column layout',
            'left, right = st.columns(2)',
            '',
            'with left:',
            '    st.markdown("## \\U0001f3af Key Themes")',
            '    themes = REPORT.get("themes", [])',
            '    if themes:',
            '        theme_data = {t["name"]: t.get("strength", 5) for t in themes}',
            '        st.bar_chart(theme_data)',
            '        tags_html = " ".join(f\'<span class="theme-tag">{t["name"]}</span>\' for t in themes)',
            '        st.markdown(tags_html, unsafe_allow_html=True)',
            '    else:',
            '        st.warning("No themes identified.")',
            '',
            '    st.markdown("## \\U0001f4ca Sentiment Analysis")',
            '    breakdown = sentiment.get("breakdown", {})',
            '    if breakdown:',
            '        st.bar_chart(breakdown)',
            '        score = sentiment.get("score", 0)',
            '        emoji = "\\U0001f7e2" if score > 0.3 else "\\U0001f534" if score < -0.3 else "\\U0001f7e1"',
            '        st.markdown(f"**Sentiment Score:** {emoji} {score:.2f}")',
            '',
            'with right:',
            '    st.markdown("## \\U0001f4c8 Trends")',
            '    trends = REPORT.get("trends", [])',
            '    if trends:',
            '        for t in trends:',
            '            direction = t.get("direction", "stable")',
            '            icon = "\\U0001f4c8" if direction == "rising" else "\\U0001f4c9" if direction == "falling" else "\\u27a1\\ufe0f"',
            '            st.markdown(f"{icon} **{t[\'name\']}** \\u2014 {direction} (significance: {t.get(\'significance\', \'?\')}/10)")',
            '    else:',
            '        st.info("No trend data available.")',
            '',
            '    st.markdown("## \\u26a0\\ufe0f Risks")',
            '    risks = REPORT.get("risks", [])',
            '    if risks:',
            '        risk_html = " ".join(f\'<span class="risk-tag">{r}</span>\' for r in risks)',
            '        st.markdown(risk_html, unsafe_allow_html=True)',
            '',
            '    st.markdown("## \\U0001f4a1 Opportunities")',
            '    opportunities = REPORT.get("opportunities", [])',
            '    if opportunities:',
            '        opp_html = " ".join(f\'<span class="opp-tag">{o}</span>\' for o in opportunities)',
            '        st.markdown(opp_html, unsafe_allow_html=True)',
            '',
            '# Key Data Points',
            'st.markdown("---")',
            'st.markdown("## \\U0001f511 Key Data Points")',
            'key_points = REPORT.get("key_data_points", [])',
            'for i, point in enumerate(key_points, 1):',
            '    st.markdown(f"**{i}.** {point}")',
            '',
            '# Footer',
            'st.markdown("---")',
            'sources = REPORT.get("sources", [])',
            'st.caption(f"Sources: {\', \'.join(sources)} | Generated by S.A.I. Intelligence Engine")',
        ]

        L.extend(body_lines)
        return "\n".join(L)
