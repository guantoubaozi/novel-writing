"""Extract a copyright-safe, lightweight style-analysis scaffold from raw chapters.

The script deliberately produces measurements and prompts for a later agent rather
than pretending to make qualitative style judgments.  Raw prose remains local.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union


EXCLUDED_DIMENSIONS = ["平均段长", "单句成段占比", "平均句长", "句长方差"]
_SENTENCE_END = set("。！？!?…；;")
_CLOSERS = set("”’」』\"'）)]】〉》")
_QUOTE_PAIRS = {"“": "”", "‘": "’", "「": "」", "『": "』", '"': '"', "'": "'"}
_SPEECH_VERBS = "说道说问答喊叫嚷吼表示回应回道嘟囔嘀咕低语喃喃宣布承认解释"
_DESCRIPTION_MARKERS = re.compile(r"像|如同|仿佛|犹如|颜色|声音|光芒|气息|香|冷|热|静|轻轻|巨大|细长|苍白|漆黑")
_ACTION_MARKERS = re.compile(r"走|跑|跳|拿|放|看|转|推|拉|打|挥|进入|离开|站|坐|抬|落|抓|追|说|问|答|喊")
_SCENE_MARKERS = re.compile(r"房间|门|窗|街|路|天|夜|晨|风|雨|树|山|河|光|声音|气味|空气|角落|远处")
_FIGURATIVE_MARKERS = re.compile(r"像|如同|仿佛|犹如|宛如|似的")
_QUESTION_RE = re.compile(r"[？?][”’」』\"']?$|难道|岂不是|怎么会")


def split_paragraphs(text: str) -> List[str]:
    """Return non-empty paragraphs without joining chapter boundaries."""
    return [part.strip() for part in re.split(r"\n+", text.replace("\r\n", "\n")) if part.strip()]


def split_sentences(text: str) -> List[str]:
    """Split Chinese prose while retaining sentence-ending punctuation and quotes."""
    value = re.sub(r"\s+", " ", text).strip()
    result: List[str] = []
    start = 0
    index = 0
    while index < len(value):
        if value[index] in _SENTENCE_END:
            end = index + 1
            while end < len(value) and value[end] in _SENTENCE_END:
                end += 1
            while end < len(value) and value[end] in _CLOSERS:
                end += 1
            chunk = value[start:end].strip()
            if chunk:
                result.append(chunk)
            start = end
            index = end
            continue
        index += 1
    tail = value[start:].strip()
    if tail:
        result.append(tail)
    return result


def extract_dialogue_spans(text: str) -> List[Tuple[str, int, int]]:
    """Extract paired Chinese/English quoted spans as ``(text, start, end)``."""
    spans: List[Tuple[str, int, int]] = []
    stack: List[Tuple[str, int]] = []
    for index, char in enumerate(text):
        if char in _QUOTE_PAIRS:
            if char in {"\"", "'"} and stack and stack[-1][0] == char:
                opening, start = stack.pop()
                spans.append((text[start : index + 1], start, index + 1))
            elif char in {"\"", "'"}:
                stack.append((char, index))
            else:
                stack.append((char, index))
        elif stack and _QUOTE_PAIRS.get(stack[-1][0]) == char:
            _, start = stack.pop()
            spans.append((text[start : index + 1], start, index + 1))
    spans.sort(key=lambda item: item[1])
    return spans


def _tag_for_span(text: str, end: int) -> str:
    following = text[end : end + 32]
    following = following.split("\n", 1)[0]
    following = re.split(r"[。！？!?；;]", following, maxsplit=1)[0]
    if not following.strip(" \t:：,，"):
        return "unlabeled"
    verb_match = re.search(rf"[{_SPEECH_VERBS}]", following)
    if not verb_match:
        return "unlabeled"
    prefix = following[: verb_match.start()].strip(" \t:：,，")
    suffix = following[verb_match.end() :].strip(" \t:：,，")
    if len(prefix) <= 2 and not suffix:
        return "pure_say"
    return "complex_prompt"


def classify_dialogue_tags(text: str) -> Dict[str, Any]:
    spans = extract_dialogue_spans(text)
    counts = {"pure_say": 0, "complex_prompt": 0, "unlabeled": 0}
    for _, _, end in spans:
        counts[_tag_for_span(text, end)] += 1
    total = len(spans)
    return {
        **counts,
        "total": total,
        "proportions": {key: round(value / total, 4) if total else 0.0 for key, value in counts.items()},
    }


def _tendency(value: float, *, high: float = 0.6, medium: float = 0.3) -> str:
    if value >= high:
        return "high"
    if value >= medium:
        return "medium"
    return "low"


def _ratio_metric(value: float, method: str, **extra: Any) -> Dict[str, Any]:
    return {"value": round(value, 4), "tendency": _tendency(value), "method": method, **extra}


def _chapter_records(raw_dir: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in sorted(raw_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        records.append({"name": path.name, "text": text, "paragraphs": split_paragraphs(text), "sentences": split_sentences(text)})
    return records


def _count_chars(value: str) -> int:
    return len(re.findall(r"[^\s]", value))


def _tokenize_for_richness(text: str) -> Tuple[List[str], str]:
    """Tokenize for the optional lexical metric without adding a dependency."""
    try:
        import jieba

        tokens = [token.strip() for token in jieba.lcut(text) if token.strip() and re.search(r"[\u4e00-\u9fffA-Za-z0-9]", token)]
        if tokens:
            return tokens, "jieba"
    except Exception:
        pass
    return re.findall(r"[\u4e00-\u9fff]", text), "cjk_char_fallback"


def analyze_raw(raw_dir: Union[Path, str]) -> Dict[str, Any]:
    raw_path = Path(raw_dir)
    records = _chapter_records(raw_path)
    all_text = "\n".join(item["text"] for item in records)
    compact = re.sub(r"\s", "", all_text)
    sentences = [sentence for item in records for sentence in item["sentences"]]
    paragraphs = [paragraph for item in records for paragraph in item["paragraphs"]]
    dialogue_spans = extract_dialogue_spans(all_text)
    dialogue_chars = sum(max(0, len(span[0]) - 2) for span in dialogue_spans)
    narrative_chars = max(0, len(compact) - dialogue_chars)
    total_chars = len(compact)

    description_chars = sum(len(sentence) for sentence in sentences if _DESCRIPTION_MARKERS.search(sentence))
    action_chars = sum(len(sentence) for sentence in sentences if _ACTION_MARKERS.search(sentence))
    scene_chars = sum(len(sentence) for sentence in sentences if _SCENE_MARKERS.search(sentence))
    simile_count = len(_FIGURATIVE_MARKERS.findall(compact))
    rhetorical_count = sum(1 for sentence in sentences if _QUESTION_RE.search(sentence))
    parallel_count = sum(1 for sentence in sentences if len(re.findall(r"[,，、]", sentence)) >= 2 and len(set(re.findall(r"[,，、]([^,，、]{1,8})", sentence))) <= 2)
    figurative_count = simile_count + parallel_count + rhetorical_count
    idiom_count = len(re.findall(r"[\u4e00-\u9fff]{4}", compact))
    richness_tokens, tokenizer_method = _tokenize_for_richness(compact)
    unique_cjk = len(set(richness_tokens))
    punctuation_counts = {"dash": compact.count("——") + compact.count("—"), "ellipsis": compact.count("……") + compact.count("…"), "exclamation": compact.count("！") + compact.count("!")}
    per_thousand = lambda count: round(count * 1000 / max(total_chars, 1), 4)
    tag_stats = classify_dialogue_tags(all_text)

    dimensions: Dict[str, Any] = {
        "description_vs_action": {
            "description_chars": description_chars,
            "action_chars": action_chars,
            "description_ratio": round(description_chars / max(description_chars + action_chars, 1), 4),
            "action_ratio": round(action_chars / max(description_chars + action_chars, 1), 4),
            "tendency": _tendency(description_chars / max(description_chars + action_chars, 1)),
            "method": "按感官/形容标记与动作动词命中句的字符数粗分；一段可同时命中。",
        },
        "scene_vs_summary": {
            "scene_chars": scene_chars,
            "summary_chars": max(0, total_chars - scene_chars),
            "scene_ratio": round(scene_chars / max(total_chars, 1), 4),
            "summary_ratio": round(max(0, total_chars - scene_chars) / max(total_chars, 1), 4),
            "tendency": _tendency(scene_chars / max(total_chars, 1)),
            "method": "按场所、时空、感官词命中句粗分，其余视为概述。",
        },
        "figurative_frequency": {
            "count": figurative_count,
            "per_sentence": round(figurative_count / max(len(sentences), 1), 4),
            "tendency": _tendency(figurative_count / max(len(sentences), 1), high=0.6, medium=0.1),
            "simile": {"count": simile_count, "per_sentence": round(simile_count / max(len(sentences), 1), 4), "tendency": _tendency(simile_count / max(len(sentences), 1), high=0.6, medium=0.1)},
            "parallelism": {"count": parallel_count, "per_sentence": round(parallel_count / max(len(sentences), 1), 4), "tendency": _tendency(parallel_count / max(len(sentences), 1), high=0.6, medium=0.1)},
            "rhetorical_question": {"count": rhetorical_count, "per_sentence": round(rhetorical_count / max(len(sentences), 1), 4), "tendency": _tendency(rhetorical_count / max(len(sentences), 1), high=0.6, medium=0.1)},
            "method": "统计像/如同/仿佛等比喻标记与疑问反问标记；排比仅作逗号重复结构的轻量近似。",
        },
        "idiom_density": {
            "count": idiom_count,
            "per_thousand_chars": per_thousand(idiom_count),
            "tendency": _tendency(idiom_count / max(total_chars / 1000, 1), high=8, medium=3),
            "method": "连续四个汉字作为成语候选，属于粗略上界。",
        },
        "punctuation_frequency": {
            **{key: {"count": count, "per_thousand_chars": per_thousand(count), "tendency": _tendency(count / max(total_chars / 1000, 1), high=8, medium=3)} for key, count in punctuation_counts.items()},
            "em_dash": {"count": punctuation_counts["dash"], "per_thousand_chars": per_thousand(punctuation_counts["dash"]), "tendency": _tendency(punctuation_counts["dash"] / max(total_chars / 1000, 1), high=8, medium=3)},
            "method": "按每千非空白字符统计破折号、略号、感叹号。",
        },
        "lexical_richness": {
            "types": unique_cjk,
            "tokens": len(richness_tokens),
            "type_token_ratio": round(unique_cjk / max(len(richness_tokens), 1), 4),
            "tendency": _tendency(unique_cjk / max(len(richness_tokens), 1), high=0.6, medium=0.35),
            "method": tokenizer_method,
        },
        "dialogue_narrative_ratio": {
            "dialogue_chars": dialogue_chars,
            "narrative_chars": narrative_chars,
            "ratio": round(dialogue_chars / max(narrative_chars, 1), 4),
            "tendency": _tendency(dialogue_chars / max(total_chars, 1), medium=0.15),
            "method": "引号成对内容字符数 / 非对白字符数；不把角色声线当作模板。",
        },
        "dialogue_tag_distribution": {
            **tag_stats,
            "tendency": {key: _tendency(value) for key, value in tag_stats["proportions"].items()},
            "method": "对白结束引号后 32 字内查找说话动词；短‘他说’归纯说，其余带修饰/动作归复杂提示语。",
        },
    }
    return {
        "schema_version": 1,
        "source": {"chapters": len(records), "files": len(records), "characters": total_chars, "paragraphs": len(paragraphs), "sentences": len(sentences)},
        "excluded_dimensions": list(EXCLUDED_DIMENSIONS),
        "dimensions": dimensions,
    }


def extract_quote_candidates(raw_dir: Union[Path, str], per_chapter: int = 3, max_length: int = 80) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for record in _chapter_records(Path(raw_dir)):
        scored: List[Tuple[float, str]] = []
        for paragraph in record["paragraphs"]:
            for sentence in split_sentences(paragraph):
                sentence = sentence.strip()
                if not sentence or len(sentence) > max_length:
                    continue
                score = float(len(re.findall(r"[“”‘’「」『』]", sentence)) * 3 + len(re.findall(r"像|仿佛|！|？|！", sentence)))
                score += min(len(sentence), 30) / 100
                scored.append((score, sentence))
        scored.sort(key=lambda item: (-item[0], item[1]))
        for score, sentence in scored[:per_chapter]:
            candidates.append({"chapter": record["name"], "text": sentence, "score": round(score, 4)})
    return candidates


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _template(title: str, author: str) -> str:
    label = "《%s》" % title if title else "（待填写书名）"
    byline = author or "（待填写作者）"
    return f"""# 风格模板底稿：{label}（{byline}）

