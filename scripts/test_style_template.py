"""Hold-out validation and template round-trip evaluation.

This module deliberately keeps prose out of reports.  It only reuses the
lightweight metrics produced by :mod:`extract_style` and leaves qualitative
judgement to an agent supplied score sheet.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

try:
    from .extract_style import EXCLUDED_DIMENSIONS, _atomic_write, analyze_raw
except ImportError:  # pragma: no cover - exercised by direct script invocation
    from extract_style import EXCLUDED_DIMENSIONS, _atomic_write, analyze_raw


TEMPLATES = ("metrics", "quotes", "rules")
QUALITATIVE_SLOTS = (
    "viewpoint",
    "rhythm",
    "description",
    "sensory_imagery",
    "show_tell",
    "register_ellipsis",
    "dialogue_subtext",
)
QUALITATIVE_LABELS = {
    "viewpoint": "视角距离",
    "rhythm": "节奏",
    "description": "描写笔触",
    "sensory_imagery": "感官/意象",
    "show_tell": "show/tell",
    "register_ellipsis": "语域/留白",
    "dialogue_subtext": "对话标签/beat/潜台词/停顿",
}
_QUALITATIVE_ALIASES = {
    "视角距离": "viewpoint", "视角": "viewpoint", "节奏": "rhythm",
    "描写笔触": "description", "感官/意象": "sensory_imagery",
    "感官意象": "sensory_imagery", "show/tell": "show_tell",
    "语域/留白": "register_ellipsis", "对话标签/beat/潜台词/停顿": "dialogue_subtext",
}


def _chapter_names(raw_dir: Path) -> List[str]:
    return [path.name for path in sorted(raw_dir.glob("*.txt")) if path.is_file() and not path.is_symlink()]


def _subset_metrics(raw_dir: Path, names: Sequence[str]) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="style-holdout-") as temporary:
        subset = Path(temporary)
        for name in names:
            source = raw_dir / name
            target = subset / name
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return analyze_raw(subset)


def _numeric_leaves(value: Any, prefix: str = "") -> Dict[str, float]:
    leaves: Dict[str, float] = {}
    if isinstance(value, Mapping):
        for key, item in value.items():
            key = str(key)
            if key in {"source", "stats", "method", "methods", "tendency", "excluded_dimensions"}:
                continue
            child = f"{prefix}.{key}" if prefix else key
            leaves.update(_numeric_leaves(item, child))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        leaves[prefix] = float(value)
    return leaves


def _dimension_value(dimension: Mapping[str, Any]) -> Tuple[Optional[float], Dict[str, float]]:
    leaves = _numeric_leaves(dimension)
    if not leaves:
        return None, leaves
    preferred = (
        "description_ratio", "scene_ratio", "per_sentence", "per_thousand_chars",
        "type_token_ratio", "ratio", "count", "dialogue_chars",
    )
    for suffix in preferred:
        for path, value in leaves.items():
            if path == suffix or path.endswith("." + suffix):
                return value, leaves
    return next(iter(leaves.values())), leaves


def holdout_validation(raw_dir: Union[Path, str], holdout: int = 2, threshold: float = 0.25) -> Dict[str, Any]:
    """Compare training chapters with the final ``holdout`` chapters."""
    raw_path = Path(raw_dir)
    names = _chapter_names(raw_path)
    if holdout < 1:
        return {"status": "skipped", "reason": "holdout 章数必须大于 0", "train_chapters": [], "holdout_chapters": []}
    if len(names) <= holdout:
        return {
            "status": "skipped",
            "reason": f"章节至少需要 {holdout + 1} 章，实际 {len(names)} 章",
            "train_chapters": names[:-holdout] if len(names) > holdout else [],
            "holdout_chapters": names[-holdout:] if names else [],
            "dimensions": {},
        }
    train_names, holdout_names = names[:-holdout], names[-holdout:]
    train_metrics = _subset_metrics(raw_path, train_names)
    holdout_metrics = _subset_metrics(raw_path, holdout_names)
    excluded = set(train_metrics.get("excluded_dimensions", EXCLUDED_DIMENSIONS)) | set(holdout_metrics.get("excluded_dimensions", EXCLUDED_DIMENSIONS))
    dimensions: Dict[str, Any] = {}
    train_dims = train_metrics.get("dimensions", {})
    holdout_dims = holdout_metrics.get("dimensions", {})
    dimension_names = list(train_dims)
    dimension_names.extend(name for name in holdout_dims if name not in train_dims)
    for name in dimension_names:
        if name in excluded or name in EXCLUDED_DIMENSIONS:
            continue
        train_value, train_leaves = _dimension_value(train_dims.get(name, {}))
        holdout_value, holdout_leaves = _dimension_value(holdout_dims.get(name, {}))
        if train_value is None or holdout_value is None:
            continue
        relative = abs(holdout_value - train_value) / max(abs(train_value), 1e-9)
        submetrics = {}
        for path in sorted(train_leaves.keys() & holdout_leaves.keys()):
            deviation = abs(holdout_leaves[path] - train_leaves[path]) / max(abs(train_leaves[path]), 1e-9)
            submetrics[path] = {"train": train_leaves[path], "holdout": holdout_leaves[path], "relative_deviation": round(deviation, 4)}
        dimensions[name] = {
            "train": train_value,
            "holdout": holdout_value,
            "relative_deviation": round(relative, 4),
            "status": "未抓准" if relative > threshold else "ok",
            "submetrics": submetrics,
        }
    return {
        "status": "ok",
        "train_chapters": train_names,
        "holdout_chapters": holdout_names,
        "train_metrics": train_metrics,
        "holdout_metrics": holdout_metrics,
        "dimensions": dimensions,
    }


validate_holdout = holdout_validation
compute_holdout = holdout_validation


def _coerce_metrics(metrics: Union[Mapping[str, Any], Path, str]) -> Mapping[str, Any]:
    if isinstance(metrics, (Path, str)):
        return json.loads(Path(metrics).read_text(encoding="utf-8"))
    return metrics


def _normalised_difference(reference: float, candidate: float) -> float:
    if reference == candidate:
        return 0.0
    return min(1.0, abs(candidate - reference) / max(abs(reference), abs(candidate), 1.0))


def _qualitative_scores(scores: Optional[Mapping[str, Any]]) -> Dict[str, float]:
    if not scores:
        return {}
    values = scores.get("slots", scores) if isinstance(scores, Mapping) else {}
    result: Dict[str, float] = {}
    for key, value in values.items():
        canonical = _QUALITATIVE_ALIASES.get(str(key), str(key))
        if canonical not in QUALITATIVE_SLOTS:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        result[canonical] = max(0.0, min(1.0, number / 100.0 if number > 1 else number))
    return result


def style_distance(reference_metrics: Mapping[str, Any], candidate_metrics: Mapping[str, Any], qualitative: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Return normalized quantitative and optional agent-judged distances."""
    reference = _coerce_metrics(reference_metrics)
    candidate = _coerce_metrics(candidate_metrics)
    excluded = set(reference.get("excluded_dimensions", EXCLUDED_DIMENSIONS)) | set(candidate.get("excluded_dimensions", EXCLUDED_DIMENSIONS))
    ref_dims, cand_dims = reference.get("dimensions", {}), candidate.get("dimensions", {})
    paths: Dict[str, Dict[str, float]] = {}
    for dimension in sorted(ref_dims.keys() & cand_dims.keys()):
        if dimension in excluded or dimension in EXCLUDED_DIMENSIONS:
            continue
        ref_leaves, cand_leaves = _numeric_leaves(ref_dims[dimension]), _numeric_leaves(cand_dims[dimension])
        for path in sorted(ref_leaves.keys() & cand_leaves.keys()):
            paths[f"{dimension}.{path}"] = {"reference": ref_leaves[path], "candidate": cand_leaves[path], "distance": _normalised_difference(ref_leaves[path], cand_leaves[path])}
    quantitative = sum(item["distance"] for item in paths.values()) / len(paths) if paths else 0.0
    result: Dict[str, Any] = {"quantitative_distance": round(quantitative, 6), "quantitative": paths}
    scores = _qualitative_scores(qualitative)
    result["qualitative_slots"] = {slot: {"label": QUALITATIVE_LABELS[slot], "similarity": scores[slot]} for slot in scores}
    result["qualitative_rubric"] = {
        slot: {"label": QUALITATIVE_LABELS[slot], "similarity": scores.get(slot), "status": "scored" if slot in scores else "pending"}
        for slot in QUALITATIVE_SLOTS
    }
    if scores:
        q_distance = sum(1.0 - score for score in scores.values()) / len(scores)
        result["qualitative_distance"] = round(q_distance, 6)
        result["qualitative_status"] = "ok" if len(scores) == len(QUALITATIVE_SLOTS) else "pending_agent_judge"
        result["weighted_total"] = round(quantitative * 0.35 + q_distance * 0.65, 6)
    else:
        result["qualitative_distance"] = None
        result["qualitative_status"] = "pending_agent_judge"
        result["weighted_total"] = None
    return result


