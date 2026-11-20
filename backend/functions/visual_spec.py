"""Validated scene specifications and deterministic algorithm traces."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class TraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step: int = Field(ge=0)
    action: str
    state: dict[str, Any]


class VisualSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal[1] = 1
    scene_id: int = Field(ge=0)
    topic: str = Field(min_length=1, max_length=180)
    visual_goal: str = Field(min_length=1, max_length=500)
    visual_type: Literal["manim", "web_image", "pillow", "hybrid_image", "hybrid_gif"]
    duration_seconds: float = Field(gt=0, le=600)
    width: int = Field(gt=0, le=3840)
    height: int = Field(gt=0, le=2160)
    fps: int = Field(gt=0, le=60)
    input_data: dict[str, Any] = Field(default_factory=dict)
    trace: list[TraceEvent] = Field(default_factory=list)
    must_show: list[str] = Field(default_factory=list)
    must_not_show: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def constraints_do_not_conflict(self):
        required = {" ".join(feature.split()).casefold() for feature in self.must_show}
        excluded = {" ".join(feature.split()).casefold() for feature in self.must_not_show}
        if required & excluded:
            raise ValueError("must_show and must_not_show contain conflicting requirements")
        steps = [event.step for event in self.trace]
        if steps != list(range(len(steps))):
            raise ValueError("Trace steps must be contiguous and ordered from zero")
        return self


def validate_visual_spec(data: dict, *, max_repairs: int = 1) -> tuple[VisualSpec, bool]:
    """Validate a spec and attempt at most one safe repair of media settings.

    Learning goals and must/must-not constraints are never rewritten. If those
    fields are invalid or contradictory, validation fails and the caller must
    choose its explicit fallback path.
    """
    if max_repairs != 1:
        raise ValueError("VisualSpec supports exactly one bounded repair attempt")
    try:
        return VisualSpec.model_validate(data), False
    except ValidationError as original_error:
        repaired = dict(data)
        try:
            width, height = int(repaired.get("width", 1280)), int(repaired.get("height", 720))
            if width <= 0 or height <= 0 or width > 3840 or height > 2160:
                width, height = 1280, 720
            repaired["width"], repaired["height"] = width, height
            fps = int(repaired.get("fps", 25))
            repaired["fps"] = fps if 1 <= fps <= 60 else 25
            duration = float(repaired.get("duration_seconds", 5))
            repaired["duration_seconds"] = min(600.0, max(0.1, duration))
            return VisualSpec.model_validate(repaired), True
        except (TypeError, ValueError, ValidationError) as repair_error:
            raise repair_error from original_error


def trace_search(values: list, target: Any, *, binary: bool = False) -> list[TraceEvent]:
    """Create stable comparison events. Binary search requires sorted data."""
    if binary and values != sorted(values):
        raise ValueError("Binary search input must be sorted")
    events = []
    if binary:
        low, high = 0, len(values) - 1
        while low <= high:
            mid = (low + high) // 2
            value = values[mid]
            action = "found" if value == target else "compare"
            events.append(TraceEvent(step=len(events), action=action,
                                     state={"index": mid, "value": value, "target": target,
                                            "low": low, "high": high}))
            if value == target:
                break
            if value < target:
                low = mid + 1
            else:
                high = mid - 1
        return events
    for index, value in enumerate(values):
        found = value == target
        events.append(TraceEvent(step=len(events), action="found" if found else "compare",
                                 state={"index": index, "value": value, "target": target}))
        if found:
            break
    return events


def trace_bubble_sort(values: list) -> list[TraceEvent]:
    """Create deterministic swap and comparison events for bubble sort."""
    arr = list(values)
    n = len(arr)
    events = []
    for i in range(n):
        for j in range(0, n - i - 1):
            val_a, val_b = arr[j], arr[j + 1]
            will_swap = val_a > val_b
            events.append(TraceEvent(
                step=len(events),
                action="swap" if will_swap else "compare",
                state={"i": i, "j": j, "val_a": val_a, "val_b": val_b, "swap": will_swap, "array": list(arr)}
            ))
            if will_swap:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
        events.append(TraceEvent(
            step=len(events),
            action="lock",
            state={"index": n - 1 - i, "value": arr[n - 1 - i], "array": list(arr)}
        ))
    events.append(TraceEvent(
        step=len(events),
        action="sorted",
        state={"array": list(arr)}
    ))
    return events


def trace_merge_sort(values: list) -> list[TraceEvent]:
    """Create deterministic divide and merge events for merge sort."""
    events = []
    arr = list(values)
    mid = len(arr) // 2
    left_half = arr[:mid]
    right_half = arr[mid:]
    events.append(TraceEvent(
        step=len(events),
        action="split",
        state={"phase": "split_halves", "left": left_half, "right": right_half, "array": list(arr)}
    ))
    events.append(TraceEvent(
        step=len(events),
        action="merge_pairs",
        state={"phase": "merge_subarrays", "left_sorted": sorted(left_half), "right_sorted": sorted(right_half), "array": list(arr)}
    ))
    events.append(TraceEvent(
        step=len(events),
        action="sorted",
        state={"phase": "final_merge", "array": sorted(arr)}
    ))
    return events


def trace_traversal(nodes: list, edges: list[tuple], start: Any, *, breadth_first: bool) -> list[TraceEvent]:
    """Return deterministic visit and frontier-operation events in neighbor order."""
    if len(set(nodes)) != len(nodes):
        raise ValueError("Graph nodes must be unique")
    adjacency = {node: [] for node in nodes}
    for edge in edges:
        if len(edge) != 2 or edge[0] not in adjacency or edge[1] not in adjacency:
            raise ValueError("Every graph edge must reference two declared nodes")
        adjacency[edge[0]].append(edge[1])
    if start not in adjacency:
        raise ValueError("Traversal start must be a declared node")
    events = []

    def record(action, state):
        events.append(TraceEvent(step=len(events), action=action, state=state))

    if breadth_first:
        queue, seen, levels = [start], {start}, {start: 0}
        while queue:
            node = queue.pop(0)
            record("visit", {"node": node, "frontier": list(queue), "level": levels[node]})
            for neighbor in adjacency[node]:
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                levels[neighbor] = levels[node] + 1
                queue.append(neighbor)
                record("enqueue", {"node": neighbor, "parent": node,
                                   "frontier": list(queue), "level": levels[neighbor]})
        return events

    # Explicit DFS frames preserve declared neighbor order and expose backtracking.
    seen = {start}
    stack = [{"node": start, "next_neighbor": 0}]
    record("visit", {"node": start, "frontier": [start], "level": 0})
    while stack:
        frame = stack[-1]
        neighbors = adjacency[frame["node"]]
        if frame["next_neighbor"] < len(neighbors):
            neighbor = neighbors[frame["next_neighbor"]]
            frame["next_neighbor"] += 1
            if neighbor in seen:
                continue
            seen.add(neighbor)
            stack.append({"node": neighbor, "next_neighbor": 0})
            record("push", {"node": neighbor, "parent": frame["node"],
                             "frontier": [item["node"] for item in stack],
                             "level": len(stack) - 1})
            record("visit", {"node": neighbor, "frontier": [item["node"] for item in stack],
                              "level": len(stack) - 1})
            continue
        finished = stack.pop()["node"]
        parent = stack[-1]["node"] if stack else None
        record("backtrack", {"node": finished, "parent": parent,
                              "frontier": [item["node"] for item in stack],
                              "level": max(0, len(stack) - 1)})
    return events
