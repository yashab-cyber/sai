"""
Insight Analyzer — LLM-powered data analysis and summarization.

Takes raw data points from DataCollector and produces a structured
InsightReport with themes, sentiment, trends, and recommendations.
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("SAI.Intelligence.InsightAnalyzer")


class InsightAnalyzer:
    """Analyzes collected data using SAI's Brain (LLM)."""

    def __init__(self, brain):
        """
        Args:
            brain: SAI's Brain instance (core.brain.Brain)
        """
        self.brain = brain

    def analyze(self, data_points: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
        """Analyzes data points and returns a structured InsightReport.

        Args:
            data_points: List of DataPoint dicts from DataCollector
            query: The original user query for context

        Returns:
            InsightReport dict with themes, sentiment, trends, risks, summary
        """
        if not data_points:
            return self._empty_report(query)

        # Prepare a condensed version for the LLM (avoid token overflow)
        condensed = []
        for dp in data_points[:25]:
            condensed.append({
                "source": dp.get("source", "unknown"),
                "title": dp.get("title", "")[:120],
                "text": dp.get("text", "")[:300],
                "type": dp.get("type", "article"),
            })

        system_prompt, user_query = self._build_analysis_prompt(query, condensed)

        try:
            response = self.brain.prompt(system_prompt, user_query)
            # brain.prompt returns a dict; convert to string for parsing if needed
            if isinstance(response, dict):
                report = response
                report["query"] = query
                report["data_point_count"] = len(data_points)
                report["sources"] = list(set(dp.get("source", "unknown").split("/")[0] for dp in data_points))
                report["data_types"] = list(set(dp.get("type", "unknown") for dp in data_points))
                return report
            report = self._parse_response(str(response), query, data_points)
            logger.info("Analysis complete: %d themes, %d trends identified",
                       len(report.get("themes", [])), len(report.get("trends", [])))
            return report
        except Exception as e:
            logger.error("LLM analysis failed: %s", e)
            return self._fallback_analysis(data_points, query)

    def _build_analysis_prompt(self, query: str, data: List[Dict]) -> tuple:
        """Builds the LLM prompt for analysis.

        Returns:
            Tuple of (system_prompt, user_query) for Brain.prompt()
        """
        data_json = json.dumps(data, indent=2, default=str)

        system_prompt = (
            "You are an intelligence analyst for S.A.I., an advanced AI system. "
            "Analyze data and provide structured intelligence reports. "
            "Respond ONLY in valid JSON."
        )

        user_query = f"""Analyze the following data about "{query}" and provide a structured report.

DATA COLLECTED:
{data_json}

Respond in VALID JSON only. Schema:
{{
  "summary": "3-5 sentence executive summary",
  "themes": [
    {{"name": "theme name", "description": "brief description", "strength": 1-10}}
  ],
  "sentiment": {{
    "overall": "positive|negative|neutral|mixed",
    "score": -1.0 to 1.0,
    "breakdown": {{"positive": 0-100, "negative": 0-100, "neutral": 0-100}}
  }},
  "trends": [
    {{"name": "trend name", "direction": "rising|falling|stable", "significance": 1-10}}
  ],
  "risks": ["risk 1", "risk 2"],
  "opportunities": ["opportunity 1", "opportunity 2"],
  "key_data_points": ["most important finding 1", "finding 2", "finding 3"]
}}"""

        return system_prompt, user_query

    def _parse_response(self, response: str, query: str, data_points: List[Dict]) -> Dict[str, Any]:
        """Parses the LLM response into a structured InsightReport."""
        # Extract JSON from response (handle markdown code blocks)
        json_str = response
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]

        try:
            report = json.loads(json_str.strip())
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON, using fallback analysis")
            return self._fallback_analysis(data_points, query)

        # Enrich with metadata
        report["query"] = query
        report["data_point_count"] = len(data_points)
        report["sources"] = list(set(dp.get("source", "unknown").split("/")[0] for dp in data_points))
        report["data_types"] = list(set(dp.get("type", "unknown") for dp in data_points))

        return report

    def _fallback_analysis(self, data_points: List[Dict], query: str) -> Dict[str, Any]:
        """Generates a basic analysis without LLM when it fails."""
        # Simple word frequency analysis
        all_text = " ".join(dp.get("title", "") + " " + dp.get("text", "") for dp in data_points)
        words = all_text.lower().split()

        # Filter common words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
                      "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
                      "has", "have", "had", "it", "its", "this", "that", "these", "those"}
        filtered = [w for w in words if len(w) > 3 and w not in stop_words and w.isalpha()]

        # Count frequencies
        freq: Dict[str, int] = {}
        for w in filtered:
            freq[w] = freq.get(w, 0) + 1

        top_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
        themes = [{"name": w, "description": f"Mentioned {c} times", "strength": min(c, 10)} for w, c in top_words[:5]]

        return {
            "query": query,
            "summary": f"Collected {len(data_points)} data points about '{query}'. Top themes: {', '.join(w for w, _ in top_words[:5])}.",
            "themes": themes,
            "sentiment": {"overall": "neutral", "score": 0.0, "breakdown": {"positive": 33, "negative": 33, "neutral": 34}},
            "trends": [{"name": w, "direction": "stable", "significance": min(c, 10)} for w, c in top_words[:3]],
            "risks": ["Analysis limited — LLM unavailable"],
            "opportunities": [],
            "key_data_points": [dp.get("title", "") for dp in data_points[:3]],
            "data_point_count": len(data_points),
            "sources": list(set(dp.get("source", "").split("/")[0] for dp in data_points)),
            "data_types": list(set(dp.get("type", "unknown") for dp in data_points)),
        }

    def _empty_report(self, query: str) -> Dict[str, Any]:
        """Returns an empty report when no data is available."""
        return {
            "query": query,
            "summary": f"No data collected for '{query}'. Please check your internet connection or try a different query.",
            "themes": [],
            "sentiment": {"overall": "neutral", "score": 0.0, "breakdown": {"positive": 0, "negative": 0, "neutral": 100}},
            "trends": [],
            "risks": ["No data available"],
            "opportunities": [],
            "key_data_points": [],
            "data_point_count": 0,
            "sources": [],
            "data_types": [],
        }
