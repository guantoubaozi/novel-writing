# `/novel:style-import`：参考小说风格导入

> **本地样本与合规边界（先读）**：`raw/` 只存作者有权使用、获许可或公版的本地样本；不得把版权正文或长摘录分发、提交仓库或用于重建原作。成品只写可迁移的风格抽象；摘句仅作本地、极短的内部锚点。运行前仍须核对来源许可、版权、robots.txt 与网站 ToS。

本文对应 [scripts/fetch_novel.py](../scripts/fetch_novel.py)、[scripts/extract_style.py](../scripts/extract_style.py) 和 [scripts/test_style_template.py](../scripts/test_style_template.py)。命令示例均假定在 skill 根目录运行；示例只说明调用方式，不代表当前环境能够联网或某个站点一定可用。

## 1. 端到端路线

一次导入按下列顺序推进，任何网络步骤都可以被本地来源替代：

1. **检索并确认身份**：使用 `--search` 聚合候选，先核对书名、作者、来源和许可，再选择候选 ID。不能只凭搜索结果的标题猜测目标作品。
2. **取得四类输入之一**：网站抓取、作者自有 `txt`/`epub`/`md`、公版文本，或粘贴章节。四类输入最终都写入同一种 `styles/<slug>/raw/` 章节缓存。
3. **P2 抽取底稿**：`extract_style.py` 对缓存做确定性的轻量指标和摘句候选，写出 `metrics.json`、`quote_candidates.json`、`template.md` 骨架以及 `template-forms/`。
4. **Agent 定性阅读**：agent 阅读本地样本和量化底稿，填写叙事层、对话层的观察及固定 qualitative slots；脚本不替 agent 猜测视角、潜台词或审美结论。
5. **形成模板**：保留定性描述为主体，量化信号只作辅助；三种形态（`metrics`、`quotes`、`rules`）分别供回测使用。模板不携带可重建原作的长段正文。
6. **P3 验证闭环**：用末两章做 hold-out，用试写片段做 round-trip 风格距离，再对三种形态做同场景 A/B 盲评。`test-report.md` 记录榜单和暂定/最终状态。
7. **项目应用**：人工审核通过后，把抽象后的模板合并到目标项目的 `style/voice.md`。它是全书行文基线；现有 per-character voice 和 character-context 规则继续生效，不被覆盖。

建议保留每次导入的来源、许可核验、章节范围和模板版本记录，但不要把原文样本加入版本控制。

## 2. 选择输入来源

### 2.1 网站：检索、确认、抓取

`fetch_novel.py` 的网站流程是“多源检索 → 人工确认 → 目录/正文下载 → 净化 → 写本地缓存”。默认不附带任何网站书源；用户可按 schema 自行添加 HTML、Gutendex 或 MediaWiki 配置到 `scripts/booksources/`。书源可能失效，许可也可能变化，配置文件不是许可证明；不会默认访问维基文库或 Gutendex。

MediaWiki 搜索结果可能带有 `author_status=needs_manual_confirmation` 且 `author` 为空；请先人工确认作者，再传入 `--author`。脚本会拒绝缺少作者的 MediaWiki candidate ID，避免 slug 或身份误判。

先检索并把结果保存到终端或受控的本地记录中：

```bash
python3 scripts/fetch_novel.py \
  --search "书名或作者" \
  --sources scripts/booksources
```

确认输出的 `id`、书名、作者、`source` 和 URL 后，再下载指定区间（默认 `1-10`）：

```bash
python3 scripts/fetch_novel.py \
  --book "自定义书源名:确认后的候选ID" \
  --chapters 1-10 \
  --out styles/book--author/raw \
  --sources scripts/booksources
```

候选 ID 以实际 `--search` 输出为准，不要照抄示例 ID。脚本使用礼貌的 `User-Agent`（`novel-style-import/1.0 (local style analysis; respectful fetch)`）和书源配置的 `delay_ms`；遇到一个来源失败会尝试候选来源。无论脚本是否成功，都应遵守站点请求频率、API 政策、robots.txt 和 ToS，不绕过登录、付费墙、验证码或访问控制。

### 2.2 作者自有 `txt`/`epub`/`md`

本地文件通常是首选来源，不依赖网络：

```bash
python3 scripts/fetch_novel.py \
  --from-file /绝对路径/自己拥有的书.epub \
  --title "书名" --author "作者" \
  --chapters 1-10 \
  --out styles/book--author/raw
```

`txt`、`md` 按章节标题（如“第 N 章”或 `Chapter N`）切分；无法识别章节标题时会作为单章文本。`epub` 读取 spine 中的文档。只有在确实拥有相应使用权时，才把文件转换为样本缓存。

### 2.3 公版文本

公版并不等于所有版本、译本、排版或网站内容都没有限制；需分别确认文本版本和站点许可。可先用公版目录书源检索，再按“网站”步骤确认。确认手头已有许可文件时，也可以走 `--from-file`，这样更可复现。

### 2.4 粘贴章节

抓取失败、来源不稳定，或只需分析少量自有文本时，直接从标准输入粘贴：

```bash
pbpaste | python3 scripts/fetch_novel.py \
  --paste --title "本地参考" --author "作者" \
  --out styles/book--author/raw
```

也可以将编辑器选中的短章节通过管道传入；不要把第三方受限全文粘贴进共享环境。粘贴输入同样应满足版权和许可边界。

## 3. P2：确定性底稿与定性 Agent

### 3.1 脚本职责（确定性）

