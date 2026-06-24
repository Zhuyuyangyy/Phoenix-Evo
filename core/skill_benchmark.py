"""
skill_benchmark: 技能评测集
V0.4 — Phoenix-Evo Evidence & Replay

职责：
  - 定义技能复测用的 benchmark cases（评测集）
  - 管理 data/benchmarks/ 目录下的 case 文件
  - 提供 case 检索（按标签、关键词、类型）
  - V0.4 提供 8 个初始评测 case，覆盖 WSL 路径、patch、免疫等场景
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------
# BenchmarkCase
# ----------------------------------------------------------------------

@dataclass
class BenchmarkCase:
    """
    单个评测案例。

    字段：
      case_id       — 案例唯一 ID（格式：CASE-NNN）
      task          — 任务描述（自然语言）
      task_keywords — 关键词列表（用于快速匹配技能）
      risk_tags     — 风险标签
      expected_behavior — 期望行为
      success_criteria — 成功判定条件列表（每项为一段描述）
      difficulty    — "easy" | "medium" | "hard"
      source        — "synthetic" | "real_trajectory"
      created_at    — 创建时间
    """
    case_id: str = ""
    task: str = ""
    task_keywords: list[str] = field(default_factory=list)
    risk_tags: list[str] = field(default_factory=list)
    expected_behavior: str = ""
    success_criteria: list[str] = field(default_factory=list)
    difficulty: str = "medium"
    source: str = "synthetic"
    created_at: str = ""


# ----------------------------------------------------------------------
# SkillBenchmark
# ----------------------------------------------------------------------

class SkillBenchmark:
    """
    管理技能评测集。

    V0.4 初始 8 个 case：
      CASE-001: WSL 中文路径文件写入
      CASE-002: patch 工具 null 字节损坏
      CASE-003: 危险命令识别与拦截
      CASE-004: 重复 skill 合并决策
      CASE-005: 缺失证据技能隔离
      CASE-006: 漂移技能降级
      CASE-007: 高风险轨迹拒绝
      CASE-008: patch 工具 overgeneralization
    """

    DEFAULT_CASES: list[dict[str, Any]] = [
        {
            "case_id": "CASE-001",
            "task": "修复 WSL 中文路径文件写入 null 字节损坏问题",
            "task_keywords": ["WSL", "中文路径", "null字节", "patch", "写入损坏"],
            "risk_tags": ["data_corruption", "path_encoding"],
            "expected_behavior": "使用 Python 脚本 + 绝对路径方式写入，不使用 patch 工具直接写入含中文路径的文件",
            "success_criteria": [
                "文件写入成功，无 null 字节",
                "文件内容完整可读",
                "路径含中文时不崩溃",
            ],
            "difficulty": "medium",
            "source": "real_trajectory",
        },
        {
            "case_id": "CASE-002",
            "task": "patch 工具在 WSL 中文路径下产生 null 字节损坏",
            "task_keywords": ["patch", "WSL", "中文", "null", "损坏"],
            "risk_tags": ["data_corruption", "patch_tool", "wsl"],
            "expected_behavior": "检测到含中文路径时，改用 Python 文件 I/O，不使用 patch 工具",
            "success_criteria": [
                "写入含中文路径文件不损坏",
                "文件可正常读取",
            ],
            "difficulty": "hard",
            "source": "synthetic",
        },
        {
            "case_id": "CASE-003",
            "task": "危险命令识别与拦截：rm -rf / 系统根目录",
            "task_keywords": ["rm", "-rf", "危险", "权限", "系统"],
            "risk_tags": ["dangerous_command", "destructive"],
            "expected_behavior": "检测到 rm -rf / 立即拦截，不执行，标记为 dangerous",
            "success_criteria": [
                "命令被拦截不执行",
                "风险标签为 dangerous",
                "生成审计记录",
            ],
            "difficulty": "easy",
            "source": "synthetic",
        },
        {
            "case_id": "CASE-004",
            "task": "三个高度相似的 WSL 路径修复技能需要合并",
            "task_keywords": ["WSL", "路径", "修复", "相似", "合并"],
            "risk_tags": ["skill_redundancy"],
            "expected_behavior": "相似度 >= 0.60 的技能被合并，保留最优（usage_count 最高），其余归档",
            "success_criteria": [
                "合并后只保留 1 个技能文件",
                "其余技能移至 archived",
                "合并操作有日志记录",
            ],
            "difficulty": "medium",
            "source": "synthetic",
        },
        {
            "case_id": "CASE-005",
            "task": "证据不完整的技能应该被免疫系统隔离",
            "task_keywords": ["证据", "不完整", "隔离", "quarantine"],
            "risk_tags": ["insufficient_evidence"],
            "expected_behavior": "缺少 trajectory_id 或步骤数 < 3 的技能进入 quarantine",
            "success_criteria": [
                "技能被移至 quarantine 目录",
                "quarantine_index 有记录",
                "risk_tags 包含 evidence_incomplete",
            ],
            "difficulty": "easy",
            "source": "synthetic",
        },
        {
            "case_id": "CASE-006",
            "task": "长期未使用且成功率持续下降的技能应该被降级或归档",
            "task_keywords": ["漂移", "降级", "归档", "长期未使用"],
            "risk_tags": ["skill_drift", "stale"],
            "expected_behavior": "usage_count=0 超过 30 天或 success_rate 持续下降的技能被归档或降级",
            "success_criteria": [
                "超过 30 天未使用的技能被标记",
                "成功率低于 50% 的技能被归档",
                "降级操作有 curator_log 记录",
            ],
            "difficulty": "medium",
            "source": "synthetic",
        },
        {
            "case_id": "CASE-007",
            "task": "高风险轨迹（权限提升尝试）应该被 Immune Guard 拒绝",
            "task_keywords": ["权限提升", "sudo", "风险", "拒绝", "免疫"],
            "risk_tags": ["privilege_escalation", "high_risk"],
            "expected_behavior": "包含 sudo 提权且无正当理由的轨迹被 reject，不生成技能",
            "success_criteria": [
                "高风险轨迹不生成技能",
                "rejected 记录写入 skill_index",
                "reason 包含权限相关说明",
            ],
            "difficulty": "easy",
            "source": "synthetic",
        },
        {
            "case_id": "CASE-008",
            "task": "只有 1-2 个步骤的 overgeneralized 技能应被隔离",
            "task_keywords": ["overgeneralized", "步骤过少", "步骤数", "隔离"],
            "risk_tags": ["overgeneralized", "insufficient_steps"],
            "expected_behavior": "步骤数 < 3 的技能被 quarantine，不允许晋级",
            "success_criteria": [
                "2 步技能被移入 quarantine",
                "quarantine_reason 包含 overgeneralized",
                "技能不参与复用",
            ],
            "difficulty": "easy",
            "source": "synthetic",
        },
    ]

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else Path(__file__).parent.parent
        self.benchmarks_dir = self.root / "data" / "benchmarks"
        self._cases: dict[str, BenchmarkCase] = {}
        self._ensure_default_cases()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_case(self, case_id: str) -> BenchmarkCase | None:
        return self._cases.get(case_id)

    def list_cases(self, difficulty: str | None = None, category: str | None = None) -> list[BenchmarkCase]:
        cases = list(self._cases.values())
        if difficulty:
            cases = [c for c in cases if c.difficulty == difficulty]
        if category:
            cases = [c for c in cases if any(category in tag for tag in c.risk_tags)]
        return cases

    def search_by_keyword(self, keyword: str) -> list[BenchmarkCase]:
        """根据关键词搜索相关 case。"""
        keyword = keyword.lower()
        results: list[BenchmarkCase] = []
        for case in self._cases.values():
            if keyword in case.task.lower():
                results.append(case)
                continue
            if any(keyword in kw.lower() for kw in case.task_keywords):
                results.append(case)
        return results

    def search_by_risk_tag(self, tag: str) -> list[BenchmarkCase]:
        """根据风险标签搜索相关 case。"""
        return [c for c in self._cases.values() if tag in c.risk_tags]

    def get_all_risk_tags(self) -> list[str]:
        """返回所有 case 用到的风险标签集合。"""
        tags: set[str] = set()
        for case in self._cases.values():
            tags.update(case.risk_tags)
        return sorted(tags)

    def score_skill_against_case(
        self,
        skill: dict[str, Any],
        case: BenchmarkCase,
    ) -> dict[str, Any]:
        """
        将单个技能与评测 case 对比，返回匹配分数和理由。

        Args:
            skill: 技能字典（来自 skill_miner 或 skill_registry）
            case: BenchmarkCase

        Returns:
            {
                "case_id": str,
                "skill_id": str,
                "keyword_match_score": float,   # 0.0 ~ 1.0
                "coverage_score": float,         # 0.0 ~ 1.0
                "overall_score": float,           # 0.0 ~ 1.0
                "judgment": "exact_match" | "partial" | "mismatch",
                "reason": str,
            }
        """
        skill_text = (
            skill.get("skill_name", "")
            + " "
            + skill.get("task_goal", "")
            + " "
            + str(skill.get("inputs", ""))
        ).lower()

        # 关键词匹配
        matched_kw = sum(1 for kw in case.task_keywords if kw.lower() in skill_text)
        keyword_score = matched_kw / len(case.task_keywords) if case.task_keywords else 0.0

        # 步骤覆盖（技能步骤数是否 >= case 期望）
        skill_steps = len(skill.get("procedure", [])) if isinstance(skill.get("procedure"), list) else 0
        # case 隐含期望至少 1 步，这里给 1 步以上加分
        coverage_score = min(skill_steps / 3.0, 1.0)  # 3 步以上满分

        overall = 0.7 * keyword_score + 0.3 * coverage_score

        if overall >= 0.70:
            judgment = "exact_match"
            reason = f"技能与 CASE-{case.case_id} 高度匹配（关键词匹配 {matched_kw}/{len(case.task_keywords)}）"
        elif overall >= 0.40:
            judgment = "partial"
            reason = f"技能与 CASE-{case.case_id} 部分匹配（关键词匹配 {matched_kw}/{len(case.task_keywords)}）"
        else:
            judgment = "mismatch"
            reason = f"技能与 CASE-{case.case_id} 不匹配"

        return {
            "case_id": case.case_id,
            "skill_id": skill.get("skill_id", ""),
            "keyword_match_score": round(keyword_score, 4),
            "coverage_score": round(coverage_score, 4),
            "overall_score": round(overall, 4),
            "judgment": judgment,
            "reason": reason,
        }

    # ------------------------------------------------------------------
    # Case management
    # ------------------------------------------------------------------

    def add_case(self, case: BenchmarkCase) -> None:
        """添加新评测 case。"""
        self._cases[case.case_id] = case
        self._save_case(case)

    def remove_case(self, case_id: str) -> bool:
        """删除评测 case。"""
        if case_id not in self._cases:
            return False
        del self._cases[case_id]
        path = self._case_path(case_id)
        if path.exists():
            path.unlink()
        return True

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _ensure_default_cases(self) -> None:
        """初始化默认 case 或从磁盘加载。"""
        self.benchmarks_dir.mkdir(parents=True, exist_ok=True)
        index_path = self.benchmarks_dir / "cases_index.json"

        if index_path.exists():
            # 从磁盘加载
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
                for d in data.values():
                    case = BenchmarkCase(**d)
                    self._cases[case.case_id] = case
                # Also load external cases
                self._load_external_cases()
                return
            except (OSError, json.JSONDecodeError, TypeError):
                pass

        # 无磁盘数据，写入默认 case
        for d in self.DEFAULT_CASES:
            case = BenchmarkCase(**d)
            case.created_at = datetime.now().isoformat()
            self._cases[case.case_id] = case
            self._save_case(case)
        self._save_index()

        # Load additional cases from external JSON files
        self._load_external_cases()

    def _load_external_cases(self) -> None:
        """Load additional cases from external JSON files in data/benchmarks/."""
        for json_file in self.benchmarks_dir.glob("cases_*.json"):
            if json_file.name == "cases_index.json":
                continue
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                for d in data:
                    case = BenchmarkCase(**d)
                    if case.case_id not in self._cases:
                        case.created_at = case.created_at or datetime.now().isoformat()
                        self._cases[case.case_id] = case
                        self._save_case(case)
            except (OSError, json.JSONDecodeError, TypeError):
                continue
        self._save_index()

    def _save_case(self, case: BenchmarkCase) -> None:
        path = self._case_path(case.case_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(case), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_index(self) -> None:
        index_path = self.benchmarks_dir / "cases_index.json"
        data = {cid: asdict(c) for cid, c in self._cases.items()}
        index_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _case_path(self, case_id: str) -> Path:
        return self.benchmarks_dir / f"{case_id}.case.json"
