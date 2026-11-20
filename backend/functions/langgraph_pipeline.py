"""
LangGraph Script Generation Pipeline.

Replaces the linear create_script() → create_storyboard() chain with a
stateful, conditional graph that:

  1. Classifies the topic (technical vs general) using LLM
  2. Routes to specialized script generation (technical scripts include
     Manim visual alignment cues)
  3. Conditionally plans Manim scenes for technical topics
  4. Generates a validated Storyboard with Manim specs embedded

Graph topology:
  START → classify_topic ─┬─ (technical) → generate_technical_script → plan_manim_scenes → generate_storyboard → END
                          └─ (general)   → generate_general_script ──────────────────────→ generate_storyboard → END
"""

import json
import re
import os
from typing import TypedDict, Optional, List, Dict, Any, Annotated

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage

from functions.llm_providers import invoke_with_fallback
from functions.create_script_function import sanitize_script_for_tts
from functions.storyboard_schema import Storyboard, Scene
from functions.create_storyboard_function import (
    generate_fallback_storyboard,
    _parse_and_validate,
)
from functions.cerebras_client import strip_markdown_code_fences


# ─────────────────────────────────────────────────────────────────────────────
# State Schema
# ─────────────────────────────────────────────────────────────────────────────

class PipelineState(TypedDict):
    """State flowing through the LangGraph script generation pipeline."""
    # ── Inputs ──
    topic_name: str
    level_of_explanation: str
    age: str
    creativity_level: str
    humour_level: str
    character_name: str

    # ── Classification ──
    is_technical: bool
    topic_type: str  # "bfs", "dfs", "sorting", "binary_search", "graph_traversal", "general"

    # ── Script ──
    script_text: str

    # ── Manim Planning (populated only for technical topics) ──
    manim_scenes: List[Dict[str, Any]]

    # ── Storyboard ──
    storyboard_json: str  # JSON string of validated Storyboard
    visual_plan: List[Dict[str, Any]]  # requested strategy and route rationale per scene
    visual_specs: List[Dict[str, Any]]  # validated, renderer-neutral scene specifications


# ─────────────────────────────────────────────────────────────────────────────
# Node 1: Topic Classification
# ─────────────────────────────────────────────────────────────────────────────

def classify_topic(state: PipelineState) -> dict:
    """
    Uses LLM to classify whether a topic is technical/algorithmic
    (suitable for Manim visualization) or general.

    Returns is_technical flag and topic_type for downstream routing.
    """
    topic = state["topic_name"]
    print(f"[LangGraph] [CLASSIFY] Classifying topic: '{topic}'")

    messages = [
        SystemMessage(content=(
            "You are a topic classifier for an educational video pipeline. "
            "Classify the given topic and respond with ONLY a JSON object.\n\n"
            "Classification rules:\n"
            "- 'technical' topics are: algorithms, data structures, graph traversal (BFS, DFS), "
            "sorting algorithms, search algorithms, tree operations, mathematical proofs, "
            "physics simulations, circuit diagrams, chemical reactions, state machines, "
            "finite automata, Turing machines, neural network architectures.\n"
            "- 'general' topics are: history, language, arts, business, social sciences, "
            "general knowledge, soft skills, cooking, sports, etc.\n\n"
            "topic_type values for technical: 'bfs', 'dfs', 'graph_traversal', 'tree_traversal', "
            "'binary_search', 'sorting', 'dynamic_programming', 'linked_list', 'stack_queue', "
            "'math_proof', 'physics_sim', 'neural_network', 'state_machine', 'generic_algorithm'\n"
            "topic_type for general: 'general'\n\n"
            "Output format: {\"is_technical\": true/false, \"topic_type\": \"...\"}"
        )),
        HumanMessage(content=f"Classify this topic: \"{topic}\""),
    ]

    try:
        response = invoke_with_fallback(messages, temperature=0.1, max_tokens=1500, json_mode=True)
        cleaned = strip_markdown_code_fences(response)
        result = json.loads(cleaned)
        is_tech = bool(result.get("is_technical", False))
        topic_type = result.get("topic_type", "general")
        print(f"[LangGraph] [OK] Classification: is_technical={is_tech}, topic_type={topic_type}")
        return {"is_technical": is_tech, "topic_type": topic_type}
    except Exception as e:
        print(f"[LangGraph] [WARN] Classification failed ({e}), falling back to regex patterns")
        # Fallback to the original regex-based detection
        from functions.create_script_function import is_technical_or_algorithmic_topic
        is_tech = is_technical_or_algorithmic_topic(topic)
        if is_tech:
            lower = topic.lower()
            if "bfs" in lower or "breadth" in lower:
                topic_type = "bfs"
            elif "dfs" in lower or "depth" in lower:
                topic_type = "dfs"
            elif "merge" in lower and "sort" in lower:
                topic_type = "merge_sort"
            elif "bubble" in lower and "sort" in lower:
                topic_type = "bubble_sort"
            elif "sort" in lower:
                topic_type = "sorting"
            elif "binary" in lower and "search" in lower:
                topic_type = "binary_search"
            elif "linear" in lower and "search" in lower:
                topic_type = "linear_search"
            else:
                topic_type = "graph_traversal"
        else:
            topic_type = "general"
        return {"is_technical": is_tech, "topic_type": topic_type}


