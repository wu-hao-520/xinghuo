---
name: classroom-audio-evaluation
description: 基于课堂录音自动生成结构化听评课评估报告，支持多格式音频转写、星火标准三维度评估、学情适配与考情对标诊断，以及Word/PDF/Markdown多格式报告导出；当用户提供课堂录音要求生成听评课建议、进行教学评价分析或批量处理录音文件时使用
dependency:
  python:
    - openai-whisper
    - python-docx
    - reportlab
    - openai
    - matplotlib
    - pillow
  system:
    - ffmpeg
---

# 课堂录音听评课工作流

## 任务目标
- 本 Skill 用于: 将课堂录音转化为专业的听评课建议报告
- 能力包含: 多格式音频转写、星火标准三维度评估、学情适配与考情对标诊断、多格式报告生成与导出
- 触发条件: 用户提供课堂录音文件要求生成听评课建议、进行教学评价分析

## 需收集的信息（除录音外）

为完成学情适配与考情对标诊断，应向用户确认以下信息（缺失时跳过对应诊断维度，并在报告中标注"信息未提供"）:

- **基础信息**: 教师姓名、学生姓名、课程名称、年级/学段（小学/初中/高中）、课型（新授课/习题讲评/错题讲评/复习课，可由转写内容自动推断）
- **学生成绩**（用于学情适配诊断）: 该生本学科最近一次考试成绩（分数 + 满分）、班级/年级排名或百分位
- **考情信息**（用于考情对标诊断）: 学科 + 学段 + 章节知识点（可由转写内容自动推断，无需用户额外提供）

> 学段 + 科目 + 课型共同决定"评课路径"，多路径适配与路由规则见 [references/path_routing.md](references/path_routing.md)。

## 前置准备
- 依赖安装:
  ```bash
  pip install openai-whisper python-docx reportlab openai
  # 安装 ffmpeg（音频处理）
  # macOS: brew install ffmpeg
  # Linux: apt-get install ffmpeg
  ```
- 云端转写需设置环境变量: `OPENAI_API_KEY=sk-...`（可选，本地 Whisper 无需此配置）

## 运行环境避坑（Windows 中文编码）

> 在 Windows 上执行命令时，含中文的**命令行参数/路径**会因控制台 GBK 与 UTF-8 编码不一致而乱码（如 `仵恺阳` 变成 `浠垫伜闃充笂璇`），导致脚本找不到文件。这是环境问题，与脚本无关。

**已踩坑并验证的避坑规则（务必遵守）:**

1. **不要在命令行直接写中文参数/路径**。涉及中文文件名、中文路径时，改用以下任一方式:
   - **首选**：写一个 UTF-8 编码的临时脚本（ASCII 文件名），把中文路径/参数硬编码进脚本源码，再执行纯 ASCII 命令（如 `python _task.py`）；脚本内已带 `sys.stdout.reconfigure(encoding='utf-8')` 兜底输出编码。
   - 用 `Get-ChildItem` / 管道定位中文文件，再复制成 ASCII 文件名处理。
   - 用脚本显式指定 `-o` ASCII 输出路径，避免中文出现在命令字符串中。
2. **输出文件名若需含中文**：先在脚本内用 `shutil`/`os.rename` 把 ASCII 临时文件重命名为中文名（中文只出现在源码里，不进命令行）。
3. 脚本/报告文件的**内容**（Markdown、JSON）本身用 UTF-8 读写，不受此限制；只有**命令行参数**会乱码。

## 操作步骤

### 第一步：音频转写

使用 `scripts/transcribe_audio.py` 将音频转为文本。

> **长录音（>30 分钟）**：改用 `scripts/transcribe_long.py`（分块 + 断点续传，中断重跑自动跳过已完成块）。录音音量偏低/噪声大时，先用 `scripts/audio_preprocess.py` 做滤波增强（`standard`/`enhance`/`denoise` 三档）。需要估算教师有效讲授时长时，用 `scripts/audio_loudness.py` 做响度分析（30s 窗口 RMS + 清晰讲解段识别）。

#### 单文件转写

```bash
python scripts/transcribe_audio.py 音频文件路径 -o 输出目录 -m base -f json
```

参数说明:
- `input`: 音频文件或目录路径（支持 MP3/WAV/M4A/FLAC/OGG/AAC/WMA/OPUS）
- `-m / --model`: Whisper 模型（tiny/base/small/medium/large，推荐 base）
- `-f / --format`: 输出格式（json/txt/srt/all，推荐 json）
- `-l / --language`: 语言代码（默认 zh）
- `-o / --output`: 输出目录（默认与音频同目录）
- `--api-key`: 云端 API Key（默认从 OPENAI_API_KEY 环境变量读取）
- `--base-url`: API 端点（可选，使用代理时指定）
- `--batch`: 批量处理（输入为目录）
- `-r / --recursive`: 递归子目录

