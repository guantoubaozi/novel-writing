# Contributing

感谢你改进 Novel Writing。

## 开始之前

- 先搜索已有 Issue，避免重复工作。
- 功能变更请说明它解决的作者问题和对现有项目格式的影响。
- 不要在测试、示例或 Issue 中提交真实未公开小说、个人信息或受版权保护的长篇文本。

## 本地验证

要求 Python 3.9 或更高版本。

```bash
python3 -m unittest discover -s tests -v
python3 /path/to/skill-creator/scripts/quick_validate.py .
```

## 设计原则

- 作者对正史拥有最终决定权。
- 推断和作者计划不能静默升级为 `confirmed`。
- 先报告矛盾，再提出修复。
- 默认保留原稿，不静默覆盖正文。
- 结构化数据写入必须先验证，并保持失败时不产生部分更新。
- 读者视图不能泄露作者专属、计划中或隐藏内容。
- `SKILL.md` 保持精简，把详细规则放进直接引用的 `references/` 文件。

## Pull Request

PR 请包含：

1. 变更动机和用户场景。
2. 行为变化与兼容性说明。
3. 新增或更新的测试。
4. 本地测试结果。
