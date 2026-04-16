"""
Voice Explainer — JARVIS-style spoken intelligence briefing.

Formats InsightReport into a natural spoken briefing and
uses SAI's VoiceManager to narrate it.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("SAI.Intelligence.VoiceExplainer")


class VoiceExplainer:
    """Formats and speaks intelligence insights."""

    def __init__(self, voice_manager=None):
        """
        Args:
            voice_manager: SAI's VoiceManager instance (modules.voice.VoiceManager)
        """
        self.voice = voice_manager

    def narrate(self, report: Dict[str, Any], max_insights: int = 5) -> str:
        """Narrates the top insights from a report.

        Args:
            report: InsightReport dict from InsightAnalyzer
            max_insights: Maximum number of insights to speak

        Returns:
            The full narration text
        """
        narration = self._format_briefing(report, max_insights)

        if self.voice:
            try:
                # Chunk long text to avoid TTS buffer issues
                chunks = self._chunk_text(narration, max_chars=250)
                for chunk in chunks:
                    self.voice.speak(chunk)
                logger.info("Intelligence briefing narrated (%d chunks)", len(chunks))
            except Exception as e:
                logger.warning("Voice narration failed: %s", e)
        else:
            logger.info("No voice manager — narration text only")

        return narration

    def _format_briefing(self, report: Dict[str, Any], max_insights: int = 5) -> str:
        """Formats the InsightReport into a JARVIS-style spoken briefing."""
        query = report.get("query", "the requested topic")
        summary = report.get("summary", "")
        themes = report.get("themes", [])
        sentiment = report.get("sentiment", {})
        trends = report.get("trends", [])
        risks = report.get("risks", [])
        data_count = report.get("data_point_count", 0)
        sources = report.get("sources", [])

        parts = []

        # Opening
        parts.append(f"Sir, here is your intelligence briefing on {query}.")
        parts.append(f"I've analyzed {data_count} data points from {len(sources)} sources.")

        # Summary
        if summary:
            parts.append(summary)

        # Sentiment
        overall = sentiment.get("overall", "neutral")
        score = sentiment.get("score", 0)
        if overall == "positive":
            parts.append(f"The overall sentiment is positive, with a score of {score:.1f}.")
        elif overall == "negative":
            parts.append(f"I should note, sir, the overall sentiment is negative, at {score:.1f}.")
        elif overall == "mixed":
            parts.append("The sentiment is mixed, sir. Conflicting signals in the data.")
        else:
            parts.append("The sentiment appears neutral at this time.")

        # Top themes
        if themes:
            top = themes[:min(max_insights, len(themes))]
            theme_names = ", ".join(t["name"] for t in top[:-1])
            if len(top) > 1:
                theme_names += f", and {top[-1]['name']}"
            else:
                theme_names = top[0]["name"]
            parts.append(f"The dominant themes are: {theme_names}.")

        # Trends
        rising = [t for t in trends if t.get("direction") == "rising"]
        if rising:
            rising_names = " and ".join(t["name"] for t in rising[:3])
            parts.append(f"Notable rising trends include {rising_names}.")

        # Risks
        if risks and risks[0] != "Analysis limited — LLM unavailable":
            parts.append(f"I've flagged {len(risks)} potential risk{'s' if len(risks) > 1 else ''}.")
            if len(risks) <= 2:
                for r in risks:
                    parts.append(f"Risk: {r}.")

        # Closing
        parts.append("The full dashboard is now live, sir. Shall I dive deeper into any area?")

        return " ".join(parts)

    def _chunk_text(self, text: str, max_chars: int = 250) -> list:
        """Splits text into chunks at sentence boundaries."""
        sentences = text.replace(". ", ".\n").split("\n")
        chunks = []
        current = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(current) + len(sentence) + 1 <= max_chars:
                current = f"{current} {sentence}".strip()
            else:
                if current:
                    chunks.append(current)
                current = sentence

        if current:
            chunks.append(current)

        return chunks if chunks else [text[:max_chars]]
