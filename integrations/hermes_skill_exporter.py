"""
Phoenix-Evo V0.5 Hermes Skill Exporter
把 Phoenix 内部的 skill candidate 转换成 Hermes /skills 可读的格式。

Phoenix skill candidate 格式（内部）:
{
    "skill_id": "...",
    "skill_name": "...",
    "skill_md": "...",
    "source_trajectory": "...",
    "procedure": [...],
    "risk_tags": [...],
    "evidence_score": 0.85,
    "replay_result": {...},
    ...
}

Hermes skill 格式（SKILL.md）:
---
name: skill-name
description: 一句话描述技能用途
when_to_use: 何时使用此技能
steps:
  - step 1
  - step 2
constraints:
  - 约束1
  - 约束2
examples:
  - example 1
---
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# Hermes skill frontmatter keys (保留字)
HERMES_SKILL_FRONTKEYS = frozenset([
    "name", "description", "when_to_use", "trigger",
    "steps", "constraints", "examples", "version",
    "source_trajectory", "evidence_score", "skill_id",
])


def _slugify(name: str) -> str:
    """把技能名转成 URL-safe slug。"""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-")


def _extract_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """解析 YAML frontmatter。返回 (frontmatter_dict, body)。"""
    if not text.startswith("---"):
        return {}, text
    parts = text[3:].split("---", 1)
    if len(parts) < 2:
        return {}, text
    fm_text, body = parts
    fm = {}
    for line in fm_text.strip().splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm, body.strip()


def _parse_skill_md(skill_md: str) -> dict[str, Any]:
    """解析 Phoenix 内部 skill_md（可能带 frontmatter）。"""
    fm, body = _extract_frontmatter(skill_md)
    return {"frontmatter": fm, "body": body}


def _build_hermes_skill(
    skill_name: str,
    description: str,
    when_to_use: str,
    steps: list[str],
    constraints: list[str] | None = None,
    examples: list[str] | None = None,
    skill_id: str = "",
    source_trajectory: str = "",
    evidence_score: float = 0.0,
    version: str = "0.1",
    extra_meta: dict[str, Any] | None = None,
) -> str:
    """
    构建 Hermes 兼容的 SKILL.md 格式。
    """
    lines = [
        "---",
        f'name: "{skill_name}"',
        f'version: "{version}"',
    ]

    if skill_id:
        lines.append(f'skill_id: "{skill_id}"')

    if evidence_score > 0:
        lines.append(f"evidence_score: {evidence_score:.2f}")

    if source_trajectory:
        # 截断避免 frontmatter 过长
        src = source_trajectory[:200].replace("\n", " ")
        lines.append(f'source_trajectory: "{src}"')

    lines.extend([
        f'description: "{description}"',
        f'when_to_use: "{when_to_use}"',
        "---",
        "",
        "## Steps",
    ])

    for i, step in enumerate(steps, 1):
        # 清理 markdown 特殊字符
        step_clean = step.strip().replace("\n", " ")
        lines.append(f"{i}. {step_clean}")

    if constraints:
        lines.append("")
        lines.append("## Constraints")
        for c in constraints:
            c_clean = c.strip().replace("\n", " ")
            lines.append(f"- {c_clean}")

    if examples:
        lines.append("")
        lines.append("## Examples")
        for ex in examples:
            ex_clean = ex.strip().replace("\n", " ")
            lines.append(f"- {ex_clean}")

    if extra_meta:
        lines.append("")
        lines.append("## Metadata")
        for k, v in extra_meta.items():
            if k not in HERMES_SKILL_FRONTKEYS:
                lines.append(f"- **{k}**: {v}")

    return "\n".join(lines)


class HermesSkillExporter:
    """
    把 Phoenix skill candidate 导出为 Hermes /skills 兼容格式。

    使用方式：

    ```python
    from integrations.hermes_skill_exporter import HermesSkillExporter

    exporter = HermesSkillExporter(
        phoenix_base_dir=Path("/path/to/Phoenix-Evo"),
        output_dir=Path("/path/to/hermes/skills"),
    )

    # 导出所有 draft skills
    results = exporter.export_all_drafts()
    print(f"已导出 {len(results)} 个 skill 到 Hermes")

    # 导出单个 skill
    result = exporter.export_skill(skill_id="skill_xxx")
    ```

    V0.5 约束：
    - 只从 draft 导出，不动 active/archived
    - 不覆盖已存在的 Hermes skill
    - 不导出 quarantine/reject 状态的 skill
    """

    def __init__(
        self,
        phoenix_base_dir: Path | str | None = None,
        output_dir: Path | str | None = None,
    ):
        if phoenix_base_dir is None:
            phoenix_base_dir = Path(__file__).parent.parent
        elif isinstance(phoenix_base_dir, str):
            phoenix_base_dir = Path(phoenix_base_dir)

        self.phoenix_base_dir = phoenix_base_dir
        self.skills_dir = phoenix_base_dir / "skills"
        self.draft_dir = self.skills_dir / "draft"

        if output_dir is None:
            # 默认输出到 skills/draft/hermes_export/
            output_dir = self.draft_dir / "hermes_export"
        elif isinstance(output_dir, str):
            output_dir = Path(output_dir)

        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 不覆盖已存在的 Hermes skill
        self._protected_names: set[str] = set()
        self._load_protected_names()

    def _load_protected_names(self) -> None:
        """从 Hermes skills 目录加载已有 skill 名（防止覆盖）。"""
        # 这个路径由用户在初始化时提供，或者从 Hermes 配置中读取
        pass

    def _parse_procedure_steps(self, skill_candidate: dict[str, Any]) -> list[str]:
        """从 Phoenix skill candidate 提取 procedure 步骤。"""
        steps = []

        # 方法1：从 procedure 字段提取
        procedure = skill_candidate.get("procedure", [])
        if isinstance(procedure, list):
            for p in procedure:
                if isinstance(p, dict):
                    steps.append(p.get("description", str(p)))
                else:
                    steps.append(str(p))

        # 方法2：从 skill_md body 提取 numbered steps
        if not steps:
            skill_md = skill_candidate.get("skill_md", "")
            fm, body = _extract_frontmatter(skill_md)
            # 尝试从 body 提取 1. 2. 3. 格式的步骤
            for line in body.splitlines():
                line = line.strip()
                if re.match(r"^\d+[\..\)]\s", line):
                    steps.append(re.sub(r"^\d+[\..\)]\s+", "", line))

        # 方法3：从 description 推断（兜底）
        if not steps:
            skill_md = skill_candidate.get("skill_md", "")
            fm, body = _extract_frontmatter(skill_md)
            desc = fm.get("description", skill_candidate.get("description", ""))
            if desc:
                steps = [f"执行：{desc}"]

        return steps

    def _parse_constraints(self, skill_candidate: dict[str, Any]) -> list[str]:
        """从 skill candidate 提取约束条件。"""
        constraints = []

        # 从 risk_tags 提取高风险约束
        risk_tags = skill_candidate.get("risk_tags", [])
        if isinstance(risk_tags, list):
            for tag in risk_tags:
                if tag in ("payment", "data_destruction", "privacy_steal",
                            "privilege_escalation", "network_attack"):
                    constraints.append(f"高风险操作：{tag}，需人工确认")

        # 从 verification_result 提取
        verify = skill_candidate.get("verification_result", {})
        if isinstance(verify, dict):
            risk_level = verify.get("risk_level", "low")
            if risk_level == "high":
                constraints.append("高风险操作，禁止自动执行")
            elif risk_level == "medium":
                constraints.append("中等风险，需人工复核")

        return constraints

    def export_skill(
        self,
        skill_id: str,
        overwrite: bool = False,
        target_dir: Path | str | None = None,
    ) -> dict[str, Any]:
        """
        导出单个 Phoenix draft skill 为 Hermes 兼容格式。

        Args:
            skill_id: Phoenix skill ID
            overwrite: 是否覆盖已存在的 Hermes skill（默认 False）
            target_dir: 输出目录（默认 self.output_dir）

        Returns:
            {"success": bool, "path": str, "skill_id": str, "error": str}
        """
        target_dir = Path(target_dir) if target_dir else self.output_dir

        # 读取 Phoenix draft skill
        draft_path = self.draft_dir / f"{skill_id}.md"
        if not draft_path.exists():
            return {
                "success": False,
                "skill_id": skill_id,
                "error": f"Draft skill 不存在: {draft_path}",
            }

        skill_md = draft_path.read_text(encoding="utf-8")
        candidate = self._parse_skill_md(skill_md)
        fm = candidate["frontmatter"]
        body = candidate["body"]

        # 提取字段
        skill_name = fm.get("name") or fm.get("skill_name") or skill_id
        description = fm.get("description", "无描述")
        when_to_use = fm.get("when_to_use", fm.get("description", "通用技能"))

        # 构建 slug 作为文件名
        slug = _slugify(skill_name)
        output_path = target_dir / f"{slug}.md"

        # 防覆盖检查
        if output_path.exists() and not overwrite:
            return {
                "success": False,
                "skill_id": skill_id,
                "path": str(output_path),
                "error": f"文件已存在（覆盖需设置 overwrite=True）",
            }

        # 提取步骤
        steps = self._parse_procedure_steps(candidate)

        # 提取约束
        constraints = self._parse_constraints(candidate)

        # 构建 Hermes skill
        hermes_skill_md = _build_hermes_skill(
            skill_name=skill_name,
            description=description,
            when_to_use=when_to_use,
            steps=steps,
            constraints=constraints,
            skill_id=skill_id,
            source_trajectory=fm.get("source_trajectory", ""),
            evidence_score=float(fm.get("evidence_score", 0)),
            extra_meta={
                "phoenix_status": "draft",
                "exported_at": datetime.now().isoformat(),
                "original_skill_id": skill_id,
            },
        )

        # 写入文件
        output_path.write_text(hermes_skill_md, encoding="utf-8")

        return {
            "success": True,
            "skill_id": skill_id,
            "path": str(output_path),
            "skill_name": skill_name,
            "slug": slug,
        }

    def export_all_drafts(
        self,
        overwrite: bool = False,
        target_dir: Path | str | None = None,
    ) -> list[dict[str, Any]]:
        """
        导出所有 Phoenix draft skills 到 Hermes 兼容格式。

        Args:
            overwrite: 是否覆盖已存在的 skill 文件
            target_dir: 输出目录

        Returns:
            [{"success": bool, "skill_id": str, "path": str, "error": str}, ...]
        """
        if not self.draft_dir.exists():
            return [{"success": False, "error": f"Draft 目录不存在: {self.draft_dir}"}]

        results = []
        for md_file in self.draft_dir.glob("*.md"):
            # 跳过子目录（如 hermes_export/）
            if md_file.is_dir():
                continue
            skill_id = md_file.stem
            result = self.export_skill(skill_id, overwrite=overwrite, target_dir=target_dir)
            results.append(result)

        return results

    def export_quarantined(
        self,
        overwrite: bool = False,
        target_dir: Path | str | None = None,
    ) -> list[dict[str, Any]]:
        """
        导出 Phoenix quarantine skills（需人工复核后才导出）。
        V0.5 约束：quarantine skill 不能自动导出，此方法仅用于人工确认后的手动导出。
        """
        quarantine_dir = self.skills_dir / "quarantine"
        if not quarantine_dir.exists():
            return []

        results = []
        for md_file in quarantine_dir.glob("*.md"):
            skill_id = md_file.stem
            result = self.export_skill(skill_id, overwrite=overwrite, target_dir=target_dir)
            result["status"] = "quarantine"
            results.append(result)

        return results

    def get_hermes_export_status(self) -> dict[str, Any]:
        """返回 Hermes 导出状态。"""
        exported = list(self.output_dir.glob("*.md"))
        draft_skills = list(self.draft_dir.glob("*.md")) if self.draft_dir.exists() else []

        # 排除 hermes_export 自身
        exported = [f for f in exported if f.parent == self.output_dir]

        return {
            "output_dir": str(self.output_dir),
            "exported_count": len(exported),
            "draft_count": len(draft_skills),
            "exported_skills": [f.stem for f in exported],
        }
