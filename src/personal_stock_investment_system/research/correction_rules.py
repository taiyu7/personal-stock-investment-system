"""Exact-match human review rules for research report entities."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from personal_stock_investment_system.research.sources import EntityClassification, ResearchReport
from personal_stock_investment_system.research.stock_validation import TaiwanStockDirectory
from personal_stock_investment_system.storage.migrations import run_sqlite_migrations

EntityType = str  # taiwan_stock | foreign_stock | sector | non_stock


@dataclass(frozen=True)
class ResearchCorrectionRule:
    raw_code: str
    raw_name: str
    entity_type: EntityType
    canonical_code: str = ""
    canonical_name: str = ""
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""


class ResearchCorrectionRuleRepository:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)

    def list_rules(self) -> tuple[ResearchCorrectionRule, ...]:
        if not self.database_path.exists():
            return ()
        run_sqlite_migrations(self.database_path)
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT raw_code, raw_name, entity_type, canonical_code, canonical_name, enabled, created_at, updated_at "
                "FROM research_correction_rules ORDER BY raw_name, raw_code"
            ).fetchall()
        return tuple(ResearchCorrectionRule(*row[:5], bool(row[5]), row[6], row[7]) for row in rows)

    def save_rule(self, rule: ResearchCorrectionRule) -> ResearchCorrectionRule:
        if rule.entity_type not in {"taiwan_stock", "foreign_stock", "etf", "sector", "non_stock"}:
            raise ValueError("不支援的查核分類。")
        if not rule.raw_name.strip():
            raise ValueError("原始名稱不可空白。")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        run_sqlite_migrations(self.database_path)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """INSERT INTO research_correction_rules
                   (raw_code, raw_name, entity_type, canonical_code, canonical_name, enabled, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                   ON CONFLICT(raw_code, raw_name) DO UPDATE SET
                     entity_type=excluded.entity_type, canonical_code=excluded.canonical_code,
                     canonical_name=excluded.canonical_name, enabled=1, updated_at=excluded.updated_at""",
                (rule.raw_code.strip(), rule.raw_name.strip(), rule.entity_type, rule.canonical_code.strip(),
                 rule.canonical_name.strip(), now, now),
            )
        return replace(rule, raw_code=rule.raw_code.strip(), raw_name=rule.raw_name.strip(), enabled=True,
                       created_at=rule.created_at or now, updated_at=now)

    def set_enabled(self, rule: ResearchCorrectionRule, enabled: bool) -> None:
        run_sqlite_migrations(self.database_path)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "UPDATE research_correction_rules SET enabled=?, updated_at=? WHERE raw_code=? AND raw_name=?",
                (int(enabled), datetime.now(timezone.utc).isoformat(timespec="seconds"), rule.raw_code, rule.raw_name),
            )

    def delete_rule(self, rule: ResearchCorrectionRule) -> None:
        run_sqlite_migrations(self.database_path)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "DELETE FROM research_correction_rules WHERE raw_code=? AND raw_name=?",
                (rule.raw_code, rule.raw_name),
            )


def parse_issue_target(target: str) -> tuple[str, str]:
    parts = target.strip().split(maxsplit=1)
    return (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0] if parts else "")


def apply_research_correction_rules(
    report: ResearchReport,
    rules: tuple[ResearchCorrectionRule, ...],
    directory: TaiwanStockDirectory | None,
) -> ResearchReport:
    """Apply only exact source identities; stale/conflicting Taiwan targets remain unresolved."""
    companies = {company.code: company for company in directory.companies} if directory else {}
    active = {(rule.raw_code, rule.raw_name): rule for rule in rules if rule.enabled}
    issues = list(report.verification_issues)
    classifications = list(report.entity_classifications)
    for issue in report.verification_issues:
        raw_code, raw_name = parse_issue_target(issue.target)
        rule = active.get((raw_code, raw_name))
        if rule is None:
            continue
        if rule.entity_type == "taiwan_stock":
            company = companies.get(rule.canonical_code)
            if company is None or company.name != rule.canonical_name:
                continue
        classification = EntityClassification(
            raw_code=raw_code,
            raw_name=raw_name,
            entity_type=rule.entity_type,
            canonical_code=rule.canonical_code,
            canonical_name=rule.canonical_name,
            evidence=issue.evidence,
            source_locator=issue.reference.display_locator() if issue.reference else "未判定",
        )
        if classification not in classifications:
            classifications.append(classification)
        issues = [item for item in issues if item != issue]
        if rule.entity_type == "taiwan_stock":
            issues.append(replace(issue, target=f"{rule.canonical_code} {rule.canonical_name}",
                                  status="已修正", evidence=f"人工確認並套用精確永久規則：{raw_code} {raw_name} → {rule.canonical_code} {rule.canonical_name}。"))

    def correct(code: str, name: str) -> tuple[str, str]:
        rule = active.get((code.strip(), name.strip()))
        if rule and rule.entity_type == "taiwan_stock":
            company = companies.get(rule.canonical_code)
            if company and company.name == rule.canonical_name:
                return company.code, company.name
        return code, name

    def apply_entity_classification(items: tuple, get_identity):
        result = []
        for item in items:
            code, name = get_identity(item)
            rule = active.get((code.strip(), name.strip()))
            if rule and rule.entity_type in {"sector", "non_stock"}:
                continue
            if rule and rule.entity_type in {"foreign_stock", "etf"}:
                result.append(
                    replace(
                        item,
                        stock=rule.canonical_code.strip() or code,
                        company=rule.canonical_name.strip() or name,
                    )
                )
                continue
            new_code, new_name = correct(code, name)
            result.append(replace(item, stock=new_code, company=new_name))
        return tuple(result)

    return replace(
        report,
        stock_opinions=apply_entity_classification(report.stock_opinions, lambda item: (item.stock, item.company)),
        stock_relations=apply_entity_classification(report.stock_relations, lambda item: (item.stock, item.company)),
        company_profiles=apply_entity_classification(report.company_profiles, lambda item: (item.stock, item.company)),
        technical_notes=apply_entity_classification(report.technical_notes, lambda item: (item.stock, item.company)),
        verification_issues=tuple(issues),
        entity_classifications=tuple(classifications),
    )