转写通道自动切换:
1. 若提供 api-key -> 云端 Whisper API
2. 若本地安装了 openai-whisper -> 本地模型
3. 均不可用 -> 报错提示

> **环境现状（Windows 本地）**: 本地会优先尝试 faster-whisper，但缺 `onnxruntime` 时会回退到 openai-whisper base（较慢，属正常）；faster-whisper 内部调 ffmpeg 时在中文 Windows 下可能报 `UnicodeDecodeError: 'gbk' codec`（是子进程输出解码问题，不影响最终转写结果，可忽略）。

输出 JSON 包含: file_name, text, segments(含时间戳), duration, model 等字段。

> **读取提示**: `text` 字段是整节课转写的**超长单行**（约 4000～5000 字），直接 `read_file` 整个 JSON 会因 `segments` 数组 + 超长 `text` 触发截断。**请用临时脚本（ASCII 名）提取 `text` 字段打印到 stdout 再读取**，而非直接读整个 JSON 文件。

> **⚠️ 长录音必读：练习段/静音段会被转成"幻觉噪音"，勿误判为无效内容**（本次踩坑，耗时最长）：
>
> 1对1 课堂常是"讲 → 学生安静练习 → 讲评"结构。学生练习段**声音极轻**（仅翻书/写字环境声），Whisper（尤其 base 模型）会把这类**低音量持续底噪**转成一段**固定短语的机械重复**（如"法定人數不足"），而把练习段之后**老师恢复讲解的内容也一并吞成噪音**。
>
> **判断与处理规则（务必遵守）**：
> 1. **看到转写里出现"某个短语机械重复几十次"时**，不要默认它是设备未关闭的静音，要先怀疑"这是练习段 + 后续讲评被幻觉吞掉了"。
> 2. **用 `small` 模型重转练习段之后的部分**（而非整个文件，省时间）：先 `ffmpeg -ss <起> -to <止> -i 音频 -ar 16000 -ac 1 -acodec pcm_s16le 段.wav` 截出"疑似噪音起点之后"的音频，再 `transcribe(model_size='small')` 重转。small 比 base 更准，能区分底噪与真实语音。
> 3. **定位练习段边界**：先读 segments 时间戳，找到"幻觉噪音"首次出现的 `start` 时间（即练习段开始）；练习段结束后老师恢复讲解的时间，用 `ffmpeg -af silencedetect=noise=-40dB:d=5` 检测（若全程无 >5s 静音，说明练习段也有环境声，直接重转噪音段之后部分即可）。
> 4. **报告中的"课堂时长"**：应写"有效授课时长"（讲解 + 讲评），练习段单独标注，不要整段算作无效或把 120 分钟都算成授课。
>
> 本次案例：290MB 的 mp3 总长 120 分钟，前 14 分钟讲解（base 正常转出）→ 15 分钟练习（转成"法定人數不足"）→ 43 分钟讲评（base 也吞了，small 重转后完整还原）。第一版报告误把后 58 分钟当静音，严重低估课堂（78 分 → 修正后 86 分）。

#### 批量转写

```bash
python scripts/transcribe_audio.py 音频目录 --batch -o ./transcripts -f json
# 递归处理子目录
python scripts/transcribe_audio.py 音频目录 --batch --recursive -f json
```

### 第二步：生成听评课报告框架

使用 `scripts/generate_evaluation_report.py` 生成报告框架:

```bash
python scripts/generate_evaluation_report.py 转写文件.json \
  --teacher "教师姓名" --course "课程名称" --grade "授课年级" \
  --student "学生姓名" --date "2026-08-22" -f markdown
```

参数说明:
- `transcript`: 转写文件路径（JSON 格式）
- `--teacher`: 授课教师姓名
- `--course`: 课程名称
- `--grade`: 授课年级
- `--student`: 学生姓名
- `--date`: 听课日期（YYYY-MM-DD，默认当天）
- `-f / --format`: 输出格式（markdown/json/html/text/docx/pdf）
- `-o / --output`: 指定输出路径
- `--output-dir`: 输出目录（默认 ./reports）
- `--standard`: 自定义评估标准 JSON 文件路径

报告命名规则: `{YYYYMMDD}_{教师名}老师_{学生名}_听评课报告.{ext}`
默认输出目录: `./reports/`

### 第三步：AI 深度分析（核心步骤）

