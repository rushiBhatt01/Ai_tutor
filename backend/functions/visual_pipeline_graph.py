"""LangGraph orchestration for planning, rendering, and collecting visual scenes.

The graph keeps scene artifacts as its state contract. Renderer workers own the
bounded per-scene retry/fallback loop; this graph owns stage ordering and the
terminal manifest completeness gate before composition.
"""

from typing import Any, TypedDict
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from functions.storyboard_schema import Storyboard
from functions.visual_artifacts import load_visual_manifest


class VisualPipelineState(TypedDict, total=False):
    run_dir: str
    storyboard_json: str
    storyboard: Any
    visual_specs: list[dict]
    video_paths: list[str]
    manifest_path: str
    status: str


def plan_visuals(state: VisualPipelineState) -> dict:
    storyboard = state.get("storyboard")
    if storyboard is None and state.get("storyboard_json"):
        storyboard = Storyboard.model_validate_json(state["storyboard_json"])
    if storyboard is not None:
        from functions.visual_routing import route_storyboard
        from functions.langgraph_pipeline import _validated_visual_specs

        route_storyboard(storyboard)
        specs = _validated_visual_specs(storyboard)
        expected = list(range(len(storyboard.scenes)))
        if [int(spec["scene_id"]) for spec in specs] != expected:
            raise ValueError("Visual graph requires contiguous ordered scene specs")
        return {"storyboard": storyboard, "visual_specs": specs}
    return {"visual_specs": []}


def dispatch_visuals(state: VisualPipelineState) -> dict:
    from functions.manim_renderer import render_all_visual_scenes

    paths = render_all_visual_scenes(
        state["run_dir"], storyboard=state.get("storyboard"),
        visual_specs=state.get("visual_specs", []),
    )
    return {"video_paths": paths}


def collect_visual_manifest(state: VisualPipelineState) -> dict:
    run_dir = state["run_dir"]
    manifest = load_visual_manifest(run_dir)
    expected_specs = state.get("visual_specs", [])
    if manifest is None:
        if expected_specs:
            raise RuntimeError("Visual renderer did not write a manifest")
        return {"status": "complete", "manifest_path": ""}
    expected_ids = [int(spec["scene_id"]) for spec in expected_specs]
    video_ids = [
        int(Path(path).stem.removeprefix("seg_"))
        for path in state.get("video_paths", [])
        if Path(path).stem.startswith("seg_") and Path(path).stem[4:].isdigit()
    ]
    if expected_specs and video_ids != expected_ids:
        raise RuntimeError("Visual dispatch paths do not match the planned scene IDs")
    actual_ids = [scene.scene_id for scene in manifest.scenes]
    if expected_specs and actual_ids != expected_ids:
        raise RuntimeError("Visual manifest scene ordering does not match the plan")
    incomplete = [scene for scene in manifest.scenes if scene.status != "accepted"]
    if incomplete:
        failed_ids = [scene.artifact_id for scene in incomplete]
        raise RuntimeError(f"Visual graph cannot complete with unaccepted scenes: {failed_ids}")
    return {
        "status": "complete",
        "manifest_path": str(run_dir) + "/artifacts/visual_manifest.json",
    }


def build_visual_graph():
    graph = StateGraph(VisualPipelineState)
    graph.add_node("plan_visuals", plan_visuals)
    graph.add_node("dispatch_visuals", dispatch_visuals)
    graph.add_node("collect_manifest", collect_visual_manifest)
    graph.add_edge(START, "plan_visuals")
    graph.add_edge("plan_visuals", "dispatch_visuals")
    graph.add_edge("dispatch_visuals", "collect_manifest")
    graph.add_edge("collect_manifest", END)
    return graph.compile()


def run_visual_pipeline(run_dir: str, storyboard=None) -> dict:
    """Execute the visual graph and return its ordered terminal artifact state."""
    state = {"run_dir": run_dir}
    if storyboard is not None:
        state["storyboard"] = storyboard
        state["storyboard_json"] = storyboard.model_dump_json()
    return build_visual_graph().invoke(state)
