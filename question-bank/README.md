# 题库（question-bank）

统一题库，**按年级/科目分库存放**，id 全局唯一，供检索、组卷、错题出题复用。

## 目录结构（分库架构）

```
question-bank/
├── _meta.json            # 全局 id 计数器（next_id）+ 分库注册表
├── _index.md             # 全局概览（聚合各库统计）
├── README.md
└── {年级}/{科目}/         # 分库（如 高三/物理/、初三/数学/），按需自动创建
    ├── _questions.json   # 该库题目（核心数据）
    ├── _papers.json      # 该库试卷清单
    └── images/{试卷名}/  # 题目插图（images 字段存相对库根的路径）
```

## 关键规则

1. **分库定位**：入库时按试卷的 `grade` + `subject` 写入对应分库；分库不存在时自动创建。
2. **id 全局唯一**：`Q-` + 5 位序号（如 `Q-00323`），由 `_meta.json` 的 `next_id` 统一分配——**跨库绝不重复**。入库流程：读 `_meta.json` → 取号 → 写库 → `next_id+1` 写回。
3. **归属校验**：库内每题的 `grade`/`subject` 必须与所在分库一致（体检脚本强制校验）。
4. **体检**：每次入库后必跑
   `python .codebuddy/skills/exam-paper-analyzer/scripts/validate_question_bank.py`
   （遍历所有分库 + 跨库 id 唯一性 + 字段/枚举/图片/papers 一致性）

## 题目结构（_questions.json 每一项）

```json
{
  "id": "Q-00323",
  "subject": "物理",
  "grade": "高三",
  "source_paper": "顺德一中第四届物理运算",
  "exam_date": "2026-09-05",
  "exam_type": "周测",
  "question_no": "第8题",
  "question_text": "题干",
  "options": ["A...", "B...", "C...", "D..."],
  "answer": "AD",
  "answer_source": "真题答案",
  "analysis": "解析",
  "knowledge_point": "电磁感应",
  "exam_point": "安培力、磁通变化、电量",
  "difficulty": "难题",
  "question_type": "多选题",
  "images": ["images/顺德一中第四届物理运算/第8题.png"]
}
```

## 字段说明

- `answer_source`（答案来源，重要）：`真题答案`（原卷自带）/ `AI解答（待教师确认）`（图片无答案时 AI 解答）/ `教师确认`（AI 解答经教师核对）。教师优先抽查 AI 解答类。
- `exam_type` 枚举：月考 / 期中 / 期末 / 中考 / 高考 / 模拟考 / 联考 / 周测 / 单元测试 / 其他 / 待确认。
- `difficulty` 枚举：基础 / 中等 / 较难 / 难题。

## 使用

- **入库**：`exam-paper-analyzer` skill 分析试卷后，按年级/科目写入对应分库。
- **检索/出题**：`student-error-tracker` skill 按学生的年级+科目定位分库，从中匹配同类题。
