"""
Lightweight deterministic query understanding and intent classification service.
Analyzes developer questions to identify structural, semantic, and keyword intents
using regex patterns and heuristics without requiring external LLM API calls.
"""

import re
from typing import List, Dict, Set, Tuple

from backend.app.retrieval.retrieval_models import (
    QueryIntent,
    RetrievalStrategy,
    QueryAnalysisResult,
)

# Common non-symbol words that happen to contain underscores or camelCase
STOP_TERMS: Set[str] = {
    "how_to", "so_called", "built_in", "e_g", "i_e", "end_to_end",
    "git_hub", "open_ai", "pull_request",
}

# Regex pattern for file paths and manifests
FILE_PATH_PATTERN = re.compile(
    r"\b([a-zA-Z0-9_\-\./\\]+\.(?:py|js|ts|tsx|jsx|java|c|cpp|h|hpp|go|md|json|yml|yaml|toml|txt))\b",
    re.IGNORECASE,
)

# Regex pattern for backticked symbols: `foo_bar` or `Class.method`
BACKTICK_PATTERN = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_\.:]*)`")

# Regex pattern for function calls: foo() or obj.bar()
FUNC_CALL_PATTERN = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\)")

# Regex pattern for camelCase / PascalCase identifiers
CAMEL_CASE_PATTERN = re.compile(r"\b([A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+)\b")

# Regex pattern for snake_case identifiers
SNAKE_CASE_PATTERN = re.compile(r"\b([a-z0-9]+(?:_[a-z0-9]+)+)\b")

# Regex pattern for capitalized class or type names (e.g. Flask, Config, Scaffold)
CLASS_IDENTIFIER_PATTERN = re.compile(r"\b([A-Z][a-zA-Z0-9_]+)\b")

COMMON_ENGLISH_WORDS: Set[str] = {
    "What", "Which", "Where", "When", "Who", "How", "Why", "Explain", "Trace",
    "Find", "Show", "Locate", "Generate", "Summarize", "Define", "Does",
    "Can", "Will", "The", "This", "That", "These", "Those", "All", "And",
    "For", "With", "From", "Into", "Over", "Under", "Between", "Through",
    "Important", "Admin", "Directive", "Reveal", "Print", "Not", "Yes", "No",
    "Is", "Are", "Was", "Were", "In", "On", "At", "By", "To", "If", "Solidity",
}


class QueryAnalyzer:
    """
    Classifies user question intents and extracts potential symbol/file targets.
    """

    def analyze(self, query: str) -> QueryAnalysisResult:
        """
        Analyzes developer query and returns classified intents, extracted symbols,
        and recommended retrieval strategies.
        """
        q_clean = query.strip()
        q_lower = q_clean.lower()

        intents: List[QueryIntent] = []
        intent_reasons: Dict[str, str] = {}

        # 1. Extract potential symbols
        symbols = self._extract_symbols(q_clean)

        # 2. Extract potential file paths
        file_paths = self._extract_file_paths(q_clean)

        # 3. Check for Caller queries
        caller_match = re.search(
            r"\b(who|which (functions?|methods?|callers?|symbols?))\s+(calls?|invokes?)|callers?\s+of|where\s+is\s+.*called\b",
            q_lower,
        )
        if caller_match:
            intents.append(QueryIntent.CALLERS)
            intent_reasons[QueryIntent.CALLERS.value] = "Query requests incoming function/method callers."

        # 4. Check for Callee queries
        callee_match = re.search(
            r"\b(what|which (functions?|methods?))\s+(does\s+.*\s+(call|invoke)|is\s+called\s+by)|callees?\s+of|what\s+does\s+.*\s+invoke\b",
            q_lower,
        )
        if callee_match:
            intents.append(QueryIntent.CALLEES)
            intent_reasons[QueryIntent.CALLEES.value] = "Query requests outgoing function/method callees."

        # 5. Check for Dependency queries
        dep_match = re.search(
            r"\b(depend(s|encies)?\s+on|who\s+imports|imports?\s+of|what\s+modules?\s+does|dependents?\s+of)\b",
            q_lower,
        )
        if dep_match:
            intents.append(QueryIntent.DEPENDENCIES)
            intent_reasons[QueryIntent.DEPENDENCIES.value] = "Query requests module imports or component dependencies."

        # 6. Check for Inheritance queries
        inh_match = re.search(
            r"\b(inherits?|subclasses?|superclasses?|base\s+class|classes\s+implementing|implements?\s+(interface)?)\b",
            q_lower,
        )
        if inh_match:
            intents.append(QueryIntent.INHERITANCE)
            intent_reasons[QueryIntent.INHERITANCE.value] = "Query requests class inheritance or interface realization."

        # 7. Check for Impact Analysis queries
        impact_match = re.search(
            r"\b(what\s+(could\s+break|breaks)|impact\s+of\s+(modifying|changing)|blast\s+radius|affected\s+if|change\s+impact)\b",
            q_lower,
        )
        if impact_match:
            intents.append(QueryIntent.IMPACT_ANALYSIS)
            intent_reasons[QueryIntent.IMPACT_ANALYSIS.value] = "Query requests modification blast radius and impact analysis."

        # 8. Check for Execution Flow queries
        flow_match = re.search(
            r"\b(execution\s+flow|call\s+flow|trace\s+(the\s+)?flow|path\s+(from|between)|call\s+sequence|step[- ]by[- ]step\s+flow)\b",
            q_lower,
        )
        if flow_match:
            intents.append(QueryIntent.EXECUTION_FLOW)
            intent_reasons[QueryIntent.EXECUTION_FLOW.value] = "Query requests invocation paths and operation sequencing."

        # 9. Check for Architecture queries
        arch_match = re.search(
            r"\b(architecture|overall\s+structure|how\s+is\s+this\s+(project|repo|repository)\s+structured|high[- ]level\s+overview|components\s+overview)\b",
            q_lower,
        )
        if arch_match:
            intents.append(QueryIntent.ARCHITECTURE)
            intent_reasons[QueryIntent.ARCHITECTURE.value] = "Query requests high-level architecture or directory structure."

        # 10. Check for Config or Documentation queries
        config_match = re.search(
            r"\b(config(uration)?|settings|environment(\s+variables?)?|env\s+vars?|docker|docker-compose|requirements\.txt|package\.json|readme|setup|install(ation)?)\b",
            q_lower,
        )
        if config_match:
            intents.append(QueryIntent.CONFIG_OR_DOCS)
            intent_reasons[QueryIntent.CONFIG_OR_DOCS.value] = "Query requests configuration manifests or documentation."

        # 11. Check for Exact Symbol Lookup
        if symbols and (
            re.search(r"\b(find|where\s+is|show|locate|definition\s+of)\b", q_lower)
            or BACKTICK_PATTERN.search(q_clean)
            or FUNC_CALL_PATTERN.search(q_clean)
        ):
            if QueryIntent.EXACT_SYMBOL not in intents:
                intents.append(QueryIntent.EXACT_SYMBOL)
                intent_reasons[QueryIntent.EXACT_SYMBOL.value] = f"Exact symbols detected: {', '.join(symbols)}"

        # 12. Check for Semantic query (default or explicit)
        semantic_match = re.search(
            r"\b(explain|how\s+does|how\s+to|what\s+is|understand|purpose\s+of|overview\s+of|logic\s+behind)\b",
            q_lower,
        )
        if semantic_match or not intents:
            intents.append(QueryIntent.SEMANTIC)
            intent_reasons[QueryIntent.SEMANTIC.value] = "Query requests semantic concept understanding."

        # Fallback if empty
        if not intents:
            intents.append(QueryIntent.UNKNOWN)
            intent_reasons[QueryIntent.UNKNOWN.value] = "Query intent is ambiguous or unspecified."

        # Determine recommended strategies
        strategies = self._derive_strategies(intents)

        return QueryAnalysisResult(
            original_query=q_clean,
            intents=intents,
            extracted_symbols=symbols,
            extracted_file_paths=file_paths,
            confidence=0.9 if QueryIntent.UNKNOWN not in intents else 0.5,
            recommended_strategies=strategies,
            intent_reasons=intent_reasons,
        )

    def _extract_symbols(self, text: str) -> List[str]:
        """Extracts candidate code symbols from backticks, invocations, and identifier patterns."""
        found: List[str] = []

        # 1. Backticked symbols
        for m in BACKTICK_PATTERN.finditer(text):
            found.append(m.group(1))

        # 2. Function calls foo()
        for m in FUNC_CALL_PATTERN.finditer(text):
            found.append(m.group(1))

        # 3. CamelCase / PascalCase
        for m in CAMEL_CASE_PATTERN.finditer(text):
            found.append(m.group(1))

        # 4. snake_case
        for m in SNAKE_CASE_PATTERN.finditer(text):
            sym = m.group(1)
            if sym not in STOP_TERMS and len(sym) >= 4:
                found.append(sym)

        # 5. Capitalized class/type identifiers (e.g. Flask, Config, Scaffold)
        for m in CLASS_IDENTIFIER_PATTERN.finditer(text):
            sym = m.group(1)
            if sym not in COMMON_ENGLISH_WORDS and len(sym) >= 3:
                found.append(sym)

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for s in found:
            s_clean = s.strip(":().")
            if s_clean and s_clean not in seen:
                seen.add(s_clean)
                deduped.append(s_clean)

        return deduped

    def _extract_file_paths(self, text: str) -> List[str]:
        """Extracts file names and paths mentioned in the query."""
        found = [m.group(1) for m in FILE_PATH_PATTERN.finditer(text)]
        seen = set()
        deduped = []
        for f in found:
            if f not in seen:
                seen.add(f)
                deduped.append(f)
        return deduped

    def _derive_strategies(self, intents: List[QueryIntent]) -> List[RetrievalStrategy]:
        """Maps classified intents to recommended retrieval strategies."""
        strategies: Set[RetrievalStrategy] = set()

        for intent in intents:
            if intent == QueryIntent.SEMANTIC:
                strategies.add(RetrievalStrategy.VECTOR)
                strategies.add(RetrievalStrategy.KEYWORD)
            elif intent == QueryIntent.EXACT_SYMBOL:
                strategies.add(RetrievalStrategy.KEYWORD)
                strategies.add(RetrievalStrategy.VECTOR)
            elif intent in (
                QueryIntent.CALLERS,
                QueryIntent.CALLEES,
                QueryIntent.DEPENDENCIES,
                QueryIntent.INHERITANCE,
            ):
                strategies.add(RetrievalStrategy.GRAPH)
                strategies.add(RetrievalStrategy.KEYWORD)
            elif intent in (QueryIntent.IMPACT_ANALYSIS, QueryIntent.EXECUTION_FLOW):
                strategies.add(RetrievalStrategy.GRAPH)
                strategies.add(RetrievalStrategy.VECTOR)
                strategies.add(RetrievalStrategy.KEYWORD)
            elif intent == QueryIntent.ARCHITECTURE:
                strategies.add(RetrievalStrategy.VECTOR)
                strategies.add(RetrievalStrategy.GRAPH)
                strategies.add(RetrievalStrategy.KEYWORD)
            elif intent == QueryIntent.CONFIG_OR_DOCS:
                strategies.add(RetrievalStrategy.KEYWORD)
                strategies.add(RetrievalStrategy.VECTOR)
            elif intent == QueryIntent.UNKNOWN:
                strategies.add(RetrievalStrategy.VECTOR)
                strategies.add(RetrievalStrategy.KEYWORD)

        if len(strategies) > 1:
            strategies.add(RetrievalStrategy.HYBRID)

        return sorted(list(strategies), key=lambda s: s.value)


# Global singleton instance
query_analyzer = QueryAnalyzer()

