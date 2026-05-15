"""
skill_evidence: 技能证据链管理
V0.4 — Phoenix-Evo Evidence & Replay

职责：
  - 为每个技能生成并维护 skill_card.json（证据卡）
  - 绑定 source_trajectory_id，追踪来源
  - 记录技能完整生命周期状态（created → verified → replayed → promoted/rejected）
  - 管理 evidence/ 目录下的所有证据文件
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


# ----------------------------------------------------------------------
# SkillCard — 技能证据卡
# ----------------------------------------------------------------------

@dataclass
class SkillCard:
    """
    技能证据卡，记录每个技能的来源、验证状态、晋升历史。

    核心字段：
      skill_id          — 技能唯一标识
      source_trajectory_ids — 来源轨迹 ID 列表
      evidence_type     — "successful_trajectory" | "merged" | "manual"
      status            — "draft" | "verified" | "replay_pending" | "replay_pass" | "replay_fail" | "active" | "archived"
      promotion_ready    — 是否可以晋级 active
      replay_report_ids — 关联的回放报告 ID 列表
      created_at        — 创建时间
      promoted_at       — 晋升 active 时间
      archived_at       — 归档时间
    """
    skill_id: str = ""
    skill_name: str = ""
    source_trajectory_ids: list[str] = field(default_factory=list)
    evidence_type: str = "successful_trajectory"   # 来源类型
    status: str = "draft"
    risk_level: str = "low"
    quality_score: float = 0.0
    created_at: str = ""
    verified_by: list[str] = field(default_factory=list)        # 通过的验证器名称
    replay_report_ids: list[str] = field(default_factory=list)  # 回放报告 ID
    replay_pass_count: int = 0
    replay_fail_count: int = 0
    promotion_ready: bool = False
    promotion_note: str = ""
    promoted_at: str = ""
    archived_at: str = ""
    archive_reason: str = ""
    tags: list[str] = field(default_factory=list)               # 技能标签（来自轨迹）
    task_goal: str = ""                                          # 原始任务目标
    procedure_steps: int = 0                                     # 技能步骤数

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SkillCard":
        # 过滤未知字段
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})


# ----------------------------------------------------------------------
# SkillEvidenceManager
# ----------------------------------------------------------------------

class SkillEvidenceManager:
    """
    管理 evidence/skill_cards/ 目录下的所有技能证据卡。

    职责：
      - 创建 / 读取 / 更新 skill_card.json
      - 绑定 source_trajectory_id
      - 记录验证器通过历史
      - 更新 replay 结果
      - 决定是否可以晋级
    """

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else Path(__file__).parent.parent
        self.cards_dir = self.root / "evidence" / "skill_cards"
        self.cards_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_card(
        self,
        skill: dict[str, Any],
        trajectory_id: str,
    ) -> SkillCard:
        """
        从技能字典和来源轨迹创建证据卡。

        Args:
            skill: SkillMiner.mine() 返回的技能字典
            trajectory_id: 来源轨迹的 task_id

        Returns:
            SkillCard 实例
        """
        card = SkillCard(
            skill_id=skill.get("skill_id", ""),
            skill_name=skill.get("skill_name", ""),
            source_trajectory_ids=[trajectory_id],
            evidence_type="successful_trajectory",
            status="draft",
            risk_level=skill.get("risk_level", "low"),
            quality_score=skill.get("quality_score", 0.0),
            created_at=datetime.now().isoformat(),
            task_goal=skill.get("task_goal", ""),
            procedure_steps=len(skill.get("procedure", [])),
            tags=skill.get("tags", []),
        )
        self.save_card(card)
        return card

    def get_card(self, skill_id: str) -> SkillCard | None:
        """读取指定技能的证据卡。"""
        path = self._card_path(skill_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return SkillCard.from_dict(data)
        except (json.JSONDecodeError, IOError):
            return None

    def save_card(self, card: SkillCard) -> None:
        """保存证据卡到 JSON 文件。"""
        path = self._card_path(card.skill_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(card.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update_card(self, skill_id: str, **kwargs) -> SkillCard | None:
        """更新证据卡的指定字段。"""
        card = self.get_card(skill_id)
        if card is None:
            return None
        for k, v in kwargs.items():
            if hasattr(card, k):
                setattr(card, k, v)
        self.save_card(card)
        return card

    def list_cards(self, status: str | None = None) -> list[SkillCard]:
        """列出所有证据卡，可选按 status 过滤。"""
        cards: list[SkillCard] = []
        for p in self.cards_dir.glob("*.json"):
            try:
                card = SkillCard.from_dict(json.loads(p.read_text(encoding="utf-8")))
                if status is None or card.status == status:
                    cards.append(card)
            except (json.JSONDecodeError, IOError):
                continue
        return cards

    # ------------------------------------------------------------------
    # Replay integration
    # ------------------------------------------------------------------

    def record_replay_result(
        self,
        skill_id: str,
        replay_report_id: str,
        passed: bool,
    ) -> SkillCard | None:
        """
        记录单次回放结果，更新 evidence_card。

        Args:
            skill_id: 技能 ID
            replay_report_id: 回放报告 ID
            passed: 是否通过

        Returns:
            更新后的 SkillCard
        """
        card = self.get_card(skill_id)
        if card is None:
            return None

        if replay_report_id not in card.replay_report_ids:
            card.replay_report_ids.append(replay_report_id)

        if passed:
            card.replay_pass_count += 1
        else:
            card.replay_fail_count += 1

        # 更新 status
        total = card.replay_pass_count + card.replay_fail_count
        if total >= 1:
            if card.replay_pass_count == total and card.replay_pass_count >= 1:
                card.status = "replay_pass"
            elif card.replay_fail_count > 0:
                card.status = "replay_fail"

        self.save_card(card)
        return card

    def set_promotion_ready(
        self,
        skill_id: str,
        ready: bool,
        note: str = "",
    ) -> SkillCard | None:
        """设置技能是否可以晋级。"""
        card = self.get_card(skill_id)
        if card is None:
            return None
        card.promotion_ready = ready
        card.promotion_note = note
        if ready:
            card.status = "replay_pass"
        self.save_card(card)
        return card

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _card_path(self, skill_id: str) -> Path:
        return self.cards_dir / f"{skill_id}.card.json"

    def get_pending_replay(self) -> list[SkillCard]:
        """
        返回所有需要回放验证的 draft 技能。
        条件：status == "draft" 且 replay_pass_count == 0
        """
        cards = self.list_cards(status="draft")
        return [c for c in cards if c.replay_pass_count == 0 and c.replay_fail_count == 0]

    def get_promotion_candidates(self) -> list[SkillCard]:
        """
        返回所有可以晋级的技能。
        条件：promotion_ready == True 且 status == "replay_pass"
        """
        return [
            c for c in self.list_cards()
            if c.promotion_ready and c.status == "replay_pass"
        ]

    def bind_trajectory(self, skill_id: str, trajectory_id: str) -> SkillCard | None:
        """将额外轨迹绑定为技能来源（用于 merged 技能的来源合并）。"""
        card = self.get_card(skill_id)
        if card is None:
            return None
        if trajectory_id not in card.source_trajectory_ids:
            card.source_trajectory_ids.append(trajectory_id)
            card.evidence_type = "merged"
        self.save_card(card)
        return card
