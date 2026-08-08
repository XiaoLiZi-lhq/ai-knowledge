"""
AI Knowledge Hub - AI 导师服务
出题 / 盲区扫描 / 学习计划生成
"""

from datetime import date, timedelta
from app.core.llm import llm_service
from app.core.rag import rag
from app.config import settings
import yaml
from pathlib import Path
import json
import sqlite3


# AI/ML 标准知识树
DEFAULT_KNOWLEDGE_TREE = {
    "数学基础": ["线性代数", "概率论", "微积分", "优化理论", "信息论"],
    "机器学习": ["监督学习", "无监督学习", "强化学习", "模型评估", "特征工程", "集成学习"],
    "深度学习": ["CNN", "RNN", "LSTM", "Transformer", "注意力机制", "预训练模型", "生成模型"],
    "NLP": ["词嵌入", "文本分类", "序列标注", "生成模型", "RLHF", "RAG", "Prompt工程"],
    "工程实践": ["模型部署", "推理优化", "向量数据库", "Agent", "MLOps", "分布式训练"],
}


class QuizGenerator:
    """AI 出题引擎"""

    def generate(self, topic: str = "", count: int = 5, quiz_type: str = "mixed") -> dict:
        """
        基于知识库内容生成测验题
        quiz_type: choice（选择）/ short_answer（简答）/ code（代码）/ mixed（混合）
        """
        # 检索相关笔记
        query = topic if topic else "AI 机器学习 深度学习"
        retrieved = rag.retrieve(query, top_k=5)

        if not retrieved:
            return {"error": "知识库中没有相关内容，请先导入笔记"}

        # 构建出题 Prompt
        context = "\n\n".join([f"[{i+1}] {d['content']}" for i, d in enumerate(retrieved)])

        type_instruction = {
            "choice": "生成选择题（4个选项，标注正确答案）",
            "short_answer": "生成简答题",
            "code": "生成代码实现题",
            "mixed": "混合生成选择题、简答题和代码题",
        }.get(quiz_type, "混合生成各类题目")

        prompt = f"""基于以下笔记内容，{type_instruction}。共 {count} 道题。
主题：{topic or "综合"}

笔记内容：
{context}

要求：
- 题目必须基于笔记内容，不要编造
- 难度适中，考察理解而非记忆
- 输出 JSON 格式：
{{"questions": [{{"type": "choice|short_answer|code", "question": "题目", "options": ["A选项","B选项","C选项","D选项"], "answer": "正确答案", "explanation": "解析"}}]}}

只输出 JSON。"""

        result = llm_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=2000,
        )

        try:
            result = result.strip().strip("```json").strip("```").strip()
            data = json.loads(result)
            self._log_quiz(topic, len(data.get("questions", [])))
            return data
        except Exception:
            return {"error": "题目生成失败，请重试", "raw": result[:500]}

    def submit(self, answers: list[dict]) -> dict:
        """提交答案，返回得分和反馈"""
        correct = 0
        feedback = []
        for ans in answers:
            if ans.get("user_answer", "").strip() == ans.get("correct_answer", "").strip():
                correct += 1
                feedback.append({"question": ans.get("question", ""), "result": "correct"})
            else:
                feedback.append({
                    "question": ans.get("question", ""),
                    "result": "wrong",
                    "correct_answer": ans.get("correct_answer", ""),
                    "user_answer": ans.get("user_answer", ""),
                })

        score = int(correct / max(len(answers), 1) * 100)
        return {"score": score, "correct": correct, "total": len(answers), "feedback": feedback}

    def _log_quiz(self, topic: str, count: int):
        """记录测验日志"""
        conn = sqlite3.connect(settings.SQLITE_PATH)
        conn.execute(
            "INSERT INTO learning_log (date, activity, topic, score) VALUES (?, 'quiz', ?, NULL)",
            (date.today().isoformat(), topic or "general"),
        )
        conn.commit()
        conn.close()