脚本生成的是报告框架，**核心分析内容由 AI 完成**。

读取转写文本后，依据评估标准进行深度分析:
1. 读取转写文本（JSON 文件中的 text 字段）
2. 读取评估标准: 见 [references/evaluation_criteria.md](references/evaluation_criteria.md)
3. 读取考点对标知识库: 见 [references/exam_points.md](references/exam_points.md)
4. **选择评课路径**（多路径适配，无需修改 skill）: 读 [references/path_routing.md](references/path_routing.md)，按「学段 + 科目 + 课型」组合选择路径 —— 学段路径 [paths/stages.md](references/paths/stages.md) 定考情对标基准，科目路径 [paths/subjects.md](references/paths/subjects.md) 定公式与考点形式，课型路径 [paths/course_types.md](references/paths/course_types.md) 定五环节评价侧重；此后所有评分与建议均沿所选路径执行
5. 按三大板块评估: 教学环节(75分) / 教学风格(10分) / 学生反馈(15分)
6. 按子项打分并给出优点、待改进、证据引用
7. 若已收集学生成绩 → 进行**学情适配诊断**（附加 10 分）
8. 若已知学科+学段 → 进行**考情对标诊断**（附加 10 分）
9. 结合学情分层 + 考情高频考点 → 制定**短期教学规划指导**（规范见 [references/teaching_plan.md](references/teaching_plan.md)）
10. 生成完整的 Markdown 格式报告

分析提示词模板:

```
请基于以下课堂录音转写文本，生成专业的听评课建议报告。

【基本信息】
- 授课教师：[姓名]
- 课程：[课程名称]
- 年级/学段：[年级/学段]
- 时长：[X 分钟]
- 学生本学科最近成绩：[分数/满分，排名或百分位；未提供则填"未提供"]

【转写文本】
[粘贴转写内容]

【分析要求】
1. 依据《星火教育 1对1 课堂听评课评价标准》三大板块评估：教学环节(75分)、教学风格(10分)、学生反馈(15分)，总分 100
2. 按子项打分：课堂导入(5) / 主题细化(10) / 例题讲解(40) / 变式选题(10) / 模块小结(5) / 作业布置(5) / 形象(5) / 语言(5) / 倾听配合(5) / 师生互动(5) / 课程目标(5)
3. 以学生视角为基准，重点关注学生听完是否真正理解
4. 【学情适配诊断（附加10分）】若提供了学生成绩：按得分率分层（A/B+/B/C），定位当堂内容难度（基础/中档/拔高），依据最近发展区判定"匹配/偏难/偏易"，并评估方法适配（铺垫、梯度、节奏、追问），给出评级与调整建议
5. 【考情对标诊断（附加10分）】按学科+学段：归纳当堂知识点清单，逐点标注考频（高频/中频/低频）与层次，核对教师时间分配与考频是否成正比、有无遗漏核心考点、是否贴合命题趋势，给出评级与调整建议
6. 【短期教学规划指导】结合考情对标（高频核心考点）与学情适配（学生层级），制定未来 2～4 周的落地规划：量化近期目标 + 主攻重点（2～3 个）+ 周计划（具体到每节课/每天，含题量/时长/达标线）+ 检验与调整。必须分学科、分学生层级落地，禁用"加强/提高/夯实"等空话，规范见 references/teaching_plan.md
7. 列出教学亮点（3-5 条）
8. 提出改进建议（3-5 条，要实际、可操作）
9. 引用转写文本中的具体内容作为证据
10. 生成结构化报告（Markdown 格式，公式用 $...$ 与 $$...$$）
```

### 第四步：导出交付

AI 分析完成后，用 `scripts/export_report.py` 将 Markdown 报告导出（默认 PDF）:

```bash
python scripts/export_report.py 分析报告.md \
  --teacher "吴浩" --student "刘子榆" --date "2026-08-22" -f pdf
# -> ./reports/20260822_吴浩老师_刘子榆_听评课报告.pdf
```

参数说明:
- `input`: Markdown 报告文件路径
- `-f / --format`: 输出格式（pdf/docx，默认 pdf）
- `--teacher`: 教师姓名（用于命名和正文补全）
- `--student`: 学生姓名（用于命名和正文补全）
- `--date`: 听课日期（YYYY-MM-DD）
- `-o / --output`: 指定完整输出路径（覆盖命名规则）
- `--output-dir`: 输出目录（默认 ./reports）

