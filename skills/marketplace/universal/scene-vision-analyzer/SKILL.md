---
name: scene-vision-analyzer
description: >
  Analyze game scene concept art / screenshots into structured JSON for 3D reconstruction.
  Extracts objects, spatial layout, camera parameters, lighting, perspective lines, and depth layers.
  Use when: (1) user provides a scene image and wants structured analysis for 3D scene building,
  (2) converting 2D concept art to UE/3D engine scene layout,
  (3) extracting object lists, positions, and spatial relationships from game art.
  Triggers: "分析场景", "场景原画分析", "scene analysis", "图片分析", "结构化分析", "2D to 3D".
---

# Scene Vision Analyzer

Analyze game scene concept art into structured JSON — the data foundation for 2D→3D reconstruction pipeline.

## Workflow

### Step 1: Prepare

1. Load the image (user provides path or URL)
2. Read `references/output-schema.json` for the full JSON schema
3. Read `references/analysis-prompts.md` for prompt templates

### Step 2: Run Analysis (Round 1 — Required)

Send the image to a multimodal AI with:
- **System prompt**: from `analysis-prompts.md` § System Prompt
- **User prompt**: from `analysis-prompts.md` § User Prompt, with `{schema}` replaced by `output-schema.json` content
- **Image**: attached as vision input

Parse the AI response as JSON. If the response is wrapped in markdown code blocks, strip them.

### Step 3: Refinement (Round 2 — Recommended)

Send the Round 1 result back with the refinement prompt from `analysis-prompts.md` § 第二轮细化 Prompt.

Focus: missed objects, bbox precision, ground_contact accuracy.

### Step 4: Consistency Validation (Round 3 — Optional)

Send the Round 2 result with the validation prompt from `analysis-prompts.md` § 第三轮一致性校验 Prompt.

Focus: size consistency, depth consistency, occlusion logic, shadow direction, group coherence.

### Step 5: Save Results

Use `scripts/scene_analyze.py` helper functions:
```python
from scene_analyze import save_result, generate_summary
# save_result(output_dir, json_string) → saves analysis_result.json + analysis_summary.txt
```

Or save manually:
- `analysis_result.json` — full structured result
- `analysis_summary.txt` — human-readable summary

Default output dir: `<image_dir>/scene_analysis_<timestamp>/`

## Quick Reference: Key Schema Fields

| Field | Purpose | Used by downstream |
|-------|---------|-------------------|
| `objects[].ground_contact_pct` | Where object touches ground | Step 3 (perspective → 3D coords) |
| `objects[].estimated_size_m` | Real-world size in meters | Step 3 (scale calibration) |
| `objects[].bbox_pct` | 2D bounding box (%) | Step 2 (annotation drawing) |
| `camera.pitch_angle_deg/yaw_angle_deg` | View angles | Step 3 (camera matrix) |
| `camera.horizon_position_pct` | Horizon line position | Step 3 (vanishing point) |
| `spatial_references.perspective_lines` | Depth cue lines | Step 3 (homography) |
| `spatial_references.vanishing_points_pct` | Convergence points | Step 3 (focal length est.) |
| `ground_plane.polygon_pct` | Ground area outline | Step 3 (ground plane fit) |
| `groups` | Repeated object patterns | Step 5 (batch placement) |

## Output Validation Checklist

Before passing results to the next pipeline step, verify:

- [ ] All coordinates are in 0–100 percentage range
- [ ] Every object has a unique semantic `id`
- [ ] `ground_contact_pct` exists for ground-touching objects
- [ ] `confidence` is filled for every object
- [ ] `analysis_meta.total_objects_identified` matches `objects` array length
- [ ] No fabricated objects (only what's visible in the image)

## CLI Usage (Dry Run / Prompt Generation)

```bash
python scripts/scene_analyze.py <image_path> --dry-run          # print prompts
python scripts/scene_analyze.py <image_path> -o ./output -r 3   # prep 3-round prompts
```

## Tips

- **Low-poly scenes**: Geometric edges are clear → perspective line detection is reliable, push for more `perspective_lines` entries
- **45° isometric views**: Strong geometric constraints → `pitch_angle_deg` ≈ -45, exploit this for Step 3
- **Dense scenes**: Run Round 2 refinement to catch small props hidden behind larger objects
- **Fog/particles**: Note in `analysis_meta.analysis_limitations` — these regions will have low confidence