> 本文件由脚本生成，定性结论必须由 agent 阅读 `raw/`、`metrics.json` 与 `quote_candidates.json` 后填写。请写风格抽象，不复制原文。

## 叙事层

TODO：填写视角与距离、自由间接引语、节奏质感、描写笔触、感官/意象、show/tell、语域、留白等 §4.1 观察。

## 对话层

TODO：填写作者整体对话基线（标签、beat、潜台词、语域、停顿）；不得覆盖角色 per-character voice。

## 量化辅助

参见 `metrics.json`。量化仅作粗略参照和回测信号，不是写作硬指标，也不包含被剔除的四项长度指标。

## 摘句锚点（待 agent 选择）

从 `quote_candidates.json` 中仅选择极短、必要的内部锚点；成品不得粘贴长段原文。

## 版权与使用边界

原文样本和候选摘句仅限本地（仅本地使用）、仅用于风格抽象与测试，不得分发或重建原作。发布/共享时只保留抽象描述；引用遵循适用的版权与合理使用边界。
"""


_FORM_CONTENT = {
    "metrics.md": """# 指标型模板骨架

## 用途
将 `metrics.json` 的粗略倾向转成写作检查清单与回测输入。

## 输入槽位
- 量化指标：`metrics.json`\n- 定性观察：`template.md` 的叙事层/对话层\n- 目标片段：待生成文本

