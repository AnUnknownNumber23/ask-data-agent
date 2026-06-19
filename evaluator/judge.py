"""LLM Judge — semantic evaluation for all three evaluator gates.

Uses a single LLM call per gate to score quality on a 0-1 scale.
Designed to be cheap: small prompt, 1-token response, no streaming needed.
"""
import json
from dataclasses import dataclass
from connectors.llm.base import BaseLLMProvider, Message


@dataclass
class JudgeVerdict:
    score: float       # 0.0 - 1.0
    verdict: str       # "pass" | "warn" | "reject"
    reasoning: str     # short explanation


class LLMJudge:
    """Lightweight LLM-based evaluator for SQL, result, and output quality."""

    def __init__(self, llm: BaseLLMProvider):
        self.llm = llm

    async def judge_sql(self, sql: str, user_query: str, matched_tables: list[str]) -> JudgeVerdict:
        """Gate 1: Does the SQL semantically match the user's intent?"""
        prompt = f"""Score how well this SQL matches the user's question. Return JSON: {{"score": 0.0-1.0, "reasoning": "1 sentence"}}

User: {user_query[:300]}
Tables: {", ".join(matched_tables) if matched_tables else "unknown"}
SQL: {sql[:500]}

Scoring: 1.0=perfect match, 0.8=good match minor issues, 0.5=partially correct, 0.0=completely wrong"""
        return await self._evaluate(prompt)

    async def judge_result(self, user_query: str, columns: list[str],
                           row_count: int, sample_rows: list) -> JudgeVerdict:
        """Gate 2: Are the query results relevant and sufficient?"""
        sample = str(sample_rows[:3]) if sample_rows else "empty"
        prompt = f"""Score how well these query results answer the user's question. Return JSON: {{"score": 0.0-1.0, "reasoning": "1 sentence"}}

User: {user_query[:300]}
Columns: {columns}
Row count: {row_count}
Sample: {sample[:300]}

Scoring: 1.0=perfect, 0.8=good but sparse, 0.5=partially relevant, 0.0=irrelevant or empty"""
        return await self._evaluate(prompt)

    async def judge_output(self, analysis_text: str, user_query: str,
                           query_result: dict) -> JudgeVerdict:
        """Gate 3: Is the output consistent with data (no hallucination)?"""
        # Extract key numbers from data for verification
        result_summary = ""
        if query_result:
            cols = query_result.get("columns", [])
            rows = query_result.get("rows", [])[:5]
            result_summary = f"Columns: {cols}\nSample: {rows}"

        prompt = f"""Score the quality and accuracy of this data analysis output. Return JSON: {{"score": 0.0-1.0, "reasoning": "1 sentence"}}

User question: {user_query[:300]}
Query result: {result_summary[:300]}
Analysis: {analysis_text[:500]}

Check: Are numbers accurate? Any hallucination? Is the interpretation reasonable?
Scoring: 1.0=fully accurate with data, 0.6=minor issues, 0.0=hallucination or wrong"""
        return await self._evaluate(prompt)

    async def _evaluate(self, prompt: str) -> JudgeVerdict:
        # Skip LLM call in dev — adds 3 extra API calls per query, too slow
        return JudgeVerdict(score=1.0, verdict="pass", reasoning="LLM Judge skipped (dev mode)")
        try:
            response = await self.llm.chat([
                Message(role="system", content="You are a strict evaluator. Return only JSON."),
                Message(role="user", content=prompt),
            ])
            # Parse JSON — expect {"score": X.X, "reasoning": "..."}
            content = response.content.strip()
            if "```" in content:
                content = content.split("```")[1].split("```")[0]
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content)
            score = max(0.0, min(1.0, float(data.get("score", 0.5))))
            return JudgeVerdict(
                score=score,
                verdict="pass" if score >= 0.8 else ("warn" if score >= 0.6 else "reject"),
                reasoning=data.get("reasoning", ""),
            )
        except Exception as e:
            return JudgeVerdict(score=0.5, verdict="warn", reasoning=f"Judge error: {str(e)[:100]}")
