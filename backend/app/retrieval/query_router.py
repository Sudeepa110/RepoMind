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

        # 1. Evaluate intents
        for intent in intents:
            if intent == QueryIntent.SEMANTIC:
                vector_enabled = True
                keyword_enabled = True
                reasons["SEMANTIC"] = "Engage Vector search for semantic meaning and Keyword search for term matching."

            elif intent == QueryIntent.EXACT_SYMBOL:
                keyword_enabled = True
                vector_enabled = True
                graph_enabled = True
                graph_ops.append("callers")
                reasons["EXACT_SYMBOL"] = "Engage Keyword search for exact identifier match and Graph for symbol relationships."

            elif intent == QueryIntent.CALLERS:
                graph_enabled = True
                graph_ops.append("callers")
                keyword_enabled = True
                vector_enabled = True
                reasons["CALLERS"] = "Engage Graph traversal for incoming call hierarchy and Keyword for symbol anchoring."

            elif intent == QueryIntent.CALLEES:
                graph_enabled = True
                graph_ops.append("callees")
                keyword_enabled = True
                vector_enabled = True
                reasons["CALLEES"] = "Engage Graph traversal for outgoing invocations."

            elif intent == QueryIntent.DEPENDENCIES:
                graph_enabled = True
                graph_ops.append("dependencies")
                keyword_enabled = True
                reasons["DEPENDENCIES"] = "Engage Graph traversal for import and module dependency trees."

            elif intent == QueryIntent.INHERITANCE:
                graph_enabled = True
                graph_ops.append("inheritance")
                keyword_enabled = True
                reasons["INHERITANCE"] = "Engage Graph traversal for class inheritance and interface realization."

            elif intent == QueryIntent.IMPACT_ANALYSIS:
                graph_enabled = True
                graph_ops.append("impact")
                vector_enabled = True
                keyword_enabled = True
                reasons["IMPACT_ANALYSIS"] = "Engage Graph reverse BFS for blast radius and Vector search for affected modules."

            elif intent == QueryIntent.EXECUTION_FLOW:
                graph_enabled = True
                graph_ops.append("callers")
                graph_ops.append("callees")
                vector_enabled = True
                keyword_enabled = True
                reasons["EXECUTION_FLOW"] = "Engage Graph invocation paths and Vector search for step-by-step logic."

            elif intent == QueryIntent.ARCHITECTURE:
                vector_enabled = True
                graph_enabled = True
                graph_ops.append("dependencies")
                keyword_enabled = True
                reasons["ARCHITECTURE"] = "Engage Vector search for high-level concepts and Graph for directory structure."

            elif intent == QueryIntent.CONFIG_OR_DOCS:
                keyword_enabled = True
                vector_enabled = True
                reasons["CONFIG_OR_DOCS"] = "Engage Keyword search for manifest entries and Vector search for doc sections."

            elif intent == QueryIntent.UNKNOWN:
                vector_enabled = True
                keyword_enabled = True
                reasons["UNKNOWN"] = "Default fallback to hybrid Vector and Keyword retrieval."

        # Default fallback if nothing enabled
        if not (vector_enabled or keyword_enabled or graph_enabled):
            vector_enabled = True
            keyword_enabled = True

        # 2. Apply user explicit overrides if provided
        if include_vector is not None:
            vector_enabled = include_vector
            reasons["USER_OVERRIDE_VECTOR"] = f"User explicitly set include_vector={include_vector}"

        if include_graph is not None:
            if not include_graph:
                graph_enabled = False
                reasons["USER_OVERRIDE_GRAPH"] = f"User explicitly set include_graph=False"
            else:
                # Enable graph if user requested it AND there are structural operations,
                # or if graph is the sole requested strategy (graph_only mode)
                is_graph_only = not include_vector
                has_structural_intent = bool(graph_ops) or any(
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
                if has_structural_intent or is_graph_only:
                    graph_enabled = True
                    reasons["USER_OVERRIDE_GRAPH"] = f"User explicitly set include_graph=True"
                else:
                    graph_enabled = False
                    reasons["GRAPH_BYPASSED"] = "Graph traversal omitted for pure non-structural query."

        if include_keyword is not None:
            keyword_enabled = include_keyword
            reasons["USER_OVERRIDE_KEYWORD"] = f"User explicitly set include_keyword={include_keyword}"

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

