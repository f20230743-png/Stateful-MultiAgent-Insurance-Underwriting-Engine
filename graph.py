from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from typing import Optional

from nodes import (
    classification_node,
    decision_node,
    gateway_node,
    human_in_the_loop_node,
    ingest_node,
    log_node,
    parallel_retrieval_node,
    partial_cases_node,
    trigger_communication_node,
)
from state import InsuranceClaimStates


def _route_after_gateway(state: InsuranceClaimStates) -> str:
    if state.get("gateway_route") == "human_pipeline_stop":
        return "log_node"
    return "parallel_retrieval_node"


def _route_after_classification(state: InsuranceClaimStates) -> str:
    if state.get("workflow_route") == "human_verification_need_more_info":
        return "human_in_the_loop_node"
    return "decision_node"


def _route_after_decision(state: InsuranceClaimStates) -> str:
    if state.get("final_claim_decision", {}).get("status") == "partial":
        return "partial_cases_node"
    return "human_in_the_loop_node"


def _route_after_human_review(state: InsuranceClaimStates) -> str:
    if state.get("workflow_route") == "trigger_communication":
        return "trigger_communication_node"
    return "log_node"


def _human_review_approved(state: InsuranceClaimStates) -> InsuranceClaimStates:
    return human_in_the_loop_node(state, human_approved=True)


def build_claim_graph():
    """
    Build and compile LangGraph claim pipeline with MemorySaver checkpointing.
    """
    builder = StateGraph(InsuranceClaimStates)

    builder.add_node("ingest_node", ingest_node)
    builder.add_node("gateway_node", gateway_node)
    builder.add_node("parallel_retrieval_node", parallel_retrieval_node)
    builder.add_node("classification_node", classification_node)
    builder.add_node("decision_node", decision_node)
    builder.add_node("partial_cases_node", partial_cases_node)
    builder.add_node("human_in_the_loop_node", _human_review_approved)
    builder.add_node("trigger_communication_node", trigger_communication_node)
    builder.add_node("log_node", log_node)

    builder.add_edge(START, "ingest_node")
    builder.add_edge("ingest_node", "gateway_node")
    builder.add_conditional_edges("gateway_node", _route_after_gateway)
    builder.add_edge("parallel_retrieval_node", "classification_node")
    builder.add_conditional_edges("classification_node", _route_after_classification)
    builder.add_conditional_edges("decision_node", _route_after_decision)
    builder.add_edge("partial_cases_node", "human_in_the_loop_node")
    builder.add_conditional_edges("human_in_the_loop_node", _route_after_human_review)
    builder.add_edge("trigger_communication_node", "log_node")
    builder.add_edge("log_node", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


def run_claim_graph(
    initial_state: Optional[InsuranceClaimStates] = None,
    thread_id: str = "insurance-claim-thread",
) -> InsuranceClaimStates:
    """
    Invoke compiled LangGraph with state sync and MemorySaver checkpoints.
    """
    claim_graph = build_claim_graph()
    return claim_graph.invoke(initial_state or {}, config={"configurable": {"thread_id": thread_id}})


def run_dummy_claim_graph(thread_id: str = "insurance-claim-dummy-thread") -> InsuranceClaimStates:
    return run_claim_graph({}, thread_id=thread_id)
