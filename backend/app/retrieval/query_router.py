"""
Query Routing Engine.
Maps classified query intents into an optimized execution plan across Vector RAG,
GraphRAG, and Keyword Search, with per-engine parameter limits and user overrides.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from backend.app.retrieval.retrieval_models import (
    QueryIntent,
    RetrievalStrategy,
    QueryAnalysisResult,
)


class RoutingPlan(BaseModel):
    """Execution plan detailing which engines to run and with what parameters."""
    strategies: List[RetrievalStrategy]
    vector_enabled: bool = True
    vector_top_k: int = 5
    keyword_enabled: bool = True
    keyword_top_k: int = 5
    graph_enabled: bool = False
    graph_operations: List[str] = Field(default_factory=list)  # callers, callees, dependencies, impact, hierarchy
    target_symbols: List[str] = Field(default_factory=list)
    reasons: Dict[str, str] = Field(default_factory=dict)


class QueryRouter:
    """
    Directs queries to appropriate retrieval engines based on intent classification.
    """

    def route(
        self,
        analysis: QueryAnalysisResult,
        top_k: int = 10,
        include_vector: Optional[bool] = None,
        include_graph: Optional[bool] = None,
        include_keyword: Optional[bool] = None,
    ) -> RoutingPlan:
        """
        Builds an optimized routing plan from query analysis and user overrides.
        """
        intents = analysis.intents
        symbols = analysis.extracted_symbols

        vector_enabled = False
        keyword_enabled = False
        graph_enabled = False
        graph_ops: List[str] = []
        reasons: Dict[str, str] = {}

        # 1. Determine if this is a strict single-strategy override
        is_vector_only = include_vector is True and include_graph is False and include_keyword is False
        is_keyword_only = include_keyword is True and include_vector is False and include_graph is False
        is_graph_only = include_graph is True and include_vector is False and include_keyword is False

        if is_vector_only:
            vector_enabled = True
            reasons["USER_OVERRIDE_VECTOR"] = "User explicitly selected vector-only retrieval."
        elif is_keyword_only:
            keyword_enabled = True
            reasons["USER_OVERRIDE_KEYWORD"] = "User explicitly selected keyword-only retrieval."
        elif is_graph_only:
            graph_enabled = True
            # Determine appropriate graph operations from intents
            for intent in intents:
                if intent == QueryIntent.CALLERS:
                    graph_ops.append("callers")
                elif intent == QueryIntent.CALLEES:
                    graph_ops.append("callees")
                elif intent == QueryIntent.DEPENDENCIES:
                    graph_ops.append("dependencies")
                elif intent == QueryIntent.INHERITANCE:
                    graph_ops.append("inheritance")
                elif intent == QueryIntent.IMPACT_ANALYSIS:
                    graph_ops.append("impact")
                elif intent == QueryIntent.EXECUTION_FLOW:
                    graph_ops.extend(["callers", "callees"])
            if not graph_ops:
                graph_ops.append("callers")
            reasons["USER_OVERRIDE_GRAPH"] = "User explicitly selected graph-only retrieval."
        else:
            # 2. Query-Adaptive Retrieval Routing
            has_structural = any(
                i in intents
                for i in (
                    QueryIntent.CALLERS,
                    QueryIntent.CALLEES,
                    QueryIntent.DEPENDENCIES,
                    QueryIntent.INHERITANCE,
                    QueryIntent.IMPACT_ANALYSIS,
                    QueryIntent.EXECUTION_FLOW,
                    QueryIntent.ARCHITECTURE,
                )
            )
            has_exact_symbol = QueryIntent.EXACT_SYMBOL in intents
            has_semantic = QueryIntent.SEMANTIC in intents

            # A. Caller / Callee queries -> Prioritize graph traversal + keyword for chunk retrieval
            if QueryIntent.CALLERS in intents or QueryIntent.CALLEES in intents:
                graph_enabled = True
                if QueryIntent.CALLERS in intents:
                    graph_ops.append("callers")
                if QueryIntent.CALLEES in intents:
                    graph_ops.append("callees")
                keyword_enabled = True
                vector_enabled = False  # Avoid semantic subject swamping
                reasons["ROUTING_STRUCTURAL_CALLS"] = "Prioritize graph traversal for invocation hierarchy and keyword for symbol chunks."

            # B. Inheritance queries -> Prioritize graph traversal + keyword for class chunks
            elif QueryIntent.INHERITANCE in intents:
                graph_enabled = True
                graph_ops.append("inheritance")
                keyword_enabled = True
                vector_enabled = False
                reasons["ROUTING_INHERITANCE"] = "Prioritize graph traversal for class inheritance and interface realization."

            # C. Dependency queries -> Prioritize graph relationships and keyword evidence
            elif QueryIntent.DEPENDENCIES in intents:
                graph_enabled = True
                graph_ops.append("dependencies")
                keyword_enabled = True
                vector_enabled = False
                reasons["ROUTING_DEPENDENCIES"] = "Prioritize graph relationships and keyword evidence for imports and dependencies."

            # D. Architecture queries -> Combine semantic and structural evidence
            elif QueryIntent.ARCHITECTURE in intents:
                vector_enabled = True
                graph_enabled = True
                graph_ops.append("dependencies")
                keyword_enabled = True
                reasons["ROUTING_ARCHITECTURE"] = "Combine semantic and structural evidence for repository architecture."

            # E. Impact Analysis & Execution Flow -> Hybrid retrieval combining all streams
            elif QueryIntent.IMPACT_ANALYSIS in intents or QueryIntent.EXECUTION_FLOW in intents:
                graph_enabled = True
                if QueryIntent.IMPACT_ANALYSIS in intents:
                    graph_ops.append("impact")
                if QueryIntent.EXECUTION_FLOW in intents:
                    graph_ops.extend(["callers", "callees"])
                vector_enabled = True
                keyword_enabled = True
                reasons["ROUTING_FLOW_IMPACT"] = "Engage full hybrid retrieval across vector, keyword, and graph for flow/impact analysis."

            # F. Exact symbol lookup -> Prioritize keyword and symbol node retrieval (no caller traversal)
            elif has_exact_symbol:
                keyword_enabled = True
                graph_enabled = True  # Enable node lookup without traversing callers
                vector_enabled = False  # Prioritize exact symbol and avoid semantic drift
                reasons["ROUTING_EXACT_SYMBOL"] = "Prioritize keyword and symbol retrieval for exact identifier match."

            # G. Conceptual questions -> Prioritize vector retrieval
            elif has_semantic and not has_structural and not has_exact_symbol:
                vector_enabled = True
                keyword_enabled = False  # Avoid irrelevant stop-word noise
                graph_enabled = False  # Avoid unnecessary graph traversal
                reasons["ROUTING_CONCEPTUAL"] = "Prioritize vector retrieval for conceptual and semantic inquiries."

            # H. Mixed / Config / Unknown fallback
            else:
                vector_enabled = True
                keyword_enabled = True
                if has_structural:
                    graph_enabled = True
                reasons["ROUTING_HYBRID_FALLBACK"] = "Engage hybrid retrieval for multi-intent or ambiguous query."

            # Apply explicit overrides if specified by caller
            if include_vector is not None:
                vector_enabled = include_vector
                reasons["USER_OVERRIDE_VECTOR"] = f"User explicitly set include_vector={include_vector}"
            if include_keyword is not None:
                keyword_enabled = include_keyword
                reasons["USER_OVERRIDE_KEYWORD"] = f"User explicitly set include_keyword={include_keyword}"
            if include_graph is not None:
                if not include_graph:
                    graph_enabled = False
                    reasons["USER_OVERRIDE_GRAPH"] = "User explicitly set include_graph=False"
                else:
                    if has_structural or not vector_enabled:
                        graph_enabled = True
                        reasons["USER_OVERRIDE_GRAPH"] = "User explicitly set include_graph=True"
                graph_enabled = False

        # 3. Compile active strategies list
        strategies: List[RetrievalStrategy] = []
        if vector_enabled:
            strategies.append(RetrievalStrategy.VECTOR)
        if keyword_enabled:
            strategies.append(RetrievalStrategy.KEYWORD)
        if graph_enabled:
            strategies.append(RetrievalStrategy.GRAPH)
        if len(strategies) > 1:
            strategies.append(RetrievalStrategy.HYBRID)

        return RoutingPlan(
            strategies=strategies,
            vector_enabled=vector_enabled,
            vector_top_k=top_k,
            keyword_enabled=keyword_enabled,
            keyword_top_k=top_k,
            graph_enabled=graph_enabled,
            graph_operations=list(set(graph_ops)),
            target_symbols=symbols,
            reasons=reasons,
        )


# Global singleton instance
query_router = QueryRouter()

