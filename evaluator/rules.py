"""Rule engine for deterministic SQL safety and quality checks. Zero LLM dependency."""
import re
from dataclasses import dataclass, field
from enum import Enum


class Verdict(Enum):
    PASS = "pass"
    WARN = "warn"
    REJECT = "reject"


@dataclass
class RuleResult:
    verdict: Verdict
    checks: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


FORBIDDEN_KEYWORDS = [
    "DROP", "DELETE", "INSERT", "UPDATE", "TRUNCATE", "ALTER",
    "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
]

SUSPICIOUS_PATTERNS = [
    (r"'\s*OR\s+'1'\s*=\s*'1", "SQL injection: OR 1=1"),
    (r"'\s*OR\s+1\s*=\s*1\s*--", "SQL injection: OR 1=1 --"),
    (r";\s*DROP\s+TABLE", "SQL injection: DROP TABLE"),
    (r"UNION\s+SELECT", "UNION SELECT (may be suspicious)"),
]


class SQLEvaluator:
    """Gate 1 rule engine: deterministic SQL safety and quality checks."""

    def __init__(self, max_limit: int = 10000):
        self.max_limit = max_limit  # must align with reason.j2 LIMIT value

    def check(self, sql: str) -> RuleResult:
        sql_upper = sql.upper().strip()
        errors: list[str] = []
        warnings: list[str] = []
        checks: dict[str, bool] = {}

        # 1. Must be SELECT (or CTE: WITH ... SELECT)
        is_select = sql_upper.startswith("SELECT")
        is_cte = sql_upper.startswith("WITH") and "SELECT" in sql_upper
        checks["is_select"] = is_select or is_cte
        if not checks["is_select"]:
            errors.append("SQL must start with SELECT or WITH (CTE)")

        # 2. Check forbidden keywords
        found_forbidden = [kw for kw in FORBIDDEN_KEYWORDS if re.search(rf"\b{kw}\b", sql_upper)]
        checks["no_dangerous_op"] = len(found_forbidden) == 0
        if found_forbidden:
            errors.append(f"Forbidden keywords found: {', '.join(found_forbidden)}")

        # 3. Must have LIMIT
        checks["has_limit"] = bool(re.search(r"\bLIMIT\s+\d+", sql_upper))
        if not checks["has_limit"]:
            warnings.append("No LIMIT clause — query may return too many rows")

        # 4. Check LIMIT value
        limit_match = re.search(r"\bLIMIT\s+(\d+)", sql_upper)
        if limit_match:
            limit_val = int(limit_match.group(1))
            checks["limit_reasonable"] = limit_val <= self.max_limit
            if not checks["limit_reasonable"]:
                errors.append(f"LIMIT {limit_val} exceeds max allowed ({self.max_limit})")

        # 5. Suspicious patterns
        for pattern, desc in SUSPICIOUS_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                warnings.append(desc)

        if errors:
            return RuleResult(verdict=Verdict.REJECT, checks=checks, errors=errors, warnings=warnings)
        if warnings:
            return RuleResult(verdict=Verdict.WARN, checks=checks, warnings=warnings)
        return RuleResult(verdict=Verdict.PASS, checks=checks)