# ─────────────────────────────────────────────────────────────────────────────
# Node 2a: Generate Technical Script (with Manim alignment cues)
# ─────────────────────────────────────────────────────────────────────────────

def _build_style_guidance(state: PipelineState) -> tuple:
    """Build level, creativity, and humour guidance strings from state."""
    level = state["level_of_explanation"]
    if level == "beginner":
        level_string = (
            "Explain this topic in simple, intuitive terms suitable for a beginner. "
            "Focus on foundational logic, intuitive concepts, and core importance."
        )
    elif level == "intermediate":
        level_string = (
            "Explain the topic with moderate depth and technical clarity. "
            "Cover underlying mechanisms, practical functionality, and key architecture details."
        )
    else:
        level_string = (
            "Provide an in-depth, comprehensive technical explanation. "
            "Delve into intricate architectural details, inner workings, and optimization trade-offs."
        )

    def _to_int(val, default=5):
        try:
            return int(val)
        except (ValueError, TypeError):
            mapping = {"low": 2, "medium": 5, "high": 8}
            return mapping.get(str(val).lower(), default)

    creativity = _to_int(state.get("creativity_level", 5), 8)
    humour = _to_int(state.get("humour_level", 5), 6)

    if creativity < 4:
        creativity_string = "Maintain a straightforward, direct explanatory approach."
    elif creativity < 7:
        creativity_string = "Use creative analogies and relatable real-world examples."
    else:
        creativity_string = "Use highly imaginative visual analogies, vibrant metaphors, and engaging mental pictures."

    if humour < 4:
        humour_string = "Keep the tone professional, clear, and informative."
    elif humour < 7:
        humour_string = "Incorporate a lighthearted, friendly humor to keep the viewer entertained."
    else:
        humour_string = "Add funny observations, witty remarks, and playful banter."

    return level_string, creativity_string, humour_string


