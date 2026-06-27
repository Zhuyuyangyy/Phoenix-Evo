"""
QuarantineManager: 隔离区管理器
V0.2 — Phoenix-Evo Immune Guard

管理被 quarantine 的技能：写入 quarantine 目录、记录原因、维护索引。
被隔离的技能不参与复用，需人工复核后才能激活或归档。
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class QuarantineEntry:
    """隔离区条目。"""
    skill_id: str = ""
    skill_name: str = ""
    quarantine_reason: str = ""
    quarantine_rules: list[str] = field(default_factory=list)   # 触发规则名称列表
    risk_profile: dict = field(default_factory=dict)             # 风险画像快照
    quarantined_at: str = ""                                    # ISO timestamp
    manual_reviewed: bool = False
    manual_review_note: str = ""
    reviewed_by: str = ""                                       # "human" 或 "curator"
    resolution: str = ""                                        # "activated" / "archived" / "rejected"


class QuarantineManager:
    """
    管理 skills/quarantine/ 目录。
    被 immune_guard 判定为 quarantine 的技能写入此处。
    """

    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).parent.parent
        self.quarantine_dir = self.root / "skills" / "quarantine"
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.quarantine_dir / "quarantine_index.json"
        self._index: dict[str, QuarantineEntry] = {}
        self._load_index()

    def _load_index(self) -> None:
        if self.index_file.exists():
            try:
                raw = json.loads(self.index_file.read_text(encoding="utf-8"))
                self._index = {k: QuarantineEntry(**v) for k, v in raw.items()}
            except (json.JSONDecodeError, TypeError, KeyError):
                self._index = {}
        else:
            self._index = {}

    def _save_index(self) -> None:
        data = {k: asdict(v) for k, v in self._index.items()}
        self.index_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def quarantine_skill(
        self,
        skill_md_path: Path,
        reason: str,
        quarantine_rules: list[str],
        risk_profile: dict,
    ) -> QuarantineEntry:
        """
        将技能文件移动到 quarantine 目录，并记录索引。

        Args:
            skill_md_path: 原技能文件路径（通常在 skills/draft/）
            reason: 隔离原因描述
            quarantine_rules: 触发的免疫规则名称列表
            risk_profile: RiskProfile 的 dict 快照

        Returns:
            QuarantineEntry 条目
        """
        skill_id = skill_md_path.stem  # 文件名（不含扩展名）

        entry = QuarantineEntry(
            skill_id=skill_id,
            skill_name=skill_md_path.read_text(encoding="utf-8").split("\n")[0].lstrip("# ").strip(),
            quarantine_reason=reason,
            quarantine_rules=quarantine_rules,
            risk_profile=risk_profile,
            quarantined_at=datetime.now().isoformat(),
        )

        # 移动到 quarantine 目录
        dest = self.quarantine_dir / f"{skill_id}.md"
        if skill_md_path.exists():
            skill_md_path.rename(dest)
        elif not dest.exists():
            dest.write_text(
                f"# Skill: {skill_id}\n\n*In Quarantine*\n\nReason: {reason}",
                encoding="utf-8",
            )

        self._index[skill_id] = entry
        self._save_index()

        return entry

    def resolve_skill(
        self,
        skill_id: str,
        resolution: str,          # "activated" | "archived" | "rejected"
        reviewed_by: str = "human",
        note: str = "",
    ) -> bool:
        """
        人工或 Curator 复核后处理隔离技能。

        resolution="activated" → 移至 skills/active/
        resolution="archived"   → 移至 skills/archived/
        resolution="rejected"   → 保留在 quarantine（标记为 rejected）
        """
        if skill_id not in self._index:
            return False

        entry = self._index[skill_id]
        entry.manual_reviewed = True
        entry.reviewed_by = reviewed_by
        entry.manual_review_note = note
        entry.resolution = resolution

        src = self.quarantine_dir / f"{skill_id}.md"

        if resolution == "activated":
            dest = self.root / "skills" / "active" / f"{skill_id}.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                src.rename(dest)
        elif resolution == "archived":
            dest = self.root / "skills" / "archived" / f"{skill_id}.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                src.rename(dest)
        # rejected → 留在原地，仅更新索引

        self._save_index()
        return True

    def get_pending_review(self) -> list[QuarantineEntry]:
        """返回待复核的 quarantine 技能列表。"""
        return [v for v in self._index.values() if not v.manual_reviewed]

    def get_all_entries(self) -> dict[str, QuarantineEntry]:
        return dict(self._index)

    def count_pending(self) -> int:
        return len(self.get_pending_review())