def _metrics_for_sample(path: Path) -> Optional[Mapping[str, Any]]:
    if not path.exists() or path.is_symlink():
        return None
    if path.is_dir():
        if not any(path.glob("*.txt")):
            return None
        return analyze_raw(path)
    if path.suffix.lower() == ".json":
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    with tempfile.TemporaryDirectory(prefix="style-sample-") as temporary:
        sample = Path(temporary) / "sample.txt"
        sample.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        return analyze_raw(Path(temporary))


def evaluate_templates(style_dir: Union[Path, str], samples: Mapping[str, Union[Path, str]], qualitative_scores: Optional[Mapping[str, Any]] = None, holdout: int = 2) -> Dict[str, Any]:
    style_path = Path(style_dir)
    metrics_file = style_path / "metrics.json"
    reference = json.loads(metrics_file.read_text(encoding="utf-8")) if metrics_file.exists() else None
    if reference is None and (style_path / "raw").is_dir():
        reference = analyze_raw(style_path / "raw")
    scores = qualitative_scores or {}
    templates: Dict[str, Any] = {}
    for template in TEMPLATES:
        sample_value = samples.get(template)
        sample_path = Path(sample_value) if sample_value else None
        candidate = _metrics_for_sample(sample_path) if sample_path else None
        if reference is None or candidate is None:
            templates[template] = {"status": "missing", "distance": None}
            continue
        template_scores = scores.get(template) if isinstance(scores, Mapping) else None
        distance = style_distance(reference, candidate, template_scores)
        templates[template] = {"status": "ok", "distance": distance}
    available = [(name, item) for name, item in templates.items() if item.get("status") == "ok"]
    provisional = any(item["distance"].get("qualitative_status") != "ok" for _, item in available)
    def ranking_score(name: str) -> float:
        distance = templates[name]["distance"]
        if not provisional and distance.get("weighted_total") is not None:
            return float(distance["weighted_total"])
        return float(distance["quantitative_distance"])

    order = {name: index for index, name in enumerate(TEMPLATES)}
    leaderboard = sorted((name for name, _ in available), key=lambda name: (ranking_score(name), order[name]))
    best = leaderboard[0] if leaderboard else None
    holdout_result = holdout_validation(style_path / "raw", holdout=holdout) if (style_path / "raw").is_dir() else {"status": "skipped", "reason": "未找到 raw/ 章节目录", "dimensions": {}}
    return {"templates": templates, "leaderboard": leaderboard, "best_template": best, "provisional": provisional, "holdout": holdout_result, "reference_status": "ok" if reference is not None else "missing"}