def generate_technical_script(state: PipelineState) -> dict:
    """
    Generate a script for technical/algorithmic topics with explicit
    Manim visual alignment cues — step sequences stated in narration order
    so the animated visualization can sync with audio.
    """
    topic = state["topic_name"]
    character = state["character_name"]
    age = state["age"]
    topic_type = state.get("topic_type", "generic_algorithm")
    level_string, creativity_string, humour_string = _build_style_guidance(state)

    print(f"[LangGraph] [SCRIPT] Generating TECHNICAL script for '{topic}' (type: {topic_type})")

    messages = [
        SystemMessage(content=(
            f"You are {character}, an expert educator and captivating video tutorial narrator.\n"
            f"Output ONLY plain, spoken prose narration for Text-to-Speech.\n"
            f"Do NOT include markdown headers, bolding, bullet points, stage directions, or brackets."
        )),
        HumanMessage(content=(
            f"Write a SHORT, punchy video tutorial script explaining '{topic}' "
            f"tailored for a {age}-year-old audience.\n\n"
            f"ABSOLUTE LENGTH CONSTRAINT:\n"
            f"The ENTIRE script MUST be between 150 and 225 words total (60 to 90 seconds of spoken narration). "
            f"Be concise, direct, and impactful. Every sentence must earn its place.\n\n"
            f"NARRATIVE STRUCTURE (4 brief sections, flowing naturally as speech):\n"
            f"1. HOOK & INTRO: One attention-grabbing sentence, then a crisp definition of {topic} (2-3 sentences max).\n"
            f"2. CORE EXPLANATION: The essential 'what' and 'how' — cover only the most important concepts (3-4 sentences max).\n"
            f"3. STEP-BY-STEP WALKTHROUGH: Walk through a concrete example with labeled elements.\n"
            f"4. WRAP-UP: One punchy takeaway and a brief sign-off (1-2 sentences max).\n\n"
            f"CRITICAL — MANIM VISUAL ALIGNMENT INSTRUCTION:\n"
            f"An animated vector visualization will run on-screen in sync with your words.\n"
            f"In Section 3 (WALKTHROUGH), you MUST:\n"
            f"- Use concrete labeled elements (e.g., nodes A, B, C, D, E or array items 12, 24, 37).\n"
            f"- State the EXACT sequence of steps explicitly: 'We start at node A. Next, we visit B and C. "
            f"Then we move to D and E in level order.'\n"
            f"- The spoken order MUST match the exact visitation order so the animation highlights each element in sync.\n"
            f"- Use 5-7 labeled steps for a clear demonstration.\n\n"
            f"STYLE & TONAL GUIDELINES:\n"
            f"- {level_string}\n"
            f"- {creativity_string}\n"
            f"- {humour_string}\n"
            f"- Speak in first-person as {character} with an enthusiastic, encouraging voice.\n\n"
            f"CRITICAL FORMATTING RULES FOR TEXT-TO-SPEECH & WAV2LIP:\n"
            f"1. Output ONLY plain, raw spoken prose.\n"
            f"2. NEVER use markdown symbols: NO asterisks, hashtags, underscores, backticks, or bullet points.\n"
            f"3. No stage directions, camera instructions, or brackets.\n"
            f"4. No section headers. Use natural spoken transitions.\n"
            f"5. Conclude with: 'Sincerely, {character}.'\n"
            f"6. MAXIMUM 225 words. Count carefully.\n"
        )),
    ]

    try:
        raw_script = invoke_with_fallback(messages, temperature=0.3, max_tokens=4000)
        sanitized = sanitize_script_for_tts(raw_script)
        words = sanitized.split()
        if len(words) > 240:
            sanitized = " ".join(words[:240])
            last_period = sanitized.rfind(".")
            if last_period > len(sanitized) * 0.6:
                sanitized = sanitized[:last_period + 1]
        print(f"[LangGraph] [OK] Technical script generated ({len(sanitized.split())} words)")
        return {"script_text": sanitized}
    except Exception as e:
        print(f"[LangGraph] [ERROR] Technical script generation failed: {e}")
        raise


