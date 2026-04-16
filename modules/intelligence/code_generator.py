"""
Code Generator — Generates self-contained Streamlit dashboard scripts.

Takes an InsightReport and produces a runnable Streamlit Python file
with embedded data, charts, and insights. No external data files needed.
"""

import os
import json
import logging
import textwrap
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger("SAI.Intelligence.CodeGenerator")

DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "workspace", "dashboards")


class CodeGenerator:
    """Generates Streamlit dashboard scripts from InsightReports."""

    def __init__(self, output_dir: str = DASHBOARD_DIR):
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

        with open(filepath, "w") as f:
            f.write(code)

        logger.info("Dashboard generated: %s", filepath)
        return os.path.abspath(filepath)

    def _build_dashboard_code(self, report: Dict[str, Any]) -> str:
        """Builds the full Streamlit dashboard Python code."""
        # Serialize report data for embedding
        report_json = json.dumps(report, indent=2, default=str)

        query = report.get("query", "Intelligence Report")
        summary = report.get("summary", "No summary available.")
        sentiment = report.get("sentiment", {})
        themes = report.get("themes", [])
        trends = report.get("trends", [])
        risks = report.get("risks", [])
        opportunities = report.get("opportunities", [])
        key_points = report.get("key_data_points", [])
        sources = report.get("sources", [])
        data_count = report.get("data_point_count", 0)

        code = textwrap.dedent(f'''\
            """
            S.A.I. Intelligence Dashboard
            Query: {query}
            Generated: {datetime.now().isoformat()}
            """
            import streamlit as st
            import json

            # ── Page Config ──
            st.set_page_config(
                page_title=f"S.A.I. Intelligence — {json.dumps(query)[1:-1]}",
                page_icon="🧠",
                layout="wide",
                initial_sidebar_state="collapsed"
            )

            # ── Embedded Data ──
            REPORT = json.loads("""{report_json}""")

            # ── Custom CSS ──
            st.markdown("""
            <style>
                .stApp {{
                    background: linear-gradient(135deg, #0a0e1a 0%, #0d1b2a 50%, #1b263b 100%);
                    color: #c8d6df;
                }}
                .metric-card {{
                    background: rgba(255,255,255,0.03);
                    border: 1px solid rgba(0,229,255,0.1);
                    border-radius: 16px;
                    padding: 24px;
                    text-align: center;
                }}
                .metric-value {{
                    font-size: 2.2em;
                    font-weight: 800;
                    color: #00e5ff;
                }}
                .metric-label {{
                    font-size: 0.85em;
                    text-transform: uppercase;
                    letter-spacing: 2px;
                    color: #3d6b7f;
                    margin-top: 8px;
                }}
                .theme-tag {{
                    display: inline-block;
                    background: rgba(0,229,255,0.08);
                    border: 1px solid rgba(0,229,255,0.2);
                    border-radius: 20px;
                    padding: 6px 16px;
                    margin: 4px;
                    color: #00e5ff;
                    font-weight: 600;
                }}
                .risk-tag {{
                    display: inline-block;
                    background: rgba(255,61,113,0.08);
                    border: 1px solid rgba(255,61,113,0.2);
                    border-radius: 20px;
                    padding: 6px 16px;
                    margin: 4px;
                    color: #ff3d71;
                }}
                .opp-tag {{
                    display: inline-block;
                    background: rgba(0,255,136,0.08);
                    border: 1px solid rgba(0,255,136,0.2);
                    border-radius: 20px;
                    padding: 6px 16px;
                    margin: 4px;
                    color: #00ff88;
                }}
                h1, h2, h3 {{ color: #e0e8ef !important; }}
                .stMarkdown p {{ color: #8899a6; }}
            </style>
            """, unsafe_allow_html=True)

            # ── Header ──
            st.markdown("# 🧠 S.A.I. Intelligence Dashboard")
            st.markdown(f"### Query: *{{REPORT.get('query', 'N/A')}}*")
            st.markdown("---")

            # ── Metrics Row ──
            col1, col2, col3, col4 = st.columns(4)
            sentiment = REPORT.get("sentiment", {{}})
            with col1:
                st.markdown(f"""<div class="metric-card"><div class="metric-value">{{REPORT.get('data_point_count', 0)}}</div><div class="metric-label">Data Points</div></div>""", unsafe_allow_html=True)
            with col2:
                st.markdown(f"""<div class="metric-card"><div class="metric-value">{{len(REPORT.get('themes', []))}}</div><div class="metric-label">Themes</div></div>""", unsafe_allow_html=True)
            with col3:
                sentiment_val = sentiment.get("overall", "N/A").upper()
                st.markdown(f"""<div class="metric-card"><div class="metric-value">{{sentiment_val}}</div><div class="metric-label">Sentiment</div></div>""", unsafe_allow_html=True)
            with col4:
                st.markdown(f"""<div class="metric-card"><div class="metric-value">{{len(REPORT.get('sources', []))}}</div><div class="metric-label">Sources</div></div>""", unsafe_allow_html=True)

            st.markdown("")

            # ── Executive Summary ──
            st.markdown("## 📋 Executive Summary")
            st.info(REPORT.get("summary", "No summary available."))

            # ── Two-column layout ──
            left, right = st.columns(2)

            with left:
                # Themes
                st.markdown("## 🎯 Key Themes")
                themes = REPORT.get("themes", [])
                if themes:
                    # Bar chart
                    theme_data = {{t["name"]: t.get("strength", 5) for t in themes}}
                    st.bar_chart(theme_data)
                    # Tags
                    tags_html = " ".join(f'<span class="theme-tag">{{t["name"]}}</span>' for t in themes)
                    st.markdown(tags_html, unsafe_allow_html=True)
                else:
                    st.warning("No themes identified.")

                # Sentiment Breakdown
                st.markdown("## 📊 Sentiment Analysis")
                breakdown = sentiment.get("breakdown", {{}})
                if breakdown:
                    st.bar_chart(breakdown)
                    score = sentiment.get("score", 0)
                    emoji = "🟢" if score > 0.3 else "🔴" if score < -0.3 else "🟡"
                    st.markdown(f"**Sentiment Score:** {{emoji}} {{score:.2f}}")

            with right:
                # Trends
                st.markdown("## 📈 Trends")
                trends = REPORT.get("trends", [])
                if trends:
                    for t in trends:
                        direction = t.get("direction", "stable")
                        icon = "📈" if direction == "rising" else "📉" if direction == "falling" else "➡️"
                        st.markdown(f"{{icon}} **{{t['name']}}** — {{direction}} (significance: {{t.get('significance', '?')}}/10)")
                else:
                    st.info("No trend data available.")

                # Risks & Opportunities
                st.markdown("## ⚠️ Risks")
                risks = REPORT.get("risks", [])
                if risks:
                    risk_html = " ".join(f'<span class="risk-tag">{{r}}</span>' for r in risks)
                    st.markdown(risk_html, unsafe_allow_html=True)

                st.markdown("## 💡 Opportunities")
                opportunities = REPORT.get("opportunities", [])
                if opportunities:
                    opp_html = " ".join(f'<span class="opp-tag">{{o}}</span>' for o in opportunities)
                    st.markdown(opp_html, unsafe_allow_html=True)

            # ── Key Data Points ──
            st.markdown("---")
            st.markdown("## 🔑 Key Data Points")
            key_points = REPORT.get("key_data_points", [])
            for i, point in enumerate(key_points, 1):
                st.markdown(f"**{{i}}.** {{point}}")

            # ── Footer ──
            st.markdown("---")
            sources = REPORT.get("sources", [])
            st.caption(f"Sources: {{', '.join(sources)}} | Generated by S.A.I. Intelligence Engine")
        ''')

        return code