## 禁止事项
不得把数值当硬约束，不得补写未观察到的风格结论，不得复制原文。
""",
    "quotes.md": """# 摘句锚点型模板骨架

## 用途
供 agent 从 `quote_candidates.json` 挑选极短内部锚点，辅助说明抽象规则。

## 输入槽位
- 候选：`quote_candidates.json`\n- 原文上下文：`raw/`（仅本地）\n- 抽象维度：`template.md`

## 禁止事项
不得选择跨段或过长片段，不得把候选原文写入分发成品，不得把人物声线当作者基线。
""",
    "rules.md": """# 规则指令型模板骨架

## 用途
把定性观察改写成可执行的写作/修订指令，并供回测复用。

## 输入槽位
- 风格观察：`template.md`\n- 辅助信号：`metrics.json`\n- 场景草稿：调用方提供

## 禁止事项
不得伪造定性结论，不得要求命中固定句长，不得覆盖角色 per-character voice 或分发原文。
""",
}


def extract_style(raw_dir: Union[Path, str], out_dir: Optional[Union[Path, str]] = None, *, title: str = "", author: str = "") -> Dict[str, Path]:
    raw_path = Path(raw_dir)
    output = Path(out_dir) if out_dir is not None else raw_path.parent
    output.mkdir(parents=True, exist_ok=True)
    metrics = analyze_raw(raw_path)
    candidates = extract_quote_candidates(raw_path)
    _atomic_write(output / "metrics.json", json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(output / "quote_candidates.json", json.dumps(candidates, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(output / "template.md", _template(title, author))
    for name, content in _FORM_CONTENT.items():
        _atomic_write(output / "template-forms" / name, content)
    return {"metrics": output / "metrics.json", "quotes": output / "quote_candidates.json", "template": output / "template.md"}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Extract local style metrics and template scaffolds")
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--title", default="")
    parser.add_argument("--author", default="")
    args = parser.parse_args(argv)
    extract_style(args.raw, args.out, title=args.title, author=args.author)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
