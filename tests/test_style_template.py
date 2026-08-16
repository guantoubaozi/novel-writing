import json
from pathlib import Path

import pytest

from scripts import extract_style
from scripts import test_style_template


def make_raw(tmp_path: Path, count: int = 4) -> Path:
    raw = tmp_path / "styles" / "demo" / "raw"
    raw.mkdir(parents=True)
    texts = [
        "晨光落在窗边。\n\n‘快走！’他说。",
        "夜色像墨一样沉。\n\n她问：‘你还好吗？’",
        "风吹过街道，树影摇晃。\n\n‘当然。’她回答。",
        "雨声渐远，空气很冷。\n\n他轻轻地说：‘再见。’",
    ]
    for index, text in enumerate(texts[:count], 1):
        (raw / f"{index:03d}-chapter.txt").write_text(text, encoding="utf-8")
    return raw


def test_holdout_uses_last_two_and_respects_excluded(tmp_path):
    raw = make_raw(tmp_path)
    result = test_style_template.holdout_validation(raw)
    assert result["status"] == "ok"
    assert result["train_chapters"] == ["001-chapter.txt", "002-chapter.txt"]
    assert result["holdout_chapters"] == ["003-chapter.txt", "004-chapter.txt"]
    assert result["train_metrics"]["source"]["chapters"] == 2
    assert result["holdout_metrics"]["source"]["chapters"] == 2
    assert "平均段长" not in result["dimensions"]
    assert "description_vs_action" in result["dimensions"]
    assert {"train", "holdout", "relative_deviation", "status"} <= set(result["dimensions"]["description_vs_action"])


def test_holdout_fewer_than_three_is_structured_skipped(tmp_path):
    raw = make_raw(tmp_path, count=2)
    result = test_style_template.holdout_validation(raw)
    assert result["status"] == "skipped"
    assert "至少" in result["reason"]


def test_style_distance_identical_zero_and_different_positive(tmp_path):
    raw = make_raw(tmp_path)
    metrics = extract_style.analyze_raw(raw)
    assert test_style_template.style_distance(metrics, metrics)["quantitative_distance"] == 0
    changed = json.loads(json.dumps(metrics))
    changed["dimensions"]["lexical_richness"]["type_token_ratio"] = 0
    assert test_style_template.style_distance(metrics, changed)["quantitative_distance"] > 0


def test_style_distance_qualitative_pending_and_weighted():
    metrics = {"excluded_dimensions": [], "dimensions": {"x": {"value": 1}}}
    pending = test_style_template.style_distance(metrics, metrics)
    assert pending["qualitative_status"] == "pending_agent_judge"
    scored = test_style_template.style_distance(metrics, metrics, {"viewpoint": 0.8, "rhythm": 80})
    assert scored["qualitative_distance"] == pytest.approx(0.2)
    assert scored["weighted_total"] == pytest.approx(0.13)


def test_ab_ranking_is_stable_and_selects_best(tmp_path):
    raw = make_raw(tmp_path)
    style_dir = raw.parent
    reference = extract_style.analyze_raw(raw)
    (style_dir / "metrics.json").write_text(json.dumps(reference, ensure_ascii=False), encoding="utf-8")
    samples = {}
    for name in ("metrics", "quotes", "rules"):
        sample = tmp_path / f"{name}.txt"
        sample.write_text("晨光落在窗边。‘快走！’他说。" if name != "rules" else "完全不同的文字。", encoding="utf-8")
        samples[name] = sample
    result = test_style_template.evaluate_templates(style_dir, samples)
    assert list(result["leaderboard"]) == ["metrics", "quotes", "rules"]
    assert result["best_template"] == "metrics"


def test_cli_report_has_sections_without_raw_text(tmp_path):
    raw = make_raw(tmp_path)
    style_dir = raw.parent
    extract_style.extract_style(raw, style_dir)
    sample = tmp_path / "sample.txt"
    sample.write_text("机密原文不应进入报告。", encoding="utf-8")
    out = style_dir / "test-report.md"
    assert test_style_template.main([
        "--style-dir", str(style_dir),
        "--samples", f"metrics={sample}",
        "--samples", f"quotes={sample}",
        "--samples", f"rules={sample}",
        "--out", str(out),
    ]) == 0
    report = out.read_text(encoding="utf-8")
    assert "metrics" in report and "quotes" in report and "rules" in report
    assert "hold-out" in report
    assert "经验记录" in report
    assert "机密原文不应进入报告" not in report


def test_missing_samples_are_reported_not_crash(tmp_path):
    raw = make_raw(tmp_path)
    style_dir = raw.parent
    extract_style.extract_style(raw, style_dir)
    result = test_style_template.evaluate_templates(style_dir, {})
    assert result["templates"]["metrics"]["status"] == "missing"


def test_samples_dir_prefers_chapter_directory_then_same_name_file(tmp_path):
    raw = make_raw(tmp_path)
    style_dir = raw.parent
    extract_style.extract_style(raw, style_dir)
    samples_dir = tmp_path / "samples"
    samples_dir.mkdir()
    (samples_dir / "metrics").mkdir()
    (samples_dir / "metrics" / "001.txt").write_text("晨光落在窗边。", encoding="utf-8")
    (samples_dir / "quotes.txt").write_text("夜色像墨。", encoding="utf-8")
    (samples_dir / "rules").mkdir()
    (samples_dir / "rules.txt").write_text("风吹过街道。", encoding="utf-8")
    out = style_dir / "test-report.md"
    assert test_style_template.main(["--style-dir", str(style_dir), "--samples-dir", str(samples_dir), "--out", str(out)]) == 0
    report = out.read_text(encoding="utf-8")
    assert report.count("| ok |") == 3