def generate_general_script(state: PipelineState) -> dict:
    """
    Generate a script for non-technical / general topics.
    Standard educational narration without Manim alignment cues.
    """
    topic = state["topic_name"]
    character = state["character_name"]
    age = state["age"]
    level_string, creativity_string, humour_string = _build_style_guidance(state)

    print(f"[LangGraph] [SCRIPT] Generating GENERAL script for '{topic}'")

    messages = [
        SystemMessage(content=(
            f"You are {character}, an expert educator and captivating video tutorial narrator.\n"
            f"Output ONLY plain, spoken prose narration for Text-to-Speech.\n"
            f"Do NOT include markdown headers, bolding, bullet points, stage directions, or brackets."
        )),
        HumanMessage(content=(
            f"Write a SHORT, punchy video tutorial script explaining '{topic}' "
            f"tailored for a {age}-year-old audience.\n\n"
            f"ABSOLUTE LENGTH CONSTRAINT:\n"
            f"The ENTIRE script MUST be between 150 and 225 words total (60 to 90 seconds of spoken narration). "
            f"Be concise, direct, and impactful. Every sentence must earn its place.\n\n"
            f"NARRATIVE STRUCTURE (4 brief sections, flowing naturally as speech):\n"
            f"1. HOOK & INTRO: One attention-grabbing sentence, then a crisp definition of {topic} (2-3 sentences max).\n"
            f"2. CORE EXPLANATION: The essential 'what' and 'how' (3-4 sentences max).\n"
            f"3. QUICK EXAMPLE OR ANALOGY: One vivid, relatable example or analogy (2-3 sentences max).\n"
            f"4. WRAP-UP: One punchy takeaway and a brief sign-off (1-2 sentences max).\n\n"
            f"STYLE & TONAL GUIDELINES:\n"
            f"- {level_string}\n"
            f"- {creativity_string}\n"
            f"- {humour_string}\n"
            f"- Speak in first-person as {character} with an enthusiastic, encouraging voice.\n\n"
            f"CRITICAL FORMATTING RULES FOR TEXT-TO-SPEECH & WAV2LIP:\n"
            f"1. Output ONLY plain, raw spoken prose.\n"
            f"2. NEVER use markdown symbols: NO asterisks, hashtags, underscores, backticks, or bullet points.\n"
            f"3. No stage directions, camera instructions, or brackets.\n"
            f"4. No section headers. Use natural spoken transitions.\n"
            f"5. Conclude with: 'Sincerely, {character}.'\n"
            f"6. MAXIMUM 225 words. Count carefully.\n"
        )),
    ]

    try:
        raw_script = invoke_with_fallback(messages, temperature=0.3, max_tokens=4000)
        sanitized = sanitize_script_for_tts(raw_script)
        words = sanitized.split()
        if len(words) > 240:
            sanitized = " ".join(words[:240])
            last_period = sanitized.rfind(".")
            if last_period > len(sanitized) * 0.6:
                sanitized = sanitized[:last_period + 1]
        print(f"[LangGraph] [OK] General script generated ({len(sanitized.split())} words)")
        return {"script_text": sanitized}
    except Exception as e:
        print(f"[LangGraph] [ERROR] General script generation failed: {e}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Node 3: Plan Manim Scenes (conditional — technical topics only)
# ─────────────────────────────────────────────────────────────────────────────

def plan_manim_scenes(state: PipelineState) -> dict:
    """
    Uses LLM to generate structured Manim scene specifications from the
    technical script. Extracts labeled steps, node/edge topology, and
    animation parameters that the manim_renderer will consume.

    This is the key Manim-as-a-tool integration: the LLM reads the script
    and plans exactly which elements to animate in which order.
    """
    topic = state["topic_name"]
    topic_type = state.get("topic_type", "generic_algorithm")
    script = state["script_text"]

    print(f"[LangGraph] [MANIM] Planning Manim scenes for '{topic}' (type: {topic_type})")

    messages = [
        SystemMessage(content=(
            "You are a Manim animation planner for educational videos. "
            "Given a technical script, extract the step-by-step walkthrough and convert it "
            "into structured Manim scene specifications.\n\n"
            "Output a JSON object with key \"manim_scenes\" containing an array of scene specs.\n"
            "Each scene spec has:\n"
            "- \"topic_type\": one of 'bfs', 'dfs', 'graph_traversal', 'tree_traversal', "
            "'binary_search', 'linear_search', 'merge_sort', 'bubble_sort', 'sorting', 'dynamic_programming', 'generic_algorithm'\n"
            "- \"scene_title\": short title for the animation (max 50 chars)\n"
            "- \"steps\": array of labeled elements in visitation ORDER as spoken in the script "
            "(e.g., [\"A\", \"B\", \"C\", \"D\", \"E\"] for graph nodes, or [\"12\", \"24\", \"37\"] for array values)\n"
            "- \"nodes\": array of all node labels in the visualization\n"
            "- \"edges\": array of [source, target] pairs for graph/tree topics (empty for arrays)\n"
            "- \"params\": optional dict with extra params (e.g., {\"values\": [12, 24, 37, 45]} for sorting)\n\n"
            "RULES:\n"
            "- Extract steps in the EXACT order they appear in the narration\n"
            "- For graph topics, infer edges from the walkthrough context\n"
            "- Usually 1 Manim scene per script, but allow up to 2 if the script has distinct visual phases\n"
            "- Output ONLY the JSON object, no markdown\n"
        )),
        HumanMessage(content=(
            f"Topic: {topic}\nTopic Type: {topic_type}\n\n"
            f"Script:\n{script}\n\n"
            f"Extract the Manim scene specification(s)."
        )),
    ]

    try:
        response = invoke_with_fallback(messages, temperature=0.1, max_tokens=2000, json_mode=True)
        cleaned = strip_markdown_code_fences(response)
        result = json.loads(cleaned)
        scenes = result.get("manim_scenes", [])
        if not scenes and isinstance(result, list):
            scenes = result

        # Validate each scene has required fields
        validated_scenes = []
        for scene in scenes:
            validated_scenes.append({
                "topic_type": scene.get("topic_type", topic_type),
                "scene_title": scene.get("scene_title", f"{topic} Animation")[:50],
                "steps": scene.get("steps", ["A", "B", "C", "D", "E"]),
                "nodes": scene.get("nodes", scene.get("steps", ["A", "B", "C", "D", "E"])),
                "edges": scene.get("edges", [["A", "B"], ["A", "C"], ["B", "D"], ["B", "E"]]),
                "params": scene.get("params", {}),
            })

        if not validated_scenes:
            # Fallback: create a default scene spec
            validated_scenes = [{
                "topic_type": topic_type,
                "scene_title": f"{topic[:40]} Animation",
                "steps": ["A", "B", "C", "D", "E"],
                "nodes": ["A", "B", "C", "D", "E"],
                "edges": [["A", "B"], ["A", "C"], ["B", "D"], ["B", "E"]],
                "params": {},
            }]

        print(f"[LangGraph] [OK] Planned {len(validated_scenes)} Manim scene(s)")
        return {"manim_scenes": validated_scenes}
    except Exception as e:
        print(f"[LangGraph] [WARN] Manim planning failed ({e}), using default scene spec")
        return {
            "manim_scenes": [{
                "topic_type": topic_type,
                "scene_title": f"{topic[:40]} Animation",
                "steps": ["A", "B", "C", "D", "E"],
                "nodes": ["A", "B", "C", "D", "E"],
                "edges": [["A", "B"], ["A", "C"], ["B", "D"], ["B", "E"]],
                "params": {},
            }]
        }


# ─────────────────────────────────────────────────────────────────────────────
# Node 4: Generate Storyboard
# ─────────────────────────────────────────────────────────────────────────────

_STORYBOARD_PROMPT = """You are a professional educational video storyboard planner.
Given the topic "{topic_name}" and the script below, create a teaching storyboard.

RULES:
- Split the script into 3 to 8 scenes. Preserve the script's teaching order.
- Use ONLY facts from the script. Do NOT add unsupported claims.
- Each scene's narration must be self-contained, speakable prose (no markdown).
- visual_query must describe a concrete educational image or diagram.
- estimated_seconds should reflect spoken word count (~2.5 words/second).
{manim_instruction}

OUTPUT FORMAT (strict JSON object):
{{
  "title": "...",
  "scenes": [
    {{
      "scene_id": 0,
      "key_concept": "...",
      "narration": "...",
      "visual_query": "...",
      "on_screen_text": "...",
      "estimated_seconds": 20,
      "visual_type": "slide",
      "manim_spec": null
    }}
  ]
}}

SCRIPT:
{script}
"""

_MANIM_STORYBOARD_INSTRUCTION = """
- This is a TECHNICAL topic with Manim animation support.
- For the scene(s) that demonstrate the algorithm/concept walkthrough, set:
  "visual_type": "manim"
  "manim_spec": (the Manim scene spec provided below)
- For non-walkthrough scenes (intro, conclusion), use:
  "visual_type": "slide"
  "manim_spec": null

MANIM SCENE SPECS TO EMBED:
{manim_specs_json}
"""


def generate_storyboard(state: PipelineState) -> dict:
    """
    Generate a validated Storyboard from script text, with Manim scene
    specs injected for technical topics.

    Falls back through: LLM → repair → deterministic chunker.
    """
    topic = state["topic_name"]
    script = state["script_text"]
    is_technical = state.get("is_technical", False)
    manim_scenes = state.get("manim_scenes", [])

    print(f"[LangGraph] [STORYBOARD] Generating storyboard for '{topic}' (technical={is_technical})")

    # Build Manim instruction if applicable
    manim_instruction = ""
    if is_technical and manim_scenes:
        manim_instruction = _MANIM_STORYBOARD_INSTRUCTION.format(
            manim_specs_json=json.dumps(manim_scenes, indent=2)
        )

    prompt = _STORYBOARD_PROMPT.format(
        topic_name=topic,
        script=script,
        manim_instruction=manim_instruction,
    )

    messages = [
        SystemMessage(content="You are an expert storyboard planner that outputs valid JSON matching the exact schema."),
        HumanMessage(content=prompt),
    ]

    # Attempt 1: LLM generation
    try:
        raw_json = invoke_with_fallback(messages, temperature=0.2, max_tokens=3500, json_mode=True)
        if raw_json:
            try:
                storyboard = _parse_and_validate(raw_json)
                print(f"[LangGraph] [OK] Storyboard generated: {len(storyboard.scenes)} scenes")
                return {"storyboard_json": storyboard.model_dump_json(indent=2)}
            except Exception as first_error:
                print(f"[LangGraph] [WARN] Storyboard validation failed: {first_error}, attempting repair...")

                # Repair attempt
                repair_messages = [
                    SystemMessage(content="You are an expert storyboard planner that outputs valid JSON matching the exact schema."),
                    HumanMessage(content=(
                        f"{prompt}\n\n"
                        f"The previous JSON output failed validation with this error:\n{first_error}\n\n"
                        f"Please fix the JSON and return ONLY a corrected JSON object matching the exact schema.\n"
                        f"Remember: scene_id values must start at 0 and be contiguous (0, 1, 2, ...).\n"
                        f"All string fields must be non-empty. estimated_seconds must be between 3 and 90."
                    )),
                ]
                try:
                    repair_json = invoke_with_fallback(repair_messages, temperature=0.1, max_tokens=3500, json_mode=True)
                    storyboard = _parse_and_validate(repair_json)
                    print(f"[LangGraph] [OK] Storyboard repaired: {len(storyboard.scenes)} scenes")
                    return {"storyboard_json": storyboard.model_dump_json(indent=2)}
                except Exception as repair_error:
                    print(f"[LangGraph] [WARN] Repair also failed: {repair_error}")
    except Exception as e:
        print(f"[LangGraph] [WARN] LLM storyboard generation failed: {e}")

    # Fallback: deterministic chunker
    print("[LangGraph] [FALLBACK] Falling back to deterministic storyboard generation")
    storyboard = generate_fallback_storyboard(topic, script)

    # Inject Manim specs into fallback storyboard if we have them
    if is_technical and manim_scenes and storyboard.scenes:
        # Find the walkthrough scene (typically scene 1 or 2)
        target_idx = min(1, len(storyboard.scenes) - 1)
        scene = storyboard.scenes[target_idx]
        scene.visual_type = "manim"
        scene.manim_spec = manim_scenes[0] if manim_scenes else None

    return {"storyboard_json": storyboard.model_dump_json(indent=2)}


# ─────────────────────────────────────────────────────────────────────────────
# Routing Function
# ─────────────────────────────────────────────────────────────────────────────

def route_by_topic_type(state: PipelineState) -> str:
    """Conditional edge: route to technical or general script generation."""
    if state.get("is_technical", False):
        return "generate_technical_script"
    return "generate_general_script"


# ─────────────────────────────────────────────────────────────────────────────
# Graph Construction
# ─────────────────────────────────────────────────────────────────────────────

def build_script_graph() -> StateGraph:
    """
    Construct the LangGraph StateGraph for the script generation pipeline.

    Returns a compiled graph ready for invocation.
    """
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("classify_topic", classify_topic)
    graph.add_node("generate_technical_script", generate_technical_script)
    graph.add_node("generate_general_script", generate_general_script)
    graph.add_node("plan_manim_scenes", plan_manim_scenes)
    graph.add_node("generate_storyboard", generate_storyboard)
    graph.add_node("plan_visuals", plan_visuals)

    # Add edges
    graph.add_edge(START, "classify_topic")

    # Conditional routing after classification
    graph.add_conditional_edges(
        "classify_topic",
        route_by_topic_type,
        {
            "generate_technical_script": "generate_technical_script",
            "generate_general_script": "generate_general_script",
        },
    )

    # Technical path: script → Manim planning → storyboard
    graph.add_edge("generate_technical_script", "plan_manim_scenes")
    graph.add_edge("plan_manim_scenes", "generate_storyboard")

    # General path: script → storyboard (skip Manim)
    graph.add_edge("generate_general_script", "generate_storyboard")

    # Storyboard → visual plan → END. Rendering waits for audio/run-dir creation downstream.
    graph.add_edge("generate_storyboard", "plan_visuals")
    graph.add_edge("plan_visuals", END)

    return graph.compile()


def plan_visuals(state: PipelineState) -> dict:
    """Persist per-scene route decisions in graph state after storyboard validation."""
    from functions.visual_routing import route_storyboard

    storyboard = Storyboard.model_validate_json(state["storyboard_json"])
    route_storyboard(storyboard)
    return {
        "storyboard_json": storyboard.model_dump_json(),
        "visual_plan": [
            {
                "scene_id": scene.scene_id,
                "strategy": scene.visual_type,
                "rationale": scene.visual_rationale,
            }
            for scene in storyboard.scenes
        ],
        "visual_specs": _validated_visual_specs(storyboard),
    }


def _validated_visual_specs(storyboard: Storyboard) -> List[Dict[str, Any]]:
    """Build the shared VisualSpec contract from routed storyboard scenes."""
    from functions.visual_spec import validate_visual_spec

    specs = []
    for scene in storyboard.scenes:
        spec, repaired = validate_visual_spec({
            "scene_id": scene.scene_id,
            "topic": scene.key_concept,
            "visual_goal": scene.learning_objective or scene.visual_query or scene.key_concept,
            "visual_type": scene.visual_type if scene.visual_type in {"manim", "web_image", "pillow", "hybrid_image", "hybrid_gif"} else "pillow",
            "duration_seconds": scene.estimated_seconds,
            "width": 1280,
            "height": 720,
            "fps": 25,
            "input_data": scene.manim_spec or {"query": scene.visual_query},
            "must_show": scene.must_show or [scene.key_concept],
            "must_not_show": scene.must_not_show,
        })
        specs.append(spec.model_dump(mode="json"))
    return specs


# ─────────────────────────────────────────────────────────────────────────────
# Public Entry Point
# ─────────────────────────────────────────────────────────────────────────────

# Compile once at module load
_COMPILED_GRAPH = None


def _get_graph():
    """Lazy-initialize the compiled graph singleton."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_script_graph()
    return _COMPILED_GRAPH


def run_script_pipeline(
    topic_name: str,
    level_of_explanation: str,
    age: str,
    creativity_level: str,
    humour_level: str,
    character_name: str = "Tutor",
    *,
    return_state: bool = False,
) -> tuple:
    """
    Run the LangGraph script generation pipeline.

    This is the main entry point that replaces the old
    create_script() + create_storyboard() sequential calls.

    Returns:
        By default, (script_text, storyboard). With return_state=True,
        returns (script_text, storyboard, final_state).
    """
    print(f"\n{'='*60}")
    print(f"[LangGraph Pipeline] Starting for topic: '{topic_name}'")
    print(f"{'='*60}\n")

    graph = _get_graph()

    initial_state = {
        "topic_name": topic_name,
        "level_of_explanation": level_of_explanation,
        "age": str(age),
        "creativity_level": str(creativity_level),
        "humour_level": str(humour_level),
        "character_name": character_name,
        "is_technical": False,
        "topic_type": "general",
        "script_text": "",
        "manim_scenes": [],
        "storyboard_json": "",
        "visual_plan": [],
        "visual_specs": [],
    }

    # Run the graph synchronously
    final_state = graph.invoke(initial_state)

    script_text = final_state["script_text"]
    storyboard_json = final_state["storyboard_json"]

    # Parse storyboard JSON back into Pydantic model
    storyboard = Storyboard.model_validate_json(storyboard_json)

    print(f"\n{'='*60}")
    print(f"[LangGraph Pipeline] Complete!")
    print(f"  Script: {len(script_text.split())} words")
    print(f"  Storyboard: {len(storyboard.scenes)} scenes")
    print(f"  Technical: {final_state['is_technical']} ({final_state['topic_type']})")
    print(f"  Manim Scenes: {len(final_state.get('manim_scenes', []))}")
    print(f"{'='*60}\n")

    if return_state:
        return script_text, storyboard, final_state
    return script_text, storyboard
