import json
import builtins
import types
from pathlib import Path

import pytest

from scripts import extract_style


def make_raw(tmp_path: Path) -> Path:
    raw = tmp_path / "styles" / "demo" / "raw"
    raw.mkdir(parents=True)
    (raw / "001-one.txt").write_text(
        "他轻轻地走进房间。\n\n“快看！”他说。她问：“真的吗？”\n",
        encoding="utf-8",
    )
    (raw / "002-two.txt").write_text(
        "夜色像墨一样沉。\n\n“当然。”她低声回答，眼里闪着光。\n",
        encoding="utf-8",
    )
    return raw


def test_split_sentences_and_dialogue_spans():
    text = "甲来了！乙问：‘你好吗？’丙走了……丁。"
    sentences = extract_style.split_sentences(text)
    assert sentences == ["甲来了！", "乙问：‘你好吗？’", "丙走了……", "丁。"]
    spans = extract_style.extract_dialogue_spans(text)
    assert [span[0] for span in spans] == ["‘你好吗？’"]


def test_metrics_exclude_four_dimensions_and_include_source_stats(tmp_path):
    raw = make_raw(tmp_path)
    metrics = extract_style.analyze_raw(raw)
    assert metrics["source"]["chapters"] == 2
    assert metrics["source"]["characters"] > 0
    assert metrics["excluded_dimensions"] == ["平均段长", "单句成段占比", "平均句长", "句长方差"]
    for key in metrics:
        assert key not in {"平均段长", "单句成段占比", "平均句长", "句长方差"}
    assert "description_vs_action" in metrics["dimensions"]
    assert "dialogue_tag_distribution" in metrics["dimensions"]
    assert "action_ratio" in metrics["dimensions"]["description_vs_action"]
    assert "summary_ratio" in metrics["dimensions"]["scene_vs_summary"]
    assert set(metrics["dimensions"]["figurative_frequency"]) >= {"simile", "parallelism", "rhetorical_question"}


def test_dialogue_tag_classifier_has_three_categories():
    text = '“好。”他说。\n“走吧。”她轻轻地笑着说。\n“嗯。”'
    result = extract_style.classify_dialogue_tags(text)
    assert set(result) >= {"pure_say", "complex_prompt", "unlabeled"}
    assert result["pure_say"] == 1
    assert result["complex_prompt"] == 1
    assert result["unlabeled"] == 1


def test_fixture_tendencies_are_predictable(tmp_path):
    raw = make_raw(tmp_path)
    metrics = extract_style.analyze_raw(raw)
    dims = metrics["dimensions"]
    assert dims["dialogue_narrative_ratio"]["tendency"] in {"medium", "high"}
    assert dims["lexical_richness"]["tendency"] in {"medium", "high"}
    assert dims["figurative_frequency"]["tendency"] == "medium"


def test_lexical_tokenizer_falls_back_when_jieba_is_missing(monkeypatch):
    original_import = builtins.__import__

    def without_jieba(name, *args, **kwargs):
        if name == "jieba":
            raise ImportError("optional dependency unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_jieba)
    tokens, method = extract_style._tokenize_for_richness("春风吹过")
    assert tokens == list("春风吹过")
    assert method == "cjk_char_fallback"


def test_lexical_tokenizer_uses_optional_jieba_when_available(monkeypatch):
    fake = types.SimpleNamespace(lcut=lambda value: ["春风", "吹过"])
    original_import = builtins.__import__

    def with_fake_jieba(name, *args, **kwargs):
        if name == "jieba":
            return fake
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", with_fake_jieba)
    tokens, method = extract_style._tokenize_for_richness("春风吹过")
    assert tokens == ["春风", "吹过"]
    assert method == "jieba"


def test_quote_candidates_are_short_per_chapter_and_do_not_cross_boundary(tmp_path):
    raw = make_raw(tmp_path)
    candidates = extract_style.extract_quote_candidates(raw, per_chapter=3, max_length=30)
    assert len(candidates) <= 6
    assert all(len(item["text"]) <= 30 for item in candidates)
    assert {item["chapter"] for item in candidates} <= {"001-one.txt", "002-two.txt"}
    assert all("\n" not in item["text"] for item in candidates)


def test_quote_candidates_do_not_join_unpunctuated_paragraphs(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "001.txt").write_text("甲段没有句号\n乙段也没有句号\n", encoding="utf-8")
    candidates = extract_style.extract_quote_candidates(raw, max_length=30)
    assert all(not ("甲段没有句号" in item["text"] and "乙段" in item["text"]) for item in candidates)


def test_generate_outputs_template_and_forms(tmp_path):
    raw = make_raw(tmp_path)
    out = tmp_path / "styles" / "demo"
    result = extract_style.extract_style(raw, out, title="Demo", author="Author")
    assert result["metrics"] == out / "metrics.json"
    template = (out / "template.md").read_text(encoding="utf-8")
    for heading in ("叙事层", "对话层", "量化辅助", "摘句锚点（待 agent 选择）", "版权与使用边界"):
        assert heading in template
    assert "TODO" in template
    assert "仅本地" in template
    for name in ("metrics.md", "quotes.md", "rules.md"):
        content = (out / "template-forms" / name).read_text(encoding="utf-8")
        assert "用途" in content and "输入槽位" in content and "禁止" in content
    json.loads((out / "quote_candidates.json").read_text(encoding="utf-8"))


def test_cli_end_to_end_and_repeat_is_safe(tmp_path):
    raw = make_raw(tmp_path)
    out = tmp_path / "styles" / "demo"
    assert extract_style.main(["--raw", str(raw), "--out", str(out), "--title", "Demo"]) == 0
    first = (out / "metrics.json").read_bytes()
    assert extract_style.main(["--raw", str(raw), "--out", str(out), "--title", "Demo"]) == 0
    assert (out / "metrics.json").read_bytes() == first
