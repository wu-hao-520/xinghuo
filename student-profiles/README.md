# 学生学情数据目录（student-profiles）

本目录存放一对一教师的学生错题管理与靶向出题数据。由 `student-error-tracker` skill 维护。

## 结构

- `students/`：学生档案，每个学生一份 `{姓名}.json`（机器可读主数据）+ `{姓名}.md`（可读视图，由脚本生成，勿手改）。
- `exams/`：每次考试的试卷分析存档、练习单。
- `_question_bank.json`：题库（可选，教师逐步积累，用于优先匹配出题）。

## 使用方式

通过 `student-error-tracker` skill 自动管理（录入错题、诊断、复习、出题、追踪）。

- 录入错题：向学生 `errors` 追加错题记录。
- 生成档案：`python scripts/student_manager.py gen-md --name 学生姓名`。
- 统计薄弱点：`python scripts/student_manager.py stats --name 学生姓名`。

## 注意

- 中文文件名/目录通过 UTF-8 临时脚本读写，避免 Windows GBK 乱码。
- JSON 主数据是唯一真相，MD 是从 JSON 生成的只读视图。
