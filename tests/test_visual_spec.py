"""VIS-02 deterministic trace and VisualSpec validation fixtures."""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from functions.visual_spec import VisualSpec, validate_visual_spec, trace_search, trace_traversal


def spec(**changes):
    data = dict(scene_id=0, topic="Search", visual_goal="Find a value",
                visual_type="manim", duration_seconds=4, width=1280,
                height=720, fps=25)
    data.update(changes)
    return VisualSpec(**data)


def test_spec_validates_and_roundtrips_explicit_visual_contract():
    value = spec(input_data={"values": [2, 4, 6], "target": 4},
                 must_show=["midpoint"], must_not_show=["unsorted input"])
    assert VisualSpec.model_validate_json(value.model_dump_json()) == value


@pytest.mark.parametrize("changes", [
    {"scene_id": -1}, {"duration_seconds": 0}, {"fps": 61},
    {"width": 3841}, {"visual_type": "unknown"},
    {"must_show": ["x"], "must_not_show": ["x"]},
    {"trace": [{"step": 1, "action": "visit", "state": {}}]},
])
def test_spec_rejects_invalid_ranges_or_contradictory_constraints(changes):
    with pytest.raises(ValidationError):
        spec(**changes)


def test_spec_repairs_invalid_media_settings_once_without_changing_goals():
    data = spec(must_show=["target node"]).model_dump()
    data.update(width=9000, height=9000, fps=120, duration_seconds=900)
    repaired, did_repair = validate_visual_spec(data)
    assert did_repair is True
    assert (repaired.width, repaired.height, repaired.fps) == (1280, 720, 25)
    assert repaired.duration_seconds == 600
    assert repaired.must_show == ["target node"]


def test_spec_does_not_repair_contradictory_requirements():
    data = spec().model_dump()
    data.update(must_show=["target node"], must_not_show=["target node"])
    with pytest.raises(ValidationError):
        validate_visual_spec(data)


@pytest.mark.parametrize("values,target,expected", [
    ([], 3, []), ([7], 7, [0]), ([1, 2, 2, 4], 2, [1]),
    ([1, 3, 5, 7, 9, 11, 13], 11, [3, 5]), ([1, 2, 3], 9, [1, 2]),
])
def test_binary_trace_is_deterministic_and_terminates(values, target, expected):
    trace = trace_search(values, target, binary=True)
    assert [event.state["index"] for event in trace] == expected
    assert trace == trace_search(values, target, binary=True)
    assert [event.step for event in trace] == list(range(len(trace)))


def test_binary_search_rejects_unsorted_inputs():
    with pytest.raises(ValueError, match="sorted"):
        trace_search([3, 1, 2], 1, binary=True)


def test_linear_trace_is_sequential_and_stops_on_first_duplicate():
    trace = trace_search([2, 4, 4, 8], 4)
    assert [event.state["index"] for event in trace] == [0, 1]
    assert trace[-1].action == "found"


@pytest.mark.parametrize("breadth,expected", [
    (True, ["A", "B", "C", "D", "E"]),
    (False, ["A", "B", "D", "E", "C"]),
])
def test_graph_traversal_order_cycles_and_disconnected_nodes(breadth, expected):
    trace = trace_traversal(["A", "B", "C", "D", "E", "Z"],
                            [("A", "B"), ("A", "C"), ("B", "D"),
                             ("B", "E"), ("D", "A")], "A",
                            breadth_first=breadth)
    assert [event.state["node"] for event in trace if event.action == "visit"] == expected
    assert [event.step for event in trace] == list(range(len(trace)))
    assert trace == trace_traversal(["A", "B", "C", "D", "E", "Z"],
                                    [("A", "B"), ("A", "C"), ("B", "D"),
                                     ("B", "E"), ("D", "A")], "A",
                                    breadth_first=breadth)


@pytest.mark.parametrize("nodes,edges,start", [
    (["A", "A"], [], "A"), (["A"], [("A", "B")], "A"), (["A"], [], "Z"),
])
def test_traversal_rejects_duplicate_unknown_or_missing_nodes(nodes, edges, start):
    with pytest.raises(ValueError):
        trace_traversal(nodes, edges, start, breadth_first=True)
