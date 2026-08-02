# 雾港来信示例项目

这个最小示例展示 Novel Writing 的项目组织方式：

- `story-bible.md` 保存核心设定、主题和创作边界。
- `outline/` 保存总体结构与作者维护的章节边界。
- `characters/` 和 `style/` 保存人物知识边界与叙述声音。
- `chapters/chapter-001.md` 提供一章带可引用锚点的示例正文。
- `continuity/` 保存由作者确认的结构化故事状态。
- `visualizations/` 可生成作者版和防剧透读者版 Dashboard。

查看状态：

```bash
python3 ../../scripts/project_status.py .
```

重新生成作者版 Dashboard：

```bash
python3 ../../scripts/render_dashboard.py . --mode author
```