对 `raw/` 运行：

```bash
python3 scripts/extract_style.py \
  --raw styles/book--author/raw \
  --out styles/book--author \
  --title "书名" --author "作者"
```

脚本只做可重复的工作：净化后的章节读取、分句/分段、轻量量化统计、对白标签的粗分类、摘句候选排序，以及写出模板骨架。产物包括：

- `metrics.json`：§4.2 辅助指标和测量方法；
- `quote_candidates.json`：供 agent 选择的短句候选，不是可发布引文；
- `template.md`：等待定性填写的骨架；
- `template-forms/metrics.md`、`quotes.md`、`rules.md`：三种回测形态的输入边界。

脚本不宣称“读懂”作品，也不生成某本书的定性结论。

### 3.2 Agent 职责（定性）

Agent 必须先读 `raw/` 中的多章样本，再读 `metrics.json` 和候选短句，按 [style-template-model.md](style-template-model.md) 的固定 slots 填写：视角与距离、节奏质感、描写笔触、感官/意象、show/tell、语域/留白，以及对话标签、beat、潜台词、停顿。每项写“观察 → 证据类型 → 置信度/例外”，只写可迁移的抽象倾向。

量化底稿是校准线索，不是把数字改写成硬规则的授权。Agent 不得凭书名、常识或单个短句补写未观察到的结论，不得把角色口吻误写成作者整体对话基线，也不得复制长段原文。

## 4. P3：hold-out、round-trip 与 A/B

### 4.1 运行验证

准备三种形态各自生成的同场景试写样本（可用 `samples-dir` 或逐项 `NAME=PATH`），并准备 agent 填写的定性评分 JSON：

```bash
python3 scripts/test_style_template.py \
  --style-dir styles/book--author \
  --samples metrics=/tmp/style-ab/metrics.txt \
  --samples quotes=/tmp/style-ab/quotes.txt \
  --samples rules=/tmp/style-ab/rules.txt \
  --qualitative-scores /tmp/style-ab/qualitative-scores.json \
  --holdout 2 \
  --out styles/book--author/test-report.md
```

`--samples` 的路径只应指向本地试写文本或指标 JSON；同一场景、相近长度和相同人物设定才能让 A/B 有意义。若省略定性评分，报告会标记 `pending_agent_judge`，只能作 provisional 的量化排序，不能称为最终“最像”。

### 4.2 三个检查

- **Hold-out**：按章节文件顺序取最后两章作为留出集，其余章用于训练/抽模板；少于三章时结构化跳过。偏差大的辅助指标标记“未抓准”，应回到样本和定性描述复核。
- **Round-trip distance**：对试写文本跑同一套轻量指标，并与参考 `metrics.json` 做归一化距离；再由 agent 按固定 qualitative rubric 评分。定性权重高于量化（默认总距离为量化 35% + 定性 65%）。
- **A/B 盲评**：`metrics`、`quotes`、`rules` 三形态使用同一场景生成，评审时隐藏形态名称；脚本按完整定性评分后的加权总距离自动选优，并把榜单写入 `test-report.md`。定性未完成时只输出暂定榜单。

回测报告只写指标摘要、槽位分数和经验记录，不写入原文长段。经验记录应跨书、跨样本累积，不能把一次 A/B 结果夸大成普遍规律。

## 5. 失败切换与手动兜底

1. 某书源超时、解析器失配或返回空章节：保留错误提示，检查身份/许可后切换下一个书源；不要降低合规要求来“抓到”为止。
2. 所有自动来源失败：使用已核验的直接章节 URL 配合 `--from-url`，必要时传 `--selector` 和 `--title`：

   ```bash
   python3 scripts/fetch_novel.py \
     --from-url "https://example.invalid/owned-or-licensed/chapter" \
     --selector "article" --title "第 1 章" \
     --out styles/book--author/raw
   ```

3. URL 仍不可用或页面结构不稳定：改用自有文件 `--from-file` 或粘贴 `--paste`。手动 URL 是解析兜底，不是绕过访问控制的方法。
4. 没有足够章节做末两章留出：报告应明确 `skipped`，不要伪造验证通过；可以补充有权使用的章节后重跑。

## 6. 合规与隐私清单

- **样本留存**：`styles/<slug>/raw/` 仅本地使用，加入项目的忽略规则，不上传、发布或发给评审者；清理样本前确认模板和报告已不依赖正文。
- **成品形态**：`template.md`、`metrics.json`、`test-report.md` 只表达抽象倾向、粗略信号、槽位分数和方法；短摘句仅作为本地内部锚点，发布成品时应删除或改成非可识别的占位说明。
- **版权与 ToS**：抓取前确认授权/公版状态、站点许可、robots.txt、API 政策和请求上限；使用礼貌 UA 与延时，不并发轰击，不规避技术限制。
- **角色声线**：导入模板只设全书作者层的叙事/对话基线；不得覆盖既有 per-character voice、name-blind test 或 character-context 差异化机制。
- **联网限制**：开发沙箱或 CI 可能禁网；网络示例仅展示 CLI 合约，真实抓取请在作者本机、获许可的网络环境中验证。

## 7. 应用到项目

先人工审核 `template.md`、`metrics.json` 和 `test-report.md`，确认没有长引文、未经证实的结论或受限来源细节，再把**抽象描述**合并到目标项目的 `style/voice.md`。保留原有项目语音规则，并将导入模板标为“行文基线”；人物级 voice 继续由项目既有机制覆盖具体角色差异。