**公式支持**（全学科、全学段适用）:
- 行内公式用 `$...$`，如 `斜率 $k=\frac{y_2-y_1}{x_2-x_1}$`
- 块级公式用独立一行 `$$...$$`，如 `$$F=ma$$`
- 支持数学（分数/根号/上下标/求和等）、物理（力学/电学公式）、化学（分子式、方程式）等学科公式，导出为 PDF 时以高清矢量风格渲染
- 导出脚本已修正表格内 `**加粗**` 的渲染（不残留星号），PDF 采用主题配色、斑马纹表格与页眉页脚

#### Skill 变更记录同步输出

若本次使用过程中对 Skill 自身（脚本 / 参考文档 / SKILL.md）做过任何修改，在导出前必须：
1. 将改动追加记录到 [CHANGELOG.md](CHANGELOG.md)（格式见该文件顶部说明）；
2. 维护记录**仅保留在 `CHANGELOG.md`，不写入最终的听评课报告**——报告只面向教师/学生交付听评课内容，不含 Skill 维护细节。

### 第五步：自我总结与 Skill 优化（每次运行必做）

每次运行结束后，必须做一次自我复盘，把踩到的坑沉淀为 Skill 的改进:

1. **回顾本次运行**：是否有踩坑（如编码、路径、字体、格式、脚本 bug）、重复劳动、低效绕路、可复用的一次性脚本。
2. **判断是否值得优化**：凡是「下次还会遇到」的问题，都应固化为 Skill 的规则或脚本修复，而不是每次临场试错。
3. **落盘优化**（任选适用的动作）:
   - 更新 `SKILL.md`（补一条避坑规则 / 流程说明）；
   - 修复/增强 `scripts/` 下的脚本；
   - 更新 `references/` 参考文档；
   - 追加 `CHANGELOG.md` 变更记录（**不写入听评课报告**）。
4. **清理临时文件（一键，勿逐个删）**：遵循工作区统一「临时文件规范」——运行中的一次性调试脚本、中间音频产物（解码 wav、分块文件等）统一放入工作区 `_tmp/` 目录（已被 `.gitignore` 排除），禁止散落在根目录或正式数据目录。结束时执行**一条命令**清理，禁止逐个文件删除（会多次打扰用户确认）：

   ```
   python .codebuddy/scripts/cleanup_tmp.py
   ```

   支持 `--dry-run`（预览不删）与 `--legacy`（额外清理根目录遗留 `*_work/` 目录）。脚本只删 `_tmp/`，绝不触碰 `classroom-evaluation-output/`、`.codebuddy/` 等正式目录。
5. **原则**：把「一次性试错」变成「永久规则」，让下一次运行不再重蹈覆辙。

## 报告内容结构

生成的听评课报告包含:

1. **基本信息**: 授课教师、课程名称、年级、日期、录音时长、转写字数
2. **整体评价**: 综合得分、教学亮点、改进建议
3. **分维度评估**（星火三大板块，总分 100）:
   - 教学环节 (75 分): 课堂导入(5) / 主题细化(10) / 例题讲解(40) / 变式选题(10) / 模块小结(5) / 作业布置(5)
   - 教学风格 (10 分): 形象(5) / 语言(5)
   - 学生反馈 (15 分): 倾听配合(5) / 师生互动(5) / 课程目标(5)
4. **学情适配诊断**（附加 10 分，需学生成绩）: 学生水平分层 → 内容难度定位 → ZPD 匹配判定 → 方法适配 → 评级与调整建议
5. **考情对标诊断**（附加 10 分，需学科+学段）: 知识点考频标注 → 时间配比核对 → 重点完整性 → 趋势贴合 → 评级与调整建议
6. **短期教学规划指导**（需学科+学段+学生成绩，结合考点/知识点/学生能力）: 量化近期目标 → 主攻重点（2～3 个高频考点）→ 周计划（具体到每节课/每天）→ 检验与调整
7. **附录**: 课堂实录节选

每个评估维度包含: 评估指标、评分、优点、待改进、证据引用。

核心理念: 以学生视角为基准，重点关注学生听完是否真正理解；以教师为主导，学生为主体，训练为主线，思维为主攻，能力为主旨。

评估维度详见 [references/evaluation_criteria.md](references/evaluation_criteria.md)（含各细项勾选式评价标准与两个附加诊断维度）。
考情对标与学情适配的分级标准详见 [references/exam_points.md](references/exam_points.md)。
短期教学规划指导的生成规范与分学科/分学段/分层级落地要点详见 [references/teaching_plan.md](references/teaching_plan.md)。

## 使用示例

### 示例1：单份录音听评课

