"""
ImmuneMemory: 免疫记忆
V0.2 — Phoenix-Evo Immune Guard

维护技能历史失败记录，用于"反复失败免疫"规则。
immune_memory.json 记录同类技能多次触发失败的历史。
"""

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class ImmuneRecord:
    """单条免疫记录。"""
    skill_pattern: str          # 用于匹配同类技能的指纹（如 skill_name 前缀）
    failure_count: int = 1       # 累计失败次数
    first_seen: str = ""        # ISO timestamp
    last_seen: str = ""         # ISO timestamp
    last_failure_reason: str = ""
    quarantined: bool = False    # 是否已被 quarantine
    tags: list[str] = field(default_factory=list)  # 关联危险标签


class ImmuneMemory:
    """
    读取和写入 immune_memory.json。
    用于"反复失败免疫"规则：同类技能失败 N 次 → quarantine。
    """

    def __init__(self, root: Path | str | None = None):
        if root is None:
            self.root = Path(__file__).parent.parent
        elif isinstance(root, str):
            self.root = Path(root)
        else:
            self.root = root
        self.memory_file = self.root / "immune_memory.json"
        self._records: dict[str, ImmuneRecord] = {}
        self._load()

    def _load(self) -> None:
        if self.memory_file.exists():
            try:
                raw = json.loads(self.memory_file.read_text(encoding="utf-8"))
                for k, v in raw.items():
                    self._records[k] = ImmuneRecord(**v)
            except (json.JSONDecodeError, TypeError, KeyError):
                self._records = {}
        else:
            self._records = {}

    def _save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        data = {k: asdict(v) for k, v in self._records.items()}
        self.memory_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _fingerprint(self, skill_name: str, tags: list[str]) -> str:
        """生成技能指纹：取 skill_name 前 40 字符 + 危险标签排序后的前 3 个。"""
        base = skill_name[:40]
        key_tags = sorted(tags)[:3]
        return f"{base}::{','.join(key_tags)}"

    def record_failure(
        self,
        skill_name: str,
        reason: str,
        tags: list[str] | None = None,
    ) -> int:
        """
        记录一次技能失败。返回当前累计失败次数。
        如果超过阈值，将该 record 的 quarantined 设为 True。
        """
        tags = tags or []
        fp = self._fingerprint(skill_name, tags)
        now = datetime.now().isoformat()

        if fp in self._records:
            rec = self._records[fp]
            rec.failure_count += 1
            rec.last_seen = now
            rec.last_failure_reason = reason
        else:
            rec = ImmuneRecord(
                skill_pattern=fp,
                failure_count=1,
                first_seen=now,
                last_seen=now,
                last_failure_reason=reason,
                tags=tags,
            )
            self._records[fp] = rec

        # 超过阈值 → 标记 quarantine
        from .risk_policy import REPEAT_FAILURE_THRESHOLD
        if rec.failure_count >= REPEAT_FAILURE_THRESHOLD:
            rec.quarantined = True

        self._save()
        return rec.failure_count

    def get_failure_count(self, skill_name: str, tags: list[str] | None = None) -> int:
        """查询某类技能的累计失败次数。"""
        fp = self._fingerprint(skill_name, tags or [])
        return self._records.get(fp, ImmuneRecord(skill_pattern="")).failure_count

    def is_quarantined(self, skill_name: str, tags: list[str] | None = None) -> bool:
        """查询某类技能是否已被 quarantine。"""
        fp = self._fingerprint(skill_name, tags or [])
        rec = self._records.get(fp)
        return rec.quarantined if rec else False

    def get_all_records(self) -> dict[str, ImmuneRecord]:
        return dict(self._records)

    def clear(self) -> None:
        """清空所有免疫记忆（仅测试用）。"""
        self._records = {}
        self._save()
