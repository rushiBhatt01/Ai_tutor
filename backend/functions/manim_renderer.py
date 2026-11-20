import os
import sys
import json
import io
import math
import re
import shutil
import signal
import wave
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List
from PIL import Image, ImageDraw, ImageFont, ImageStat
from functions.visual_artifacts import (
    ImageSource, VisualArtifact, VisualManifest, VisualSpecSummary, VisualValidation, atomic_output,
    file_sha256, load_visual_manifest, probe_visual_video, save_visual_manifest,
    visual_cache_key, visual_scene_fingerprint,
)
from functions.visual_spec import trace_search, trace_traversal, trace_bubble_sort, trace_merge_sort
from functions.visual_acceptance import AttemptBudget, Check, candidate_checks, evaluate_checks

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass



_RESOLVED_MANIM_PYTHON: Optional[str] = None


def visual_worker_limit(value=None):
    """Parse the configured scene worker count and enforce the hard resource cap."""
    raw = value if value is not None else os.environ.get("VISUAL_RENDER_WORKERS", "2")
    try:
        return max(1, min(4, int(raw)))
    except (TypeError, ValueError):
        return 2


def _bounded_worker_setting(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def validate_visual_spec_alignment(scenes, visual_specs):
    """Validate spec IDs and route choices before any renderer receives a scene."""
    from functions.visual_spec import VisualSpec

    spec_by_id = {}
    for raw_spec in visual_specs or []:
        spec = VisualSpec.model_validate(raw_spec)
        if spec.scene_id in spec_by_id:
            raise ValueError(f"Duplicate visual specification for scene {spec.scene_id}")
        spec_by_id[spec.scene_id] = VisualSpecSummary.model_validate(spec.model_dump(mode="json"))
    if set(spec_by_id) != set(scenes):
        raise ValueError("Validated visual specs must match storyboard scene IDs")
    for scene_id, scene in scenes.items():
        if spec_by_id[scene_id].visual_type != scene.visual_type:
            raise ValueError(f"Visual spec strategy mismatch for scene {scene_id}")
    return spec_by_id


def resolve_manim_python() -> Optional[str]:
    """
    Locates the Python executable that has Manim installed.
    Checks:
      1. MANIM_PYTHON_PATH environment variable
      2. manim-test-module/.venv/Scripts/python.exe
      3. backend/.venv/Scripts/python.exe
      4. Current sys.executable
    """
    global _RESOLVED_MANIM_PYTHON
    if _RESOLVED_MANIM_PYTHON and os.path.isfile(_RESOLVED_MANIM_PYTHON):
        return _RESOLVED_MANIM_PYTHON

    env_path = os.environ.get("MANIM_PYTHON_PATH")
    if env_path and os.path.isfile(env_path):
        _RESOLVED_MANIM_PYTHON = env_path
        return env_path

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidates = [
        os.path.join(repo_root, "manim-test-module", ".venv", "Scripts", "python.exe"),
        os.path.join(repo_root, "backend", ".venv", "Scripts", "python.exe"),
        sys.executable,
    ]

    for cand in candidates:
        if os.path.isfile(cand):
            try:
                # Check if manim can be imported with this python
                res = subprocess.run([cand, "-c", "import manim; print('ok')"], capture_output=True, text=True, timeout=15)
                if res.returncode == 0 and "ok" in res.stdout:
                    _RESOLVED_MANIM_PYTHON = cand
                    return cand
            except Exception:
                continue

    return None


def get_audio_duration(audio_path: str) -> float:
    """Returns audio duration in seconds via wave or ffprobe."""
    if not os.path.isfile(audio_path):
        return 5.0
    try:
        with wave.open(audio_path, 'rb') as w:
            frames = w.getnframes()
            rate = w.getframerate()
            if rate > 0 and frames > 0:
                return float(frames) / float(rate)
    except Exception:
        pass

    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return float(res.stdout.strip())
    except Exception:
        pass

    return 5.0



def _trace_for_manim(topic_type, steps, params):
    """Build a deterministic trace before template rendering; templates only replay data."""
    kind = str(topic_type).strip().casefold()
    defaults = [2, 4, 6, 8, 10, 12, 14]
    if kind in {"binary_search", "linear_search"}:
        values = params.get("values", defaults)
        target = params.get("target", 12)
        if not isinstance(values, list) or len(values) > 12:
            raise ValueError("Search templates require a list with at most 12 values")
        events = trace_search(values, target, binary=kind == "binary_search")
        return [event.model_dump() for event in events], {"values": values, "target": target}

    if kind in {"bubble_sort", "sorting", "sort"}:
        sort_defaults = [6, 2, 8, 4, 1]
        values = params.get("values", sort_defaults)
        if not isinstance(values, list) or len(values) > 10:
            raise ValueError("Sorting templates require a list with at most 10 values")
        events = trace_bubble_sort(values)
        return [event.model_dump() for event in events], {"values": values}

    if kind in {"merge_sort"}:
        sort_defaults = [6, 2, 8, 4, 3, 7]
        values = params.get("values", sort_defaults)
        if not isinstance(values, list) or len(values) > 10:
            raise ValueError("Merge sort template requires a list with at most 10 values")
        events = trace_merge_sort(values)
        return [event.model_dump() for event in events], {"values": values}

    if kind in {"bfs", "dfs"}:
        nodes = params.get("nodes", params.get("graph_nodes"))
        if nodes is None:
            nodes = steps or ["A", "B", "C", "D", "E"]
        edges = params.get("edges")
        if edges is None:
            edges = [["A", "B"], ["A", "C"], ["B", "D"], ["B", "E"]]
        start = params.get("start", nodes[0] if nodes else None)
        if not isinstance(nodes, list) or len(nodes) > 10:
            raise ValueError("Traversal templates require a list with at most 10 nodes")
        events = trace_traversal(nodes, edges, start, breadth_first=kind == "bfs")
        return [event.model_dump() for event in events], {"nodes": nodes, "edges": edges}

    raise ValueError(f"Unsupported Manim algorithm: {kind or 'unspecified'}")


def _template_data(template, replacements):
    return re.sub(r"__[A-Z_]+__", lambda match: replacements.get(match.group(0), match.group(0)), template)


def _python_literal(value, depth=0):
    """Serialize JSON-like trace data as safe Python literals for the trusted template."""
    if depth > 20:
        raise ValueError("Manim trace data is too deeply nested")
    if value is None or isinstance(value, (str, bool, int)):
        return repr(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Manim trace numbers must be finite")
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_python_literal(item, depth + 1) for item in value) + "]"
    if isinstance(value, tuple):
        contents = ", ".join(_python_literal(item, depth + 1) for item in value)
        return "(" + contents + ("," if len(value) == 1 else "") + ")"
    if isinstance(value, dict):
        return "{" + ", ".join(
            f"{_python_literal(key, depth + 1)}: {_python_literal(item, depth + 1)}"
            for key, item in value.items()
        ) + "}"
    raise ValueError(f"Unsupported Manim trace value: {type(value).__name__}")


def _animation_timing(target_duration, event_count):
    duration = float(target_duration)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Animation duration must be a positive finite number")
    duration = max(0.8, duration)
    intro = min(0.45, duration * 0.15)
    creation = min(0.5, duration * 0.16)
    step_time = max(0.055, (duration - intro - creation - 0.2) / max(1, event_count))
    hold = max(0.05, duration - intro - creation - step_time * event_count)
    return intro, creation, step_time, hold


def build_manim_trace_events(topic_type, steps, target_duration, custom_params=None):
    """Return the deterministic trace annotated with approximate video time and frame."""
    params = dict(custom_params or {})
    events, _ = _trace_for_manim(topic_type, steps, params)
    intro, creation, step_time, _ = _animation_timing(target_duration, len(events))
    start = intro + creation
    timed = []
    for index, event in enumerate(events):
        event_start = start + index * step_time
        timed.append({
            **event,
            "animation_time_seconds": round(event_start, 3),
            "animation_frame": round(event_start * 25),
            "duration_seconds": round(step_time, 3),
        })
    return timed


def validate_manim_template(topic_type, code, trace_events):
    """Fail closed if the generated template or trace omits algorithm-specific steps."""
    required = {
        "binary_search": ("Low", "Mid", "High", "ptr_low"),
        "linear_search": ("Compare index", "TARGET"),
        "bubble_sort": ("Bubble Sort", "elements"),
        "merge_sort": ("Merge Sort", "DIVIDE"),
        "sorting": ("Bubble Sort", "elements"),
        "sort": ("Bubble Sort", "elements"),
        "bfs": ("QUEUE", "Level", "enqueue"),
        "dfs": ("STACK", "Backtrack", "push"),
    }.get(str(topic_type).casefold())
    if not required or any(marker not in code for marker in required):
        raise ValueError(f"Manim template evidence is incomplete for {topic_type}")
    if not trace_events or [event.get("step") for event in trace_events] != list(range(len(trace_events))):
        raise ValueError("Manim trace evidence is empty or unordered")
    times = [event.get("animation_time_seconds") for event in trace_events]
    if any(not isinstance(value, (int, float)) for value in times) or times != sorted(times):
        raise ValueError("Manim trace timestamps are invalid")


def validate_manim_trace_frames(video_path, trace_events, duration_seconds):
    """Decode representative trace frames and reject blank or out-of-range output."""
    if not trace_events:
        raise ValueError("No trace events are available for frame validation")
    times = [float(event["animation_time_seconds"]) for event in trace_events]
    if any(value < 0 or value >= duration_seconds for value in times):
        raise ValueError("Trace event falls outside the encoded visual duration")
    indices = sorted({0, len(times) // 2, len(times) - 1})
    for index in indices:
        at = min(max(0.0, times[index] + 0.08), max(0.0, duration_seconds - 0.04))
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{at:.3f}", "-i", str(video_path),
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True, timeout=12,
        )
        if result.returncode != 0 or not result.stdout:
            raise ValueError(f"Could not decode trace frame at {at:.3f}s")
        try:
            with Image.open(io.BytesIO(result.stdout)) as frame:
                variance = sum(ImageStat.Stat(frame.convert("RGB").resize((64, 36))).stddev) / 3
                if variance < 1.0:
                    raise ValueError(f"Trace frame at {at:.3f}s is visually blank")
        except (OSError, ValueError) as error:
            raise ValueError(f"Invalid trace frame at {at:.3f}s: {error}") from error
    return [f"decoded nonblank trace frames: {len(indices)}"]


def generate_manim_python_code(
    topic_type: str,
    scene_title: str,
    steps: List[str],
    target_duration: float,
    custom_params: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate one trusted template that replays a deterministic algorithm trace."""
    topic_type = str(topic_type).strip().casefold()
    params = dict(custom_params or {})
    events, data = _trace_for_manim(topic_type, steps, params)
    if not events:
        raise ValueError("Cannot animate an empty algorithm trace")
    intro, creation, step_time, hold = _animation_timing(target_duration, len(events))
    common = {
        "__TITLE__": json.dumps(str(scene_title)[:120]),
        "__TRACE__": _python_literal(events),
        "__INTRO__": repr(intro),
        "__CREATE__": repr(creation),
        "__STEP__": repr(step_time),
        "__HOLD__": repr(hold),
    }

    linear_search_template = r'''from manim import *

TITLE = __TITLE__
TRACE = __TRACE__
VALUES = __VALUES__
TARGET = __TARGET__
INTRO = __INTRO__
CREATE_TIME = __CREATE__
STEP_TIME = __STEP__
HOLD = __HOLD__

class GeneratedTechnicalScene(Scene):
    def construct(self):
        title = Text(TITLE, font_size=30).to_edge(UP)
        self.play(Write(title), run_time=INTRO)
        count = len(VALUES)
        gap = min(1.05, 8.0 / max(1, count))
        boxes, labels = [], []
        for index, value in enumerate(VALUES):
            x = (index - (count - 1) / 2) * gap
            box = Square(side_length=max(0.4, gap - 0.1), color=BLUE, stroke_width=2.5).move_to([x, 0.4, 0])
            label = Text(str(value)[:12], font_size=22, color=WHITE).move_to(box.get_center())
            index_label = Text(str(index), font_size=14, color=GRAY).next_to(box, DOWN, buff=0.1)
            boxes.append(box)
            labels.extend([label, index_label])
        if boxes:
            self.play(Create(VGroup(*boxes)), Write(VGroup(*labels)), run_time=CREATE_TIME)
        status = Text(f"Linear search: Target = {TARGET}", font_size=20).to_edge(DOWN)
        self.add(status)
        for event in TRACE:
            state = event["state"]
            index = state["index"]
            value = state["value"]
            status.become(Text(f"Compare index {index}: {value} to {TARGET}", font_size=20).to_edge(DOWN))
            color = GREEN if event["action"] == "found" else RED
            self.play(boxes[index].animate.set_fill(color, opacity=0.85), run_time=STEP_TIME)
            if event["action"] == "found":
                status.become(Text(f"Found {TARGET} at index {index}!", font_size=22, color=GREEN).to_edge(DOWN))
                break
        self.wait(HOLD)
'''

    binary_search_template = r'''from manim import *

TITLE = __TITLE__
TRACE = __TRACE__
VALUES = __VALUES__
TARGET = __TARGET__
INTRO = __INTRO__
CREATE_TIME = __CREATE__
STEP_TIME = __STEP__
HOLD = __HOLD__

class GeneratedTechnicalScene(Scene):
    def construct(self):
        title = Text(TITLE, font_size=30).to_edge(UP)
        self.play(Write(title), run_time=INTRO)
        count = len(VALUES)
        gap = min(1.15, 8.5 / max(1, count))
        boxes, labels = [], []
        for index, value in enumerate(VALUES):
            x = (index - (count - 1) / 2) * gap
            box = Square(side_length=max(0.42, gap - 0.1), color=BLUE, stroke_width=2.5).move_to([x, 0.4, 0])
            label = Text(str(value)[:12], font_size=24, color=WHITE).move_to(box.get_center())
            idx_label = Text(f"[{index}]", font_size=14, color=GRAY).next_to(box, UP, buff=0.12)
            boxes.append(box)
            labels.extend([label, idx_label])
        if boxes:
            self.play(Create(VGroup(*boxes)), Write(VGroup(*labels)), run_time=CREATE_TIME)

        ptr_low = VGroup(Arrow(start=DOWN*0.5, end=UP*0.1, color=BLUE, buff=0), Text("Low", font_size=16, color=BLUE).next_to(DOWN*0.5, DOWN, buff=0.05))
        ptr_mid = VGroup(Arrow(start=DOWN*0.5, end=UP*0.1, color=YELLOW, buff=0), Text("Mid", font_size=16, color=YELLOW).next_to(DOWN*0.5, DOWN, buff=0.05))
        ptr_high = VGroup(Arrow(start=DOWN*0.5, end=UP*0.1, color=PURPLE, buff=0), Text("High", font_size=16, color=PURPLE).next_to(DOWN*0.5, DOWN, buff=0.05))
        
        status = Text(f"Binary Search: Target = {TARGET}", font_size=20).to_edge(DOWN)
        self.add(status)
        
        pointers_added = False
        for event in TRACE:
            state = event["state"]
            mid = state["index"]
            low = state["low"]
            high = state["high"]
            value = state["value"]
            
            pos_l = [boxes[low].get_center()[0], -0.45, 0]
            pos_m = [boxes[mid].get_center()[0], -0.45, 0]
            pos_h = [boxes[high].get_center()[0], -0.45, 0]
            
            if not pointers_added:
                ptr_low.move_to(pos_l)
                ptr_mid.move_to(pos_m)
                ptr_high.move_to(pos_h)
                self.play(FadeIn(ptr_low), FadeIn(ptr_mid), FadeIn(ptr_high), run_time=min(0.4, STEP_TIME*0.8))
                pointers_added = True
            else:
                self.play(
                    ptr_low.animate.move_to(pos_l),
                    ptr_mid.animate.move_to(pos_m),
                    ptr_high.animate.move_to(pos_h),
                    run_time=min(0.35, STEP_TIME*0.6)
                )
            
            if event["action"] == "found":
                status.become(Text(f"Found Target {TARGET} at Mid index {mid}!", font_size=22, color=GREEN).to_edge(DOWN))
                self.play(boxes[mid].animate.set_fill(GREEN, opacity=0.9).scale(1.1), run_time=STEP_TIME)
                break
            else:
                cmp_text = f"Low {low} | Mid {mid} ({value}) < Target ({TARGET}) | High {high} -> Discard Left" if value < TARGET else f"Low {low} | Mid {mid} ({value}) > Target ({TARGET}) | High {high} -> Discard Right"
                status.become(Text(cmp_text, font_size=18, color=YELLOW).to_edge(DOWN))
                self.play(boxes[mid].animate.set_fill(YELLOW, opacity=0.8), run_time=STEP_TIME*0.5)
                
                if value < TARGET:
                    for j in range(low, mid + 1):
                        boxes[j].set_fill(GRAY, opacity=0.18)
                else:
                    for j in range(mid, high + 1):
                        boxes[j].set_fill(GRAY, opacity=0.18)
        self.wait(HOLD)
'''

    bubble_sort_template = r'''from manim import *

TITLE = __TITLE__
TRACE = __TRACE__
VALUES = __VALUES__
INTRO = __INTRO__
CREATE_TIME = __CREATE__
STEP_TIME = __STEP__
HOLD = __HOLD__

class GeneratedTechnicalScene(Scene):
    def construct(self):
        title = Text(TITLE, font_size=30).to_edge(UP)
        self.play(Write(title), run_time=INTRO)
        count = len(VALUES)
        gap = min(1.2, 8.0 / max(1, count))
        
        palette = [BLUE, TEAL, GREEN_B, YELLOW, ORANGE, RED]
        sorted_vals = sorted(VALUES)
        
        elements = []
        for index, val in enumerate(VALUES):
            x = (index - (count - 1) / 2) * gap
            rank = sorted_vals.index(val)
            col = palette[rank % len(palette)]
            box = Square(side_length=0.75, color=col, stroke_width=2.5).move_to([x, 0.4, 0])
            lbl = Text(str(val), font_size=26, color=WHITE).move_to(box.get_center())
            elements.append(VGroup(box, lbl))
            
        self.play(*[Create(e) for e in elements], run_time=CREATE_TIME)
        status = Text("Bubble Sort: Compare adjacent pairs and swap if out of order", font_size=20).to_edge(DOWN)
        self.add(status)
        
        ptr = Arrow(start=DOWN*0.5, end=UP*0.1, color=YELLOW).next_to(elements[0], DOWN, buff=0.2)
        self.play(FadeIn(ptr), run_time=0.3)
        
        for event in TRACE:
            action = event["action"]
            state = event["state"]
            if action in {"compare", "swap"}:
                j = state["j"]
                val_a = state["val_a"]
                val_b = state["val_b"]
                elem_a = elements[j]
                elem_b = elements[j + 1]
                pos_a = elem_a.get_center()
                pos_b = elem_b.get_center()
                
                ptr.next_to(VGroup(elem_a, elem_b), DOWN, buff=0.2)
                
                if action == "swap":
                    status.become(Text(f"Swap {val_a} > {val_b}: Moving {val_a} right", font_size=20, color=ORANGE).to_edge(DOWN))
                    self.play(
                        elem_a.animate.move_to(pos_b),
                        elem_b.animate.move_to(pos_a),
                        run_time=min(0.4, STEP_TIME)
                    )
                    elements[j], elements[j + 1] = elements[j + 1], elements[j]
                else:
                    status.become(Text(f"{val_a} <= {val_b}: Already in order", font_size=20, color=GRAY).to_edge(DOWN))
                    self.wait(min(0.2, STEP_TIME * 0.5))
            elif action == "lock":
                idx = state["index"]
                status.become(Text(f"Element {state['value']} is locked in sorted position", font_size=20, color=GREEN).to_edge(DOWN))
                self.play(elements[idx][0].animate.set_color(GREEN).set_stroke(GREEN, width=4), run_time=min(0.3, STEP_TIME*0.6))
            elif action == "sorted":
                status.become(Text("Array is fully sorted!", font_size=22, color=GREEN).to_edge(DOWN))
                self.play(*[e[0].animate.set_fill(GREEN, opacity=0.7) for e in elements], run_time=0.5)
        self.wait(HOLD)
'''

    merge_sort_template = r'''from manim import *

TITLE = __TITLE__
TRACE = __TRACE__
VALUES = __VALUES__
INTRO = __INTRO__
CREATE_TIME = __CREATE__
STEP_TIME = __STEP__
HOLD = __HOLD__

class GeneratedTechnicalScene(Scene):
    def construct(self):
        title = Text(TITLE, font_size=30).to_edge(UP)
        self.play(Write(title), run_time=INTRO)
        count = len(VALUES)
        gap = 0.9
        
        def make_row(vals, y_pos, color=BLUE):
            boxes, labels = [], []
            n = len(vals)
            for i, v in enumerate(vals):
                x = (i - (n - 1) / 2) * gap
                b = Square(side_length=0.6, color=color, stroke_width=2.5).move_to([x, y_pos, 0])
                l = Text(str(v), font_size=24, color=WHITE).move_to(b.get_center())
                boxes.append(b)
                labels.append(l)
            return VGroup(*boxes, *labels)
        
        top_row = make_row(VALUES, 1.8, color=RED_C)
        lbl_top = Text("Unsorted Array", font_size=18, color=GRAY).next_to(top_row, UP, buff=0.15)
        self.play(Create(top_row), Write(lbl_top), run_time=CREATE_TIME)
        
        status = Text("Merge Sort: Divide & Conquer", font_size=20).to_edge(DOWN)
        self.add(status)
        
        mid = count // 2
        left_vals = VALUES[:mid]
        right_vals = VALUES[mid:]
        
        status.become(Text(f"1. DIVIDE: Split into {left_vals} and {right_vals}", font_size=20, color=YELLOW).to_edge(DOWN))
        
        n_l = len(left_vals)
        boxes_l, lbls_l = [], []
        for i, v in enumerate(left_vals):
            x = -2.5 + (i - (n_l - 1) / 2) * gap
            b = Square(side_length=0.6, color=BLUE, stroke_width=2).move_to([x, 0.3, 0])
            l = Text(str(v), font_size=24, color=WHITE).move_to(b.get_center())
            boxes_l.append(b)
            lbls_l.append(l)
        left_group = VGroup(*boxes_l, *lbls_l)
        
        n_r = len(right_vals)
        boxes_r, lbls_r = [], []
        for i, v in enumerate(right_vals):
            x = 2.5 + (i - (n_r - 1) / 2) * gap
            b = Square(side_length=0.6, color=BLUE, stroke_width=2).move_to([x, 0.3, 0])
            l = Text(str(v), font_size=24, color=WHITE).move_to(b.get_center())
            boxes_r.append(b)
            lbls_r.append(l)
        right_group = VGroup(*boxes_r, *lbls_r)
        
        arr_l = Arrow(start=[0, 1.4, 0], end=[-2.5, 0.8, 0], color=GRAY, buff=0.1)
        arr_r = Arrow(start=[0, 1.4, 0], end=[2.5, 0.8, 0], color=GRAY, buff=0.1)
        self.play(Create(arr_l), Create(arr_r), FadeIn(left_group), FadeIn(right_group), run_time=0.6)
        
        sorted_l = sorted(left_vals)
        sorted_r = sorted(right_vals)
        status.become(Text("2. RECURSE: Sort sub-arrays independently", font_size=20, color=ORANGE).to_edge(DOWN))
        
        new_lbls_l = [Text(str(v), font_size=24, color=YELLOW).move_to(b.get_center()) for b, v in zip(boxes_l, sorted_l)]
        new_lbls_r = [Text(str(v), font_size=24, color=YELLOW).move_to(b.get_center()) for b, v in zip(boxes_r, sorted_r)]
        self.play(
            *[Transform(old, new) for old, new in zip(lbls_l, new_lbls_l)],
            *[Transform(old, new) for old, new in zip(lbls_r, new_lbls_r)],
            run_time=0.5
        )
        
        final_sorted = sorted(VALUES)
        status.become(Text("3. MERGE: Combine sorted halves into final array", font_size=20, color=GREEN).to_edge(DOWN))
        final_row = make_row(final_sorted, -1.2, color=GREEN)
        arr_merge_l = Arrow(start=[-2.5, -0.1, 0], end=[-0.8, -0.8, 0], color=GREEN, buff=0.1)
        arr_merge_r = Arrow(start=[2.5, -0.1, 0], end=[0.8, -0.8, 0], color=GREEN, buff=0.1)
        self.play(Create(arr_merge_l), Create(arr_merge_r), Create(final_row), run_time=0.8)
        
        status.become(Text("Merge Sort Complete: O(n log n)", font_size=22, color=GREEN).to_edge(DOWN))
        self.wait(HOLD)
'''

    if topic_type == "binary_search":
        return _template_data(binary_search_template, {
            **common,
            "__VALUES__": _python_literal(data["values"]),
            "__TARGET__": _python_literal(data["target"]),
        })

    if topic_type == "linear_search":
        return _template_data(linear_search_template, {
            **common,
            "__VALUES__": _python_literal(data["values"]),
            "__TARGET__": _python_literal(data["target"]),
        })

    if topic_type in {"bubble_sort", "sorting", "sort"}:
        return _template_data(bubble_sort_template, {
            **common,
            "__VALUES__": _python_literal(data["values"]),
        })

    if topic_type == "merge_sort":
        return _template_data(merge_sort_template, {
            **common,
            "__VALUES__": _python_literal(data["values"]),
        })

    graph_template = r'''from manim import *

TITLE = __TITLE__
TRACE = __TRACE__
NODES = __NODES__
EDGES = __EDGES__
INTRO = __INTRO__
CREATE_TIME = __CREATE__
STEP_TIME = __STEP__
HOLD = __HOLD__
IS_BFS = __IS_BFS__

class GeneratedTechnicalScene(Scene):
    def construct(self):
        title = Text(TITLE, font_size=30).to_edge(UP)
        self.play(Write(title), run_time=INTRO)
        levels = {}
        for event in TRACE:
            if event["action"] == "visit":
                levels.setdefault(event["state"]["node"], event["state"]["level"])
        grouped = {}
        for node in NODES:
            grouped.setdefault(levels.get(node, 0), []).append(node)
        positions = {}
        for level, members in grouped.items():
            spacing = min(1.7, 7.2 / max(1, len(members)))
            for index, node in enumerate(members):
                positions[node] = [(index - (len(members) - 1) / 2) * spacing,
                                   1.8 - level * 0.65, 0]
        edges = VGroup(*[Arrow(positions[a], positions[b], buff=0.34, color=GRAY)
                         for a, b in EDGES if a in positions and b in positions])
        nodes = {node: Circle(radius=0.34, color=BLUE, stroke_width=3).move_to(positions[node])
                 for node in NODES}
        labels = {node: Text(str(node)[:12], font_size=20).move_to(positions[node]) for node in NODES}
        self.play(Create(edges), *[Create(item) for item in nodes.values()],
                  *[Write(item) for item in labels.values()], run_time=CREATE_TIME)
        heading = "QUEUE" if IS_BFS else "STACK"
        status = Text(f"{heading}: ", font_size=20).to_edge(DOWN)
        self.add(status)
        for event in TRACE:
            state = event["state"]
            node = state["node"]
            frontier = " -> ".join(map(str, state["frontier"])) or "empty"
            level_text = f"    Level {state['level']}" if IS_BFS else ""
            if event["action"] == "backtrack":
                label = f"Backtrack {node} to {state['parent']}    STACK: {frontier}"
                color = GRAY
            elif event["action"] == "enqueue":
                label = f"Enqueue {node}    QUEUE: {frontier}    Level {state['level']}"
                color = YELLOW
            elif event["action"] == "push":
                label = f"Push {node}    STACK: {frontier}"
                color = YELLOW
            else:
                label = f"Visit {node}    {heading}: {frontier}{level_text}"
                color = GREEN
            status.become(Text(label, font_size=20, color=color).to_edge(DOWN))
            self.play(nodes[node].animate.set_fill(color, opacity=0.82), run_time=STEP_TIME)
        self.wait(HOLD)
'''
    return _template_data(graph_template, {
        **common,
        "__NODES__": _python_literal(data["nodes"]),
        "__EDGES__": _python_literal(data["edges"]),
        "__IS_BFS__": repr(topic_type == "bfs"),
    })


def render_manim_to_mp4(
    scene_code: str,
    output_mp4: str,
    target_duration: float,
    audio_path: Optional[str] = None,
    timeout: int = 120
) -> bool:
    """
    Renders Manim scene script using Python subprocess on CPU,
    then normalizes video to 1280x720 25fps and matches exact audio duration.
    """
    python_exe = resolve_manim_python()
    if not python_exe:
        print("[Manim] Error: No python environment with Manim found.")
        return False

    bubblewrap = shutil.which("bwrap") if sys.platform.startswith("linux") else None
    if not bubblewrap:
        print("[Manim] Linux Bubblewrap isolation is unavailable; using Pillow fallback.")
        return False

    with tempfile.TemporaryDirectory() as td:
        script_file = os.path.join(td, "scene_runner.py")
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(scene_code)

        media_dir = os.path.join(td, "media")
        timeout = max(1, min(600, int(timeout)))
        memory_mb = _bounded_worker_setting("MANIM_WORKER_MEMORY_MB", 3072, 512, 8192)
        output_mb = _bounded_worker_setting("MANIM_WORKER_FILE_LIMIT_MB", 512, 64, 4096)
        open_files = _bounded_worker_setting("MANIM_WORKER_OPEN_FILES", 128, 32, 1024)
        worker_launcher = os.path.join(os.path.dirname(__file__), "manim_worker.py")
        sandbox_launcher = os.path.join(td, "manim_worker.py")
        shutil.copyfile(worker_launcher, sandbox_launcher)
        try:
            prefix_result = subprocess.run(
                [python_exe, "-I", "-c", "import sys; print(sys.prefix)"],
                capture_output=True, text=True, timeout=10, check=True,
            )
            python_prefix = os.path.realpath(prefix_result.stdout.strip())
            if not python_prefix or not os.path.isdir(python_prefix):
                raise ValueError("Could not resolve Manim Python environment")
        except Exception as error:
            print(f"[Manim] Cannot prepare isolated runtime: {error}")
            return False
        sandbox_command = [
            bubblewrap, "--die-with-parent", "--new-session", "--unshare-all",
            "--clearenv",
            "--ro-bind", "/usr", "/usr",
        ]
        # ELF interpreters commonly use /lib or /lib64 even on usr-merged hosts.
        for runtime_path in ("/bin", "/lib", "/lib64"):
            if os.path.islink(runtime_path):
                sandbox_command.extend(["--symlink", os.readlink(runtime_path), runtime_path])
            elif os.path.isdir(runtime_path):
                sandbox_command.extend(["--ro-bind", runtime_path, runtime_path])
        if os.path.isfile("/etc/ld.so.cache"):
            sandbox_command.extend(["--ro-bind", "/etc/ld.so.cache", "/etc/ld.so.cache"])
        if os.path.exists("/etc/fonts"):
            sandbox_command.extend(["--ro-bind", "/etc/fonts", "/etc/fonts"])
        if not (python_prefix == "/usr" or python_prefix.startswith("/usr/")):
            sandbox_command.extend(["--ro-bind", python_prefix, python_prefix])
        sandbox_command.extend([
            "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
            "--bind", td, "/work", "--chdir", "/work",
            "--setenv", "HOME", "/work",
            "--setenv", "TMPDIR", "/work",
            "--setenv", "MPLCONFIGDIR", "/work/.mplconfig",
            "--setenv", "XDG_CACHE_HOME", "/work/.cache",
            "--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin",
            "--setenv", "LANG", "C.UTF-8",
            "--setenv", "OMP_NUM_THREADS", "1",
            "--setenv", "OPENBLAS_NUM_THREADS", "1",
            "--setenv", "MKL_NUM_THREADS", "1",
            "--setenv", "CUDA_VISIBLE_DEVICES", "",
            "--", python_exe, "-I", "/work/manim_worker.py",
            str(timeout + 2), str(memory_mb * 1024 * 1024),
            str(output_mb * 1024 * 1024), str(open_files), "--",
            python_exe, "-I", "-m", "manim",
            "-ql",  # fast low quality CPU rendering
            "--media_dir", "/work/media",
            "/work/scene_runner.py",
            "GeneratedTechnicalScene"
        ])
        cmd = sandbox_command

        print(f"[Manim CPU] Rendering scene in Bubblewrap sandbox with {python_exe}...")
        stdout_path = os.path.join(td, "worker.stdout")
        stderr_path = os.path.join(td, "worker.stderr")
        process = None
        try:
            with open(stdout_path, "wb") as stdout_file, open(stderr_path, "wb") as stderr_file:
                process = subprocess.Popen(
                    cmd, cwd=td, stdout=stdout_file, stderr=stderr_file,
                    start_new_session=True,
                    env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                         "MKL_NUM_THREADS": "1", "CUDA_VISIBLE_DEVICES": ""},
                )
                return_code = process.wait(timeout=timeout)
            if return_code != 0:
                with open(stderr_path, "rb") as stream:
                    stream.seek(0, os.SEEK_END)
                    stream.seek(max(0, stream.tell() - 16000))
                    error_tail = stream.read(16000).decode("utf-8", errors="replace")
                print(f"[Manim CPU] Isolated render failed (code {return_code}): {error_tail}")
                return False
        except subprocess.TimeoutExpired:
            print(f"[Manim CPU] Render timed out after {timeout} seconds.")
            return False
        except Exception as e:
            print(f"[Manim CPU] Render execution error: {e}")
            return False
        finally:
            # Descendants can outlive the direct child, including on cancellation.
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError:
                    if process.poll() is None:
                        process.kill()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("[Manim CPU] Worker cleanup exceeded its five-second deadline.")

        # Locate generated MP4
        rendered_mp4 = None
        for root, dirs, files in os.walk(media_dir):
            for file in files:
                if file.endswith(".mp4") and "partial_movie_files" not in root:
                    rendered_mp4 = os.path.join(root, file)
                    break
            if rendered_mp4:
                break

        if not rendered_mp4 or not os.path.isfile(rendered_mp4):
            print("[Manim CPU] No output MP4 found in media directory.")
            return False

        # Normalize with FFmpeg: 1280x720, 25fps, H.264, embed audio if present
        os.makedirs(os.path.dirname(output_mp4), exist_ok=True)
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", rendered_mp4,
        ]

        if audio_path and os.path.isfile(audio_path):
            ffmpeg_cmd.extend(["-i", audio_path])
        else:
            ffmpeg_cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])

        ffmpeg_cmd.extend([
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=25",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-t", f"{target_duration:.3f}",
        ])

        try:
            with atomic_output(output_mp4) as temporary:
                ff_res = subprocess.run(ffmpeg_cmd + [temporary], capture_output=True, text=True, timeout=30)
                if ff_res.returncode != 0:
                    raise ValueError(f"Normalization failed: {ff_res.stderr}")
                probe_visual_video(temporary)
            return True
        except Exception as e:
            print(f"[Manim FFmpeg] FFmpeg error: {e}")
            return False


def create_manim_fallback_slide(title: str, steps: List[str], output_image_path: str):
    """Create a readable Pillow slide, wrapping and fitting text to the canvas."""
    os.makedirs(os.path.dirname(output_image_path) or ".", exist_ok=True)
    width, height = 1280, 720
    img = Image.new("RGB", (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    title_font_resizable = True
    body_font_resizable = True
    try:
        font_title = ImageFont.truetype("arial.ttf", 44)
        font_body = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        try:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()
        except Exception:
            if hasattr(ImageFont, "load_default_imagefont"):
                font_title = ImageFont.load_default_imagefont()
                font_body = ImageFont.load_default_imagefont()
            else:
                font_title = ImageFont.load_default()
                font_body = ImageFont.load_default()
        title_font_resizable = False
        body_font_resizable = False

    def wrap(text, font, max_width):
        lines, current = [], ""
        for word in str(text).split():
            candidate = f"{current} {word}".strip()
            if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines or [""]

    def font_line_height(font):
        bounds = draw.textbbox((0, 0), "Ag", font=font)
        return max(1, bounds[3] - bounds[1])

    title_lines = wrap(title, font_title, 1160)
    while title_font_resizable and len(title_lines) > 2 and getattr(font_title, "size", 44) > 28:
        try:
            font_title = ImageFont.truetype("arial.ttf", font_title.size - 2)
        except OSError:
            title_font_resizable = False
            break
        title_lines = wrap(title, font_title, 1160)
    y = 45
    for line in title_lines[:2]:
        draw.text((60, y), line, fill=(250, 204, 21), font=font_title)
        y += font_line_height(font_title) + 8

    heading_y = y + 18
    draw.text((60, heading_y), "Technical Demonstration Walkthrough:", fill=(148, 163, 184), font=font_body)
    content_top, content_bottom = heading_y + 52, 675
    items = [f"Step {idx + 1}: {step}" for idx, step in enumerate(steps[:8])]
    if not items:
        items = ["A visual renderer was unavailable. This scene uses the safe fallback."]
    gap = 10
    row_height = min(76, max(46, (content_bottom - content_top - gap * (len(items) - 1)) // len(items)))
    for idx, text in enumerate(items):
        row_y = content_top + idx * (row_height + gap)
        if row_y + row_height > content_bottom:
            break
        draw.rounded_rectangle([60, row_y, 1220, row_y + row_height], radius=8,
                               fill=(30, 41, 59), outline=(59, 130, 246), width=2)
        lines = wrap(text, font_body, 1080)
        line_height = font_line_height(font_body) + 4
        while body_font_resizable and len(lines) * line_height > row_height - 12 and getattr(font_body, "size", 24) > 16:
            try:
                font_body = ImageFont.truetype("arial.ttf", font_body.size - 1)
            except OSError:
                body_font_resizable = False
                break
            line_height = font_line_height(font_body) + 4
            lines = wrap(text, font_body, 1080)
        line_y = row_y + max(5, (row_height - line_height * min(len(lines), 2)) // 2)
        for line in lines[:2]:
            draw.text((82, line_y), line, fill=(241, 245, 249), font=font_body)
            line_y += line_height

    with atomic_output(output_image_path) as temporary:
        img.save(temporary, "JPEG", quality=95)


def render_scene_manim(
    scene_spec: Dict[str, Any],
    chunk_id: str,
    run_dir: str,
    audio_path: Optional[str] = None
) -> str:
    """
    Main entry point for rendering a Manim scene for a single storyboard scene.
    Writes output video to {run_dir}/image_videos/{chunk_id}.mp4.
    If Manim rendering fails, writes fallback canvas to {run_dir}/images/{chunk_id}.jpg.
    Returns path to the output video file.
    """
    output_video = os.path.join(run_dir, "image_videos", f"{chunk_id}.mp4")
    output_image = os.path.join(run_dir, "images", f"{chunk_id}.jpg")

    audio_file = audio_path or os.path.join(run_dir, "audio", f"{chunk_id}.wav")
    duration = get_audio_duration(audio_file)

    topic_type = scene_spec.get("topic_type", "bfs")
    scene_title = scene_spec.get("scene_title", "Algorithm Visualization")
    steps = scene_spec.get("steps", ["A", "B", "C", "D", "E"])

    params = dict(scene_spec.get("params") or {})
    for name in ("values", "target", "nodes", "edges", "start"):
        if name in scene_spec and scene_spec[name] is not None:
            params.setdefault(name, scene_spec[name])
    try:
        scene_spec["_trace_events"] = build_manim_trace_events(
            topic_type, steps, duration, params,
        )
        code = generate_manim_python_code(
            topic_type=topic_type,
            scene_title=scene_title,
            steps=steps,
            target_duration=duration,
            custom_params=params,
        )
        validate_manim_template(topic_type, code, scene_spec["_trace_events"])
    except (TypeError, ValueError, KeyError) as error:
        print(f"[Manim Fallback] Invalid or unsupported algorithm trace for {chunk_id}: {error}")
        scene_spec["_fallback_reason"] = f"Invalid or unsupported algorithm trace: {error}"
        create_manim_fallback_slide(scene_title, steps, output_image)
        return output_image

    success = render_manim_to_mp4(
        scene_code=code,
        output_mp4=output_video,
        target_duration=duration,
        audio_path=audio_file
    )

    if success and os.path.isfile(output_video):
        try:
            scene_spec["_validation_evidence"] = validate_manim_trace_frames(
                output_video, scene_spec.get("_trace_events", []), duration,
            )
        except Exception as error:
            print(f"[Manim Fallback] Trace frame validation failed for {chunk_id}: {error}")
            scene_spec["_fallback_reason"] = f"Trace frame validation failed: {error}"
            success = False

    if success and os.path.isfile(output_video):
        print(f"[Manim OK] Rendered {chunk_id} to {output_video} ({duration:.2f}s)")
        # Also ensure a companion image exists for backward compatibility
        create_manim_fallback_slide(scene_title, steps, output_image)
        return output_video
    else:
        print(f"[Manim Fallback] Using static canvas slide for {chunk_id}")
        create_manim_fallback_slide(scene_title, steps, output_image)
        return output_image


def render_all_visual_scenes(run_dir: str, storyboard=None, visual_specs=None) -> List[str]:
    """
    Renders visual scenes for the run:
      1. Renders any Manim animation scenes on CPU (for scenes with visual_type == 'manim').
      2. Calls create_image_videos to build slide videos for static canvas scenes.
    Returns list of paths to generated video files in image_videos/.
    """
    from functions.create_image_videos_function import create_image_videos
    from functions.visual_routing import route_storyboard

    # Rendering is CPU and memory intensive; cap workers even when configuration is large.
    max_workers = visual_worker_limit()

    if storyboard:
        route_storyboard(storyboard)
    if storyboard and visual_specs is None:
        from functions.langgraph_pipeline import _validated_visual_specs
        visual_specs = _validated_visual_specs(storyboard)
    scenes = {scene.scene_id: scene for scene in storyboard.scenes} if storyboard else {}
    if storyboard and len(scenes) != len(storyboard.scenes):
        raise ValueError("Duplicate storyboard scene IDs")
    spec_by_id = validate_visual_spec_alignment(scenes, visual_specs) if storyboard else {}
    if not storyboard:
        # The legacy chunking path uses the same seg_N names without a storyboard.
        for filename in os.listdir(os.path.join(run_dir, "audio")):
            stem, extension = os.path.splitext(filename)
            if extension.lower() in (".wav", ".mp3"):
                if not stem.startswith("seg_") or not stem[4:].isdigit():
                    raise ValueError(f"Unsupported audio chunk ID: {stem}")
                scenes[int(stem[4:])] = None
    try:
        previous_manifest = load_visual_manifest(run_dir)
    except (OSError, ValueError, TypeError):
        previous_manifest = None
    previous_by_id = {
        item.scene_id: item for item in previous_manifest.scenes
    } if previous_manifest else {}
    manifest = VisualManifest(scenes=[
        VisualArtifact(
            scene_id=scene_id, artifact_id=f"seg_{scene_id}",
            requested_strategy=(
                getattr(scenes[scene_id], "visual_type", "pillow")
                if getattr(scenes[scene_id], "visual_type", "pillow") in {"manim", "web_image", "pillow", "hybrid_image", "hybrid_gif"}
                else "pillow"
            ),
            routing_rationale=getattr(scenes[scene_id], "visual_rationale", None),
            spec=spec_by_id.get(scene_id),
        )
        for scene_id in sorted(scenes)
    ])
    legacy_manifest_path = os.path.join(run_dir, "visual_manifest.json")
    legacy_records = {}
    if os.path.isfile(legacy_manifest_path):
        try:
            with open(legacy_manifest_path, encoding="utf-8") as stream:
                legacy_records = {f"seg_{record['scene_id']}": record for record in json.load(stream)}
            for artifact in manifest.scenes:
                record = legacy_records.get(artifact.artifact_id, {})
                scene = scenes.get(artifact.scene_id)
                image_path = os.path.join(run_dir, "images", f"{artifact.artifact_id}.jpg")
                provenance_matches = bool(
                    scene is not None
                    and record.get("scene_fingerprint") == visual_scene_fingerprint(scene)
                    and os.path.abspath(record.get("selected_image_path", "")) == os.path.abspath(image_path)
                    and os.path.isfile(image_path)
                    and record.get("slide_sha256") == file_sha256(image_path)
                    and record.get("image_search_used") is True
                )
                source_url = record.get("source_url")
                asset_url = record.get("asset_url")
                source_provider = record.get("selected_image_source")
                if (provenance_matches and source_url and asset_url and record.get("creator")
                        and record.get("license_id") and record.get("attribution")
                        and source_provider in {"pixabay", "wikimedia_commons", "unsplash", "pexels"}
                        and artifact.requested_strategy in {"web_image", "hybrid_image", "hybrid_gif"}):
                    artifact.source = ImageSource(
                        source_url=source_url, asset_url=asset_url,
                        creator=record.get("creator"), license_id=record.get("license_id"),
                        license_url=record.get("license_url"), attribution=record.get("attribution"),
                        retrieved_at=record.get("retrieved_at"),
                        semantic_score=record.get("similarity_score"),
                        quality_score=record.get("quality_score"),
                        required_feature_scores=record.get("required_feature_scores", {}),
                        excluded_feature_scores=record.get("excluded_feature_scores", {}),
                    )
                    artifact.actual_strategy = artifact.requested_strategy
        except (OSError, ValueError, KeyError, TypeError):
            pass
    save_visual_manifest(run_dir, manifest)
    def render_one(artifact_index):
        artifact = manifest.scenes[artifact_index]
        chunk_id = artifact.artifact_id
        scene = scenes[artifact.scene_id]
        if artifact.source:
            artifact.actual_strategy = artifact.requested_strategy
        audio_path = os.path.join(run_dir, "audio", f"{chunk_id}.wav")
        image_path = os.path.join(run_dir, "images", f"{chunk_id}.jpg")
        scene_identity = scene if scene is not None else {"scene_id": artifact.scene_id}
        artifact.cache_key = visual_cache_key(
            scene=scene_identity, audio_path=audio_path, image_path=image_path,
            image_identity=artifact.source.model_dump(mode="json") if artifact.source else None,
            strategy=artifact.requested_strategy,
        )
        previous = previous_by_id.get(artifact.scene_id)
        cached_path = os.path.join(run_dir, previous.output_path or "") if previous else ""
        cache_valid = bool(
            artifact.cache_key and previous and previous.cache_key == artifact.cache_key
            and previous.status in {"rendered", "accepted"}
            and previous.validation.semantic == "passed"
            and previous.validation.acceptance is not None
            and previous.validation.acceptance.verdict.value == "accepted"
            and previous.output_path == f"image_videos/{chunk_id}.mp4"
            and previous.sha256 and os.path.isfile(cached_path)
        )
        if cache_valid:
            try:
                cache_valid = (file_sha256(cached_path) == previous.sha256
                               and probe_visual_video(cached_path) == previous.media)
            except Exception:
                cache_valid = False
        if cache_valid:
            previous.cache_status = "hit"
            previous.elapsed_seconds = 0.0
            return previous, cached_path, None

        artifact.cache_status = "miss"
        render_started = time.perf_counter()
        budget = AttemptBudget(max_attempts=2)
        budget.begin()
        artifact.attempt_count = budget.attempts
        try:
            preserved = []
            scene_render_evidence = []
            artifact.actual_strategy = (
                artifact.requested_strategy
                if (artifact.source and artifact.requested_strategy in {"web_image", "hybrid_image", "hybrid_gif"})
                else "pillow"
            )
            legacy_record = legacy_records.get(chunk_id, {})
            slide_is_current = bool(
                scene is not None
                and legacy_record.get("scene_fingerprint") == visual_scene_fingerprint(scene)
                and os.path.abspath(legacy_record.get("selected_image_path", "")) == os.path.abspath(image_path)
                and os.path.isfile(image_path)
                and legacy_record.get("slide_sha256") == file_sha256(image_path)
            )
            if artifact.requested_strategy in {"web_image", "hybrid_image", "hybrid_gif"} and not artifact.source:
                artifact.fallback_reason = "No media passed validation; Pillow selected."
                title = getattr(scene, "on_screen_text", "") or getattr(scene, "key_concept", "Visual fallback")
                narration = getattr(scene, "narration", "") if scene else ""
                create_manim_fallback_slide(title, [part.strip() for part in narration.split(".") if part.strip()], image_path)
                scene_render_evidence.append("Pillow fallback generated from the current storyboard scene")
            elif artifact.requested_strategy in {"pillow", "hybrid_image", "hybrid_gif"}:
                if slide_is_current:
                    scene_render_evidence.append("Pillow slide provenance matches the current storyboard scene")
                else:
                    title = getattr(scene, "on_screen_text", "") or getattr(scene, "key_concept", "Visual fallback")
                    narration = getattr(scene, "narration", "") if scene else ""
                    create_manim_fallback_slide(
                        title, [part.strip() for part in narration.split(".") if part.strip()], image_path,
                    )
                    artifact.fallback_reason = "Unverified or stale Pillow slide replaced with a scene-specific fallback."
                    scene_render_evidence.append("Pillow fallback generated from the current storyboard scene")
            if artifact.requested_strategy == "manim":
                spec = getattr(scene, "manim_spec", None) or {
                    "topic_type": "bfs",
                    "scene_title": scene.on_screen_text or scene.key_concept,
                    "steps": ["A", "B", "C", "D", "E"],
                }
                spec = dict(spec)
                result = render_scene_manim(
                    spec, chunk_id, run_dir,
                    audio_path=audio_path,
                )
                artifact.trace_events = spec.pop("_trace_events", [])
                scene_render_evidence = spec.pop("_validation_evidence", [])
                if result.lower().endswith(".mp4"):
                    preserved.append(chunk_id)
                    artifact.actual_strategy = "manim"
                elif os.path.isfile(result) and result.lower().endswith((".jpg", ".jpeg", ".png")):
                    fallback_path = os.path.join(run_dir, "images", f"{chunk_id}.jpg")
                    if os.path.abspath(result) != os.path.abspath(fallback_path):
                        with Image.open(result) as fallback_image:
                            fallback_image.convert("RGB").save(fallback_path, "JPEG", quality=95)
                    artifact.actual_strategy = "pillow"
                    artifact.fallback_reason = spec.pop("_fallback_reason", "Manim rendering or normalization failed")
                    scene_render_evidence.append("Pillow fallback generated from the current storyboard scene")
                else:
                    title = getattr(scene, "on_screen_text", "") or getattr(scene, "key_concept", "Visual fallback")
                    steps = getattr(scene, "narration", "").split(".") if scene else []
                    fallback_path = os.path.join(run_dir, "images", f"{chunk_id}.jpg")
                    create_manim_fallback_slide(title, [step.strip() for step in steps if step.strip()], fallback_path)
                    artifact.actual_strategy = "pillow"
                    artifact.fallback_reason = spec.pop("_fallback_reason", "Manim rendering or normalization failed")
                    scene_render_evidence.append("Pillow fallback generated from the current storyboard scene")
            while True:
                try:
                    create_image_videos(run_dir, chunk_ids=[chunk_id], preserved_chunk_ids=preserved)
                    break
                except Exception as conversion_error:
                    retry_result = evaluate_checks([Check(
                        name="media", passed=False, reason_code="media_conversion_failed",
                        evidence=[str(conversion_error)], retryable=True,
                    )], budget)
                    artifact.attempts.append(retry_result)
                    if not budget.can_attempt:
                        raise
                    budget.begin()
                    artifact.attempt_count = budget.attempts
            relative_path = f"image_videos/{chunk_id}.mp4"
            video_path = os.path.join(run_dir, relative_path)
            artifact.media = probe_visual_video(video_path)
            artifact.sha256 = file_sha256(video_path)
            artifact.output_path = relative_path
            semantic_pass = (
                artifact.actual_strategy == "manim"
                and bool(artifact.trace_events)
                and bool(scene_render_evidence)
            ) or (
                artifact.actual_strategy in {"web_image", "hybrid_image", "hybrid_gif"}
                and bool(artifact.source and artifact.source.creator
                         and artifact.source.license_id and artifact.source.attribution)
            )
            if (artifact.actual_strategy == "pillow" and scene is not None
                    and (getattr(scene, "key_concept", "") or getattr(scene, "on_screen_text", ""))
                    and os.path.isfile(image_path)
                    and any("Pillow" in evidence for evidence in scene_render_evidence)):
                semantic_pass = True
            acceptance = evaluate_checks(candidate_checks(
                spec_valid=(scene is None or bool(getattr(scene, "narration", "")
                                                  and getattr(scene, "key_concept", ""))),
                media_valid=True,
                semantic_valid=True if semantic_pass else None,
                algorithm_valid=(bool(artifact.trace_events and scene_render_evidence)
                                 if artifact.actual_strategy == "manim" else None),
                source_eligible=(bool(artifact.source and artifact.source.creator
                                      and artifact.source.license_id and artifact.source.attribution)
                                 if artifact.actual_strategy in {"web_image", "hybrid_image", "hybrid_gif"} else None),
            ), budget)
            artifact.validation = VisualValidation(
                media="passed",
                semantic="passed" if semantic_pass else "uncertain",
                evaluator_version=acceptance.evaluator_version,
                evidence=["ffprobe media contract", *scene_render_evidence,
                          f"acceptance decision: {acceptance.decision.value}", "sha256 recorded"],
                acceptance=acceptance,
            )
            artifact.attempts.append(acceptance)
            if acceptance.verdict.value == "accepted":
                artifact.status = "accepted"
            else:
                artifact.status = "failed"
                artifact.error = "Visual acceptance was uncertain or rejected; scene excluded from composition."
        except Exception as error:
            artifact.status = "failed"
            artifact.error = str(error)
            failure_result = evaluate_checks(candidate_checks(
                spec_valid=(scene is None or bool(getattr(scene, "narration", "")
                                                  and getattr(scene, "key_concept", ""))),
                media_valid=False,
            ), budget, hard_failure=True)
            if artifact.attempts and artifact.attempts[-1].attempt == failure_result.attempt:
                artifact.attempts[-1] = failure_result
            else:
                artifact.attempts.append(failure_result)
            artifact.attempt_count = budget.attempts
            artifact.validation = VisualValidation(
                media="failed", semantic="uncertain",
                evaluator_version=failure_result.evaluator_version,
                evidence=[str(error), f"acceptance decision: {failure_result.decision.value}"],
                acceptance=failure_result,
            )
        artifact.elapsed_seconds = round(time.perf_counter() - render_started, 3)
        return artifact, (video_path if artifact.status in {"accepted", "rendered"} else None), (chunk_id if artifact.status == "failed" else None)

    indexed_results = {}
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="visual-scene") as pool:
        futures = {pool.submit(render_one, index): index for index in range(len(manifest.scenes))}
        try:
            for future in as_completed(futures):
                index = futures[future]
                try:
                    indexed_results[index] = future.result()
                except Exception as error:
                    artifact = manifest.scenes[index]
                    artifact.status = "failed"
                    artifact.error = str(error)
                    indexed_results[index] = (artifact, None, artifact.artifact_id)
        except BaseException:
            # Stop queued work; active render subprocesses also have bounded timeouts.
            for future in futures:
                future.cancel()
            raise

    rendered_files = []
    failures = []
    for index in range(len(manifest.scenes)):
        artifact, output, failure = indexed_results[index]
        manifest.scenes[index] = artifact
        if output:
            rendered_files.append(output)
        if failure:
            failures.append(failure)
        save_visual_manifest(run_dir, manifest)
    if failures:
        raise RuntimeError(f"Visual generation failed for {', '.join(failures)}; see visual_manifest.json")
    return rendered_files