- 场景/输入: 用户提供一份课堂录音文件（如 recording.mp3），要求生成听评课报告
- 预期产出: 一份结构化听评课报告（Word/PDF 格式）
- 关键要点:
  1. 先转写: `python scripts/transcribe_audio.py recording.mp3 -o ./transcripts -f json`
  2. AI 读取转写 JSON 进行深度分析，生成 Markdown 报告
  3. 导出: `python scripts/export_report.py 报告.md --teacher "张老师" --student "李明" --date "2026-08-22" -f docx`
  4. 需向用户确认教师姓名、学生姓名、课程名称、年级等信息

### 示例2：批量录音处理

- 场景/输入: 用户提供包含多个录音文件的目录，要求批量生成听评课报告
- 预期产出: 多份结构化听评课报告
- 关键要点:
  1. 批量转写: `python scripts/transcribe_audio.py ./recordings --batch -o ./transcripts -f json`
  2. 逐一处理每个转写文件，AI 分析生成报告
  3. 逐一导出为 Word/PDF

### 示例3：自定义评估标准

- 场景/输入: 用户有特定的听评课标准，非星火标准
- 预期产出: 按自定义标准生成的评估报告
- 关键要点:
  1. 准备自定义标准 JSON 文件
  2. 使用 --standard 参数: `python scripts/generate_evaluation_report.py transcript.json --standard custom_standard.json -f markdown`

## 资源索引
- 脚本: 见 [scripts/transcribe_audio.py](scripts/transcribe_audio.py)（音频转写，支持本地 Whisper 和云端 API，支持批量处理）
- 脚本: 见 [scripts/transcribe_long.py](scripts/transcribe_long.py)（长录音分块转写 + 断点续传，>30 分钟录音首选）
- 脚本: 见 [scripts/audio_preprocess.py](scripts/audio_preprocess.py)（音频预处理滤波：standard/enhance/denoise 三档，弱音量/高噪录音提升识别率）
- 脚本: 见 [scripts/audio_loudness.py](scripts/audio_loudness.py)（响度分析：30s 窗口 RMS 时间线 + 清晰讲解段识别，估算教师有效讲授时长）
- 脚本: 见 [scripts/generate_evaluation_report.py](scripts/generate_evaluation_report.py)（报告框架生成，支持多种输出格式和自定义评估标准）
- 脚本: 见 [scripts/export_report.py](scripts/export_report.py)（Markdown 报告导出为 Word/PDF，支持中文字体渲染）
- 参考: 见 [references/evaluation_criteria.md](references/evaluation_criteria.md)（何时读取: AI 进行深度分析时，作为评估标准依据，含学情适配与考情对标两个附加诊断维度）
- 参考: 见 [references/exam_points.md](references/exam_points.md)（何时读取: 进行考情对标诊断与学情适配判断时，提供考频分级、考查层次、命题趋势与各科示例）
- 参考: 见 [references/path_routing.md](references/path_routing.md)（何时读取: 深度分析开始时，按学段+科目+课型选择评课路径，避免每次修改 skill）
- 参考: 见 [references/paths/stages.md](references/paths/stages.md)（学段路径: 小学/初中/高中的考情对标基准与术语风格）
- 参考: 见 [references/paths/subjects.md](references/paths/subjects.md)（科目路径: 数学/英语/物理/化学/语文的公式、考点形式与特有评价点）
- 参考: 见 [references/paths/course_types.md](references/paths/course_types.md)（课型路径: 新授课/习题讲评/错题讲评/复习课的五环节评价侧重）
- 参考: 见 [references/teaching_plan.md](references/teaching_plan.md)（何时读取: 生成报告收尾的短期教学规划指导时，提供量化目标/主攻重点/周计划/检验调整的落地模板与分学科/分学段/分层级要点）
- 变更记录: 见 [CHANGELOG.md](CHANGELOG.md)（何时更新: 每次对 Skill 自身做修改后必须追加记录；维护记录仅保留在此文件，不写入报告）

## 注意事项
- 本地 Whisper 转写需要安装 torch 和 openai-whisper，首次加载模型较慢
- 云端转写需要设置 OPENAI_API_KEY 环境变量，适合无 GPU 环境
- Word/PDF 导出依赖 python-docx 和 reportlab，需提前安装
- PDF 导出需要系统中文字体（微软雅黑/黑体/宋体），Linux 环境需额外安装
- 仅在需要时读取评估标准参考，保持上下文简洁
- 每次实际使用中若修改了 Skill 的结构/功能/脚本/参考文档，必须更新 CHANGELOG.md（维护记录不写入听评课报告），以追踪演进、避免后期优化时破坏主体结构
- 充分利用智能体能力进行深度分析，脚本负责转写和格式化导出
