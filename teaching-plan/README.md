# 教学计划数据目录（teaching-plan）

由 `teaching-plan-planner` skill 维护。

## 结构

- `lesson-plans/`：教师提供的教案文件（PDF/Word/MD）+ `_index.json`（教案索引）
- `student-snapshots/`：学情快照（每次规划时汇总的学生现状 JSON）
- `plans/`：生成的教学计划（Markdown + Word + PDF 三格式）

## 使用

1. 把教案文件放到 `lesson-plans/`。
2. 通过 `teaching-plan-planner` skill 生成教学计划。
