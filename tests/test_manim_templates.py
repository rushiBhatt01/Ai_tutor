from pathlib import Path
import ast
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from functions.manim_renderer import build_manim_trace_events, generate_manim_python_code


SEARCH_VALUES = [2, 4, 6, 8, 10, 12, 14]
GRAPH = {
    "nodes": ["A", "B", "C", "D", "E"],
    "edges": [["A", "B"], ["A", "C"], ["B", "D"], ["B", "E"]],
    "start": "A",
}


def test_binary_search_template_uses_midpoint_bounds_and_elimination_trace():
    trace = build_manim_trace_events("binary_search", [], 8,
                                    {"values": SEARCH_VALUES, "target": 12})
    code = generate_manim_python_code("binary_search", "Binary search", [], 8,
                                      {"values": SEARCH_VALUES, "target": 12})
    assert [event["state"]["index"] for event in trace] == [3, 5]
    assert [event["animation_frame"] for event in trace] == sorted(event["animation_frame"] for event in trace)
    assert 'state["low"]' in code and 'state["high"]' in code
    assert "next_low" in code and "box.set_fill(GRAY" in code


def test_linear_search_template_is_sequential_and_stops_at_first_duplicate():
    trace = build_manim_trace_events("linear_search", [], 8,
                                    {"values": [2, 4, 4, 8], "target": 4})
    code = generate_manim_python_code("linear_search", "Linear search", [], 8,
                                      {"values": [2, 4, 4, 8], "target": 4})
    assert [event["state"]["index"] for event in trace] == [0, 1]
    assert trace[-1]["action"] == "found"
    assert "IS_BINARY = False" in code
    assert "Compare index" in code


def test_bfs_template_replays_queue_operations_and_level_information():
    trace = build_manim_trace_events("bfs", [], 8, GRAPH)
    code = generate_manim_python_code("bfs", "Breadth first search", [], 8, GRAPH)
    visits = [event["state"]["node"] for event in trace if event["action"] == "visit"]
    assert visits == ["A", "B", "C", "D", "E"]
    assert any(event["action"] == "enqueue" for event in trace)
    assert all("level" in event["state"] for event in trace)
    assert '"QUEUE"' in code or "QUEUE:" in code
    assert "Level {state['level']}" in code


def test_dfs_template_replays_stack_operations_and_backtracking():
    trace = build_manim_trace_events("dfs", [], 10, GRAPH)
    code = generate_manim_python_code("dfs", "Depth first search", [], 10, GRAPH)
    visits = [event["state"]["node"] for event in trace if event["action"] == "visit"]
    assert visits == ["A", "B", "D", "E", "C"]
    assert any(event["action"] == "push" for event in trace)
    assert any(event["action"] == "backtrack" for event in trace)
    assert "Backtrack" in code and "STACK" in code


def test_renderer_rejects_unsupported_algorithms_and_binary_search_unsorted_values():
    with pytest.raises(ValueError, match="Unsupported Manim algorithm"):
        generate_manim_python_code("quicksort", "Quick sort", [], 5)
    with pytest.raises(ValueError, match="sorted"):
        generate_manim_python_code("binary_search", "Binary search", [], 5,
                                   {"values": [3, 1, 2], "target": 1})


def test_generated_python_keeps_scene_text_as_json_data():
    title = 'Quote: "__TRACE__"'
    code = generate_manim_python_code("linear_search", title, [], 5,
                                      {"values": [1], "target": 1})
    assert f"TITLE = {json.dumps(title)}" in code


@pytest.mark.parametrize("kind,params", [
    ("binary_search", {"values": SEARCH_VALUES, "target": 12}),
    ("linear_search", {"values": [2, 4], "target": 4}),
    ("bfs", GRAPH),
    ("dfs", GRAPH),
])
def test_each_trusted_template_generates_valid_python(kind, params):
    code = generate_manim_python_code(kind, "Trace replay", [], 7, params)
    ast.parse(code)