class GapScanner:
    """知识盲区扫描器"""

    def scan(self, domain: str = "") -> dict:
        """
        对比标准知识树，扫描知识库覆盖度
        返回各领域覆盖率和缺失知识点
        """
        tree = DEFAULT_KNOWLEDGE_TREE
        if domain and domain in tree:
            tree = {domain: tree[domain]}

        # 提取 Vault 中所有标签和标题
        vault_tags = self._extract_vault_tags()
        vault_titles = self._extract_vault_titles()

        results = []
        coverage_summary = {}

        for domain_name, topics in tree.items():
            domain_coverage = []
            gaps = []

            for topic in topics:
                coverage = self._assess_topic_coverage(topic, vault_tags, vault_titles)
                domain_coverage.append(coverage)
                if coverage < 0.3:
                    gaps.append({
                        "topic": topic,
                        "coverage": coverage,
                        "suggestion": f"建议补充 {topic} 相关笔记",
                    })

            avg_coverage = sum(domain_coverage) / len(domain_coverage) if domain_coverage else 0
            coverage_summary[domain_name] = round(avg_coverage * 100)

            status = "优秀" if avg_coverage >= 0.7 else "良好" if avg_coverage >= 0.5 else "需加强"

            results.append({
                "domain": domain_name,
                "coverage_percent": round(avg_coverage * 100),
                "status": status,
                "gaps": gaps,
            })

        # 生成建议
        all_gaps = [g for r in results for g in r["gaps"]]
        suggestions = []
        if all_gaps:
            suggestions.append(f"发现 {len(all_gaps)} 个知识盲区，建议优先补充覆盖度最低的知识点")

        return {
            "coverage": coverage_summary,
            "details": results,
            "total_gaps": len(all_gaps),
            "suggestions": suggestions,
        }

    def _extract_vault_tags(self) -> set:
        """提取 Vault 所有标签"""
        vault = settings.vault_path_obj
        tags = set()
        if not vault.exists():
            return tags
        for md in vault.rglob("*.md"):
            try:
                text = md.read_text(encoding="utf-8")
                # frontmatter tags
                if text.startswith("---"):
                    parts = text.split("---", 2)
                    if len(parts) >= 3:
                        for line in parts[1].split("\n"):
                            if line.strip().startswith("tags:"):
                                tag_part = line.split(":", 1)[1].strip()
                                for t in tag_part.strip("[]").split(","):
                                    t = t.strip().strip('"\'').strip("#").strip("/")
                                    if t:
                                        tags.add(t.lower())
                # inline tags
                for line in text.split("\n"):
                    for word in line.split():
                        if word.startswith("#") and len(word) > 1:
                            tags.add(word.strip("#").strip("/").lower())
            except Exception:
                continue
        return tags

    def _extract_vault_titles(self) -> list[str]:
        """提取 Vault 所有笔记标题"""
        vault = settings.vault_path_obj
        titles = []
        if not vault.exists():
            return titles
        for md in vault.rglob("*.md"):
            titles.append(md.stem.lower())
            try:
                text = md.read_text(encoding="utf-8")
                for line in text.split("\n")[:10]:
                    if line.startswith("# "):
                        titles.append(line.strip("# ").lower())
            except Exception:
                continue
        return titles

    def _assess_topic_coverage(self, topic: str, tags: set, titles: list[str]) -> float:
        """评估单个知识点的覆盖度（0-1）"""
        topic_lower = topic.lower()
        topic_keywords = topic_lower.replace("，", " ").split()

        # 在标签中匹配
        tag_matches = sum(1 for kw in topic_keywords if any(kw in tag for tag in tags))

        # 在标题中匹配
        title_matches = sum(1 for kw in topic_keywords if any(kw in title for title in titles))

        total_possible = len(topic_keywords) * 2
        actual = tag_matches + title_matches

        return min(actual / max(total_possible, 1), 1.0)


