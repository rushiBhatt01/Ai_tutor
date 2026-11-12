from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from functions.visual_routing import route_scene, route_storyboard


def scene(**changes):
    values = dict(
        visual_type="slide",
        key_concept="An introductory lesson",
        narration="This scene explains a general concept in a clear way.",
        visual_query="An introductory concept",
        on_screen_text="Introduction",
        learning_objective="",
        manim_spec=None,
        visual_rationale=None,
    )
    values.update(changes)
    return SimpleNamespace(**values)


def test_routes_algorithm_walkthrough_to_supported_manim():
    item = scene(
        visual_type="manim",
        key_concept="Breadth-first search traversal",
        narration="Breadth-first search visits neighbors level by level.",
        manim_spec={"topic_type": "bfs", "steps": ["A", "B"]},
    )
    route = route_scene(item, {"manim": True, "web_image": True})
    assert route.strategy == "manim"
    assert "bfs" in route.rationale


def test_routes_real_world_subject_to_web_image():
    item = scene(key_concept="An introductory lesson",
                 learning_objective="Explain photosynthesis in plants",
                 narration="Plants use sunlight to make food.")
    route = route_scene(item, {"web_image": True})
    assert route.strategy == "web_image"
    assert "real-world" in route.rationale


def test_technical_definition_stays_pillow_without_algorithmic_benefit():
    item = scene(
        visual_type="manim",
        key_concept="Definition of an API",
        narration="An API is a contract that lets programs communicate with one another.",
        manim_spec={"topic_type": "bfs", "steps": ["A", "B"]},
    )
    route = route_scene(item, {"manim": True, "web_image": True})
    assert route.strategy == "pillow"
    assert "explanatory" in route.rationale


def test_unsupported_algorithm_and_malformed_strategy_fail_to_pillow():
    unsupported = scene(visual_type="manim", key_concept="Sorting algorithm", narration="A sorting algorithm orders values.",
                       manim_spec={"topic_type": "quicksort"})
    malformed = scene(visual_type="animated_gif")
    assert route_scene(unsupported).strategy == "pillow"
    assert "Unsupported animation" in route_scene(unsupported).rationale
    malformed_route = route_scene(malformed)
    assert malformed_route.strategy == "pillow"
    assert "Unrecognized requested strategy" in malformed_route.rationale


def test_disabled_capabilities_fall_back_and_rationale_is_persisted_per_scene():
    scenes = [scene(key_concept="A planet", narration="The planet orbits its star."),
              scene(visual_type="manim", key_concept="Binary search", narration="Binary search halves a sorted range.",
                    manim_spec={"topic_type": "binary_search"})]
    storyboard = SimpleNamespace(scenes=scenes)
    route_storyboard(storyboard, {"web_image": False, "manim": False})
    assert [item.visual_type for item in scenes] == ["pillow", "pillow"]
    assert all(item.visual_rationale for item in scenes)


def test_router_exception_degrades_only_affected_scene(monkeypatch):
    import functions.visual_routing as routing

    scenes = [scene(), scene()]
    original = routing.route_scene
    calls = iter([RuntimeError("router failure"), original(scenes[1], {"web_image": False})])

    def sometimes_fails(*args, **kwargs):
        result = next(calls)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(routing, "route_scene", sometimes_fails)
    routing.route_storyboard(SimpleNamespace(scenes=scenes), {"web_image": False})
    assert all(item.visual_type == "pillow" for item in scenes)
    assert "failed" in scenes[0].visual_rationale
    assert scenes[1].visual_rationale


def test_langgraph_visual_plan_node_returns_routed_storyboard_and_plan():
    import json
    from functions.langgraph_pipeline import plan_visuals

    storyboard = {
        "title": "Photosynthesis",
        "scenes": [{
            "scene_id": 0,
            "key_concept": "Plants convert light to chemical energy",
            "learning_objective": "Explain photosynthesis",
            "narration": "Plants use sunlight to make sugars from water and carbon dioxide.",
            "visual_query": "A plant leaf using sunlight",
            "on_screen_text": "Photosynthesis",
            "estimated_seconds": 8,
        }],
    }
    result = plan_visuals({"storyboard_json": json.dumps(storyboard)})
    routed = json.loads(result["storyboard_json"])
    assert result["visual_plan"] == [{
        "scene_id": 0,
        "strategy": "web_image",
        "rationale": routed["scenes"][0]["visual_rationale"],
    }]
    assert result["visual_specs"] == [{
        "schema_version": 1,
        "scene_id": 0,
        "topic": "Plants convert light to chemical energy",
        "visual_goal": "Explain photosynthesis",
        "visual_type": "web_image",
        "duration_seconds": 8.0,
        "width": 1280,
        "height": 720,
        "fps": 25,
        "input_data": {"query": "A plant leaf using sunlight"},
        "trace": [],
        "must_show": ["Plants convert light to chemical energy"],
        "must_not_show": [],
    }]
    assert routed["scenes"][0]["visual_type"] == "web_image"


def test_script_pipeline_preserves_default_return_and_can_return_graph_state(monkeypatch):
    import json
    import functions.langgraph_pipeline as pipeline

    storyboard_json = json.dumps({
        "title": "General lesson",
        "scenes": [{
            "scene_id": 0,
            "key_concept": "An introductory lesson",
            "narration": "This scene explains a general concept in a clear way.",
            "visual_query": "An introductory concept",
            "on_screen_text": "Introduction",
            "estimated_seconds": 8,
            "visual_type": "pillow",
            "visual_rationale": "A readable Pillow slide is the best fit for this scene.",
        }],
    })
    state = {
        "script_text": "lesson script", "storyboard_json": storyboard_json,
        "visual_plan": [{"scene_id": 0, "strategy": "pillow", "rationale": "readable slide"}],
        "is_technical": False, "topic_type": "general", "manim_scenes": [],
    }

    class FakeGraph:
        def invoke(self, initial_state):
            assert initial_state["visual_plan"] == []
            return state

    monkeypatch.setattr(pipeline, "_get_graph", lambda: FakeGraph())
    default = pipeline.run_script_pipeline("topic", "basic", "10", "medium", "low")
    extended = pipeline.run_script_pipeline(
        "topic", "basic", "10", "medium", "low", return_state=True,
    )
    assert len(default) == 2
    assert len(extended) == 3
    assert extended[2]["visual_plan"] == state["visual_plan"]