evaluate_ab = evaluate_templates


def _report(result: Mapping[str, Any], style_dir: Path) -> str:
    lines = ["# 风格模板回测报告", "", f"- 来源：`{style_dir}`（仅指标摘要，不复制原文）", "", "## Hold-out（hold-out）", ""]
    holdout = result["holdout"]
    lines.append(f"- 状态：{holdout.get('status', 'skipped')}")
    if holdout.get("train_chapters") is not None:
        lines.append(f"- 训练章节：{', '.join(holdout.get('train_chapters', [])) or '无'}")
        lines.append(f"- 留出章节：{', '.join(holdout.get('holdout_chapters', [])) or '无'}")
    if holdout.get("reason"):
        lines.append(f"- 原因：{holdout['reason']}")
    for name, item in holdout.get("dimensions", {}).items():
        lines.append(f"- `{name}`：train={item['train']:.4g}, holdout={item['holdout']:.4g}, 偏差={item['relative_deviation']:.4g}，{item['status']}")
    lines.extend(["", "## 三形态盲评", "", "| 形态 | 状态 | 量化距离 | 定性状态 | 总距离 |", "|---|---|---:|---|---:|"])
    for name in TEMPLATES:
        item = result["templates"].get(name, {"status": "missing"})
        distance = item.get("distance") or {}
        lines.append(f"| {name} | {item.get('status', 'missing')} | {distance.get('quantitative_distance', '—')} | {distance.get('qualitative_status', 'pending_agent_judge')} | {distance.get('weighted_total') if distance.get('weighted_total') is not None else '—'} |")
        if distance:
            slots = distance.get("qualitative_slots", {})
            if slots:
                slot_text = "、".join(f"{value['label']}={value['similarity']:.4g}" for value in slots.values())
            else:
                slot_text = "、".join(QUALITATIVE_LABELS[slot] for slot in QUALITATIVE_SLOTS)
            lines.append(f"  - 定性槽位：{slot_text}")
    lines.extend(["", "## 总榜单", "", "- 排名：" + ("、".join(result.get("leaderboard", [])) or "暂无可评样本")])
    best = result.get("best_template") or "暂无"
    qualifier = "（定性待 agent 评审，当前为 provisional 量化排序）" if result.get("provisional") else ""
    lines.extend([f"- 自动选最优：{best} {qualifier}", "", "## 经验记录", "", "- 哪类形态整体更有效：待跨书/跨样本积累后填写。", "- 备注：定性槽位由 agent 填写，不由脚本伪造。", ""])
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate style template hold-out and A/B samples")
    parser.add_argument("--style-dir", required=True, type=Path)
    parser.add_argument("--samples", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--samples-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--holdout", type=int, default=2)
    parser.add_argument("--qualitative-scores", type=Path)
    args = parser.parse_args(argv)
    samples: Dict[str, Path] = {}
    for item in args.samples:
        if "=" not in item:
            continue
        name, value = item.split("=", 1)
        if name in TEMPLATES and value:
            samples[name] = Path(value)
    if args.samples_dir and args.samples_dir.is_dir():
        for name in TEMPLATES:
            if name in samples:
                continue
            candidates = [args.samples_dir / name]
            candidates.extend(sorted(args.samples_dir.glob(name + ".*")))
            for child in candidates:
                if child.is_dir() and not any(child.glob("*.txt")):
                    continue
                if child.exists():
                    samples[name] = child
                    break
    qualitative = json.loads(args.qualitative_scores.read_text(encoding="utf-8")) if args.qualitative_scores and args.qualitative_scores.exists() else None
    result = evaluate_templates(args.style_dir, samples, qualitative, holdout=args.holdout)
    output = args.out or (args.style_dir / "test-report.md")
    _atomic_write(output, _report(result, args.style_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
