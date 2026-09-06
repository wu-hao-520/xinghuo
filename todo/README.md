# 待办事项清单

> 本文件夹记录项目中待优化、待完成的事项，按优先级排序，方便后续挑选优先级靠前的事项来推进。

## 说明

- 每个事项的优先级：🔴 高 / 🟡 中 / 🟢 低
- 状态：待处理 / 进行中 / 已完成
- 有新事项时，追加到对应优先级分组下

---

## 🔴 高优先级

### 1. 项目上传到 Git
- **状态**：待处理
- **描述**：整个项目尚未纳入 Git 版本管理（`.git` 已存在但可能为空或未提交）。需要：初始化/完善 `.gitignore`（排除 `.codebuddy` 临时文件、输出目录等）、首次 commit、关联远程仓库并推送。
- **涉及**：整个 workspace

---

## 🟡 中优先级

### 1. Word 出卷细节持续优化
- **状态**：待处理
- **描述**：继续优化学生练习/试卷的 Word 输出体验：学生版不显示题库编号；统一题干、选项、答案区、解析区排版；持续完善 LaTeX→OMML 转换校验，重点检查 `%`、空格转义、`\div`、`\to`、`\Delta`、`\[4pt]`、分数、根号、上下标等，确保 Word 中无多余反斜杠、乱码、可见 LaTeX 命令或异常公式文本。
- **涉及**：`student-error-tracker` skill、Word 出卷脚本、`scripts/omml_formula.py`

### 2. 教学计划 skill 验证
- **状态**：待处理
- **描述**：`teaching-plan-planner` skill 已创建完成（含 SKILL.md、3 个参考文档、数据目录），但尚未实际跑通完整流程验证。需要用真实学生数据 + 教案文件试跑一次（收集学情 → 解析教案 → 诊断匹配 → 排课次 → 输出三格式），确认流程可用、无 bug。
- **涉及**：`teaching-plan-planner` skill、`teaching-plan/` 数据目录

### 3. 题库公式格式统一
- **状态**：进行中
- **描述**：题库录入已支持 OMML 公式完整还原（转 LaTeX `$...$`）+ vertAlign 上下标（`~x~`/`^x^` 标记），广东卷已按此标准重录（题干选项原文一字不差）。已新增 `exam-paper-analyzer/scripts/latex2omml.py`（LaTeX→Word OMML）和 `render_docx_practice.py`（题库→Word 练习生成器），测试练习 Word 已用最新题库重新生成，公式 0 乱码。待办：① 周测卷 10 题尚未按新标准重录；② 后续新试卷按新标准录入（用 extract_docx + 入库）。

---

## 🟢 低优先级

### 1. 出试卷 PDF 输出功能（挂起）
- **状态**：待处理（已挂起，有需要时再启用）
- **描述**：按用户要求（2026-09-05），出试卷/针对性练习时**不再默认生成 PDF 格式**，只输出 Markdown + Word 两种。PDF 生成功能本身已开发完成且验证可用（连可欣检测练习 PDF 已产出 11 页正常文件），仅是挂起不启用。
- **启用方式**：`student-error-tracker` skill 的 `SKILL.md` 流程五第 6 条已标注暂缓说明；需要恢复时，把该条改回三格式输出即可。技术方案沉淀在：① reportlab 富文本（`<sub>`/`<sup>` 上下标）；② 中文 PDF 字体注册方案（`classroom-audio-evaluation/scripts/export_report.py` 的 `_register_cjk_font()`，msyh.ttc subfontIndex=0）；③ 分数 PIL 渲染 PNG + `<img valign="middle">` 内联（带 hash 缓存）；④ 公式 LaTeX → reportlab 富文本的转换函数（参考 2026-09-05 连可欣练习生成脚本）。
- **涉及**：`student-error-tracker` skill

---

## 已完成事项

### 3. 初三数学题库配图补关联 ✅
- **完成日期**：2026-09-06
- **解决方式**：已扫描 `question-bank/初三/数学/images/`，按原卷题号/图片顺序/题干图示补齐 2026 广东中考数学卷 8 道缺失配图题，题库 `images` 覆盖从 22 题提升到 30 题；其中 2026 广东中考数学卷从 5 题提升到 13 题有图。已修正 `exam-paper-analyzer/scripts/render_docx_practice.py`，Word 出卷直接按题目 `grade`/`subject` 解析分库图片并嵌入，不再依赖出卷目录临时 `assets`。已运行题库校验，0 错误。

### 1. 针对性练习 Word 版分数显示异常 ✅
- **完成日期**：2026-09-05
- **解决方式**：根因是 OMML 上下标标签用错（上标写成 `<m:rPr>` 里的 `<m:sup/>`，下标写成 `<m:sscr>`）。正确方案是 `<m:sSup>`/`<m:sSub>`/`<m:f>` 结构，已封装为 `student-error-tracker/scripts/omml_formula.py`，提供 `add_formula()` 接口。30分钟练习 Word 版已验证（13 上标 + 17 下标 + 9 真分数，0 错误标签）。

### 2. 针对性练习 PDF 版分数与文字同行对齐问题 ✅
- **完成日期**：2026-09-05
- **解决方式**：PDF 分数用 PIL 渲染 PNG + Paragraph `<img valign="middle">` 内联方案，与文字同行、基线对齐（之前的 `valign="-7"` 导致悬空偏下，已修正为 `valign="middle"`）。