class PlanGenerator:
    """学习计划生成器"""

    def generate(self, goal: str, duration_days: int = 14) -> dict:
        """
        根据目标和时长生成结构化学习计划
        """
        # 先做盲区扫描，找出相关缺失
        scanner = GapScanner()
        scan_result = scanner.scan()

        # 找到与目标相关的盲区
        goal_keywords = goal.lower().split()
        relevant_gaps = []
        for detail in scan_result["details"]:
            for gap in detail["gaps"]:
                if any(kw in gap["topic"].lower() for kw in goal_keywords) or not goal_keywords:
                    relevant_gaps.append(gap)

        # 构建计划生成 Prompt
        gaps_text = "\n".join([f"- {g['topic']}（覆盖度{int(g["coverage"]*100)}%）" for g in relevant_gaps[:10]]) or "暂无明确盲区"

        prompt = f"""生成一个 {duration_days} 天的学习计划。

目标：{goal}
当前知识盲区：
{gaps_text}

要求：
1. 每天有明确的任务（理论+实践）
2. 每周有检验节点
3. 推荐具体学习资源（论文/视频/代码库）
4. 输出 JSON 格式：
{{
  "title": "计划标题",
  "goal": "目标",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "weeks": [
    {{
      "week": 1,
      "theme": "主题",
      "days": [
        {{"date": "YYYY-MM-DD", "task": "任务描述", "estimated_hours": 2, "resources": ["资源1"]}}
      ],
      "checkpoint": "周末检验内容"
    }}
  ]
}}

今天日期：{date.today().isoformat()}
只输出 JSON。"""

        result = llm_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=3000,
        )

        try:
            result = result.strip().strip("```json").strip("```").strip()
            plan = json.loads(result)

            # 保存到 SQLite
            self._save_plan(plan)

            # 写入 Vault Markdown
            self._write_plan_md(plan)

            return plan
        except Exception:
            return {"error": "计划生成失败，请重试", "raw": result[:500]}

    def _save_plan(self, plan: dict):
        """保存到 SQLite"""
        conn = sqlite3.connect(settings.SQLITE_PATH)
        conn.execute(
            """INSERT INTO study_plans (title, start_date, end_date, goal, tasks, status)
            VALUES (?, ?, ?, ?, ?, 'active')""",
            (
                plan.get("title", "学习计划"),
                plan.get("start_date", date.today().isoformat()),
                plan.get("end_date", ""),
                plan.get("goal", ""),
                json.dumps(plan, ensure_ascii=False),
            ),
        )
        conn.commit()
        conn.close()

    def _write_plan_md(self, plan: dict):
        """写入 Vault"""
        vault = settings.vault_path_obj
        plan_dir = vault / "05-Learning" / "plans"
        plan_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{plan.get('title', 'plan')}-{date.today().isoformat()}.md"
        lines = [
            f"---",
            f"type: study-plan",
            f"status: active",
            f"start: {plan.get('start_date', '')}",
            f"end: {plan.get('end_date', '')}",
            f"---",
            f"",
            f"# {plan.get('title', '学习计划')}",
            f"",
            f"**目标**：{plan.get('goal', '')}",
            f"**周期**：{plan.get('start_date', '')} ~ {plan.get('end_date', '')}",
            f"",
        ]

        for week in plan.get("weeks", []):
            lines.append(f"## Week {week.get('week', '')}: {week.get('theme', '')}")
            lines.append("")
            lines.append("| 日期 | 任务 | 预计用时 | 资源 |")
            lines.append("|------|------|----------|------|")
            for day in week.get("days", []):
                resources = ", ".join(day.get("resources", []))
                lines.append(
                    f"| {day.get('date', '')} | {day.get('task', '')} | "
                    f"{day.get('estimated_hours', 2)}h | {resources} |"
                )
            lines.append("")
            lines.append(f"**周末检验**：{week.get('checkpoint', '')}")
            lines.append("")

        plan_dir.joinpath(filename).write_text("\n".join(lines), encoding="utf-8")


# 全局单例
quiz_generator = QuizGenerator()
gap_scanner = GapScanner()
plan_generator = PlanGenerator()
