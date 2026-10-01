"""Deterministic Taiwan listed/OTC company-name and stock-code validation."""

from __future__ import annotations

import csv
import io
import ssl
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Iterable, Literal, Mapping, Protocol, Sequence
from urllib.request import Request, urlopen

from personal_stock_investment_system.research.sources import (
    ResearchReport,
    SourceReference,
    VerificationIssue,
    VerificationStatus,
)

TaiwanStockMarket = Literal["listed", "otc"]

TWSE_LISTED_COMPANIES_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
TWSE_OTC_COMPANIES_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"


@dataclass(frozen=True)
class TaiwanListedCompany:
    code: str
    name: str
    market: TaiwanStockMarket
    full_name: str = ""
    industry: str = ""
    source_url: str = ""
    source_updated_at: str = ""

    def names(self) -> tuple[str, ...]:
        values = {_normalize_name(self.name), _normalize_name(self.full_name)}
        return tuple(value for value in values if value)


@dataclass(frozen=True)
class TaiwanStockDirectory:
    companies: tuple[TaiwanListedCompany, ...]
    collected_at: str

    @classmethod
    def from_openapi_payloads(
        cls,
        listed_payload: Sequence[Mapping[str, object]],
        otc_payload: Sequence[Mapping[str, object]],
        *,
        collected_at: str | None = None,
    ) -> "TaiwanStockDirectory":
        companies = (
            *_parse_company_payload(listed_payload, market="listed", source_url=TWSE_LISTED_COMPANIES_URL),
            *_parse_company_payload(otc_payload, market="otc", source_url=TWSE_OTC_COMPANIES_URL),
        )
        unique = {company.code: company for company in companies if company.code}
        return cls(
            companies=tuple(sorted(unique.values(), key=lambda company: company.code)),
            collected_at=collected_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )


@dataclass(frozen=True)
class StockMentionVerification:
    raw_code: str
    raw_name: str
    status: VerificationStatus
    canonical_code: str = ""
    canonical_name: str = ""
    market: TaiwanStockMarket | None = None
    evidence: str = ""
    source_url: str = ""
    confidence: str = "低"


class TaiwanStockDirectoryClient(Protocol):
    def fetch_directory(self) -> TaiwanStockDirectory:
        """Return the current official listed and OTC company directory."""


class ReferenceDataSyncRecord(Protocol):
    started_at: str
    completed_at: str
    status: str
    record_count: int
    error: str


class TaiwanStockDirectoryRepository(Protocol):
    def replace_directory(
        self,
        directory: TaiwanStockDirectory,
        *,
        started_at: str | None = None,
    ) -> ReferenceDataSyncRecord:
        """Atomically replace active directory records."""

    def record_failed_sync(self, *, started_at: str, error: str) -> ReferenceDataSyncRecord:
        """Persist a failed synchronization attempt."""

    def load_directory(self) -> TaiwanStockDirectory | None:
        """Load the last successful local directory snapshot."""


@dataclass(frozen=True)
class TaiwanStockDirectorySyncResult:
    directory: TaiwanStockDirectory | None
    status: Literal["success", "failed"]
    status_message: str
    record_count: int = 0
    error: str = ""


class MopsCompanyDirectoryClient:
    """Fetch the daily listed/OTC company master files from official MOPS open data."""

    def __init__(self, *, timeout_seconds: float = 20.0) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_directory(self) -> TaiwanStockDirectory:
        return TaiwanStockDirectory.from_openapi_payloads(
            _fetch_csv_records(TWSE_LISTED_COMPANIES_URL, timeout_seconds=self.timeout_seconds),
            _fetch_csv_records(TWSE_OTC_COMPANIES_URL, timeout_seconds=self.timeout_seconds),
        )


def sync_taiwan_stock_directory(
    *,
    client: TaiwanStockDirectoryClient,
    repository: TaiwanStockDirectoryRepository,
) -> TaiwanStockDirectorySyncResult:
    """Fetch official data, persist atomically, and keep the last good local snapshot on failure."""

    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        directory = client.fetch_directory()
        _validate_sync_directory(directory)
    except Exception as error:  # noqa: BLE001 - adapter failures become an explicit sync state.
        repository.record_failed_sync(started_at=started_at, error=str(error))
        fallback = repository.load_directory()
        return TaiwanStockDirectorySyncResult(
            directory=fallback,
            status="failed",
            status_message=(
                "官方公司清單同步失敗，沿用本機最後成功版本。"
                if fallback is not None
                else "官方公司清單同步失敗，本機尚無可用版本。"
            ),
            record_count=len(fallback.companies) if fallback is not None else 0,
            error=str(error),
        )

    try:
        sync_record = repository.replace_directory(directory, started_at=started_at)
    except Exception as error:  # Repository records its own failed transaction.
        fallback = repository.load_directory()
        return TaiwanStockDirectorySyncResult(
            directory=fallback,
            status="failed",
            status_message=(
                "公司清單寫入本機資料庫失敗，沿用最後成功版本。"
                if fallback is not None
                else "公司清單寫入本機資料庫失敗，且沒有可用版本。"
            ),
            record_count=len(fallback.companies) if fallback is not None else 0,
            error=str(error),
        )

    persisted = repository.load_directory()
    return TaiwanStockDirectorySyncResult(
        directory=persisted,
        status="success",
        status_message=f"官方上市／上櫃公司清單已同步到本機 SQLite（{sync_record.record_count} 筆）。",
        record_count=sync_record.record_count,
    )


class TaiwanStockMentionVerifier:
    def __init__(self, directory: TaiwanStockDirectory) -> None:
        self.directory = directory
        self._by_code = {company.code: company for company in directory.companies}
        self._by_name: dict[str, list[TaiwanListedCompany]] = {}
        for company in directory.companies:
            for name in company.names():
                self._by_name.setdefault(name, []).append(company)

    def verify(self, code: str, name: str = "") -> StockMentionVerification:
        raw_code = code.strip()
        raw_name = name.strip()
        normalized_name = _normalize_name(raw_name)
        company_by_code = self._by_code.get(raw_code)
        companies_by_name = self._by_name.get(normalized_name, []) if normalized_name else []

        if company_by_code is not None:
            if not normalized_name or normalized_name in company_by_code.names():
                return _result(
                    raw_code,
                    raw_name,
                    company_by_code,
                    status="已查證",
                    evidence=f"官方公司清單確認 {company_by_code.code} 為 {company_by_code.name}。",
                    confidence="高",
                )
            return _result(
                raw_code,
                raw_name,
                company_by_code,
                status="衝突",
                evidence=(
                    f"代號 {raw_code} 的官方公司名稱為 {company_by_code.name}，"
                    f"與來源名稱 {raw_name or '未提供'} 不一致。"
                ),
                confidence="高",
            )

        if len(companies_by_name) == 1:
            candidate = companies_by_name[0]
            if not raw_code:
                return _result(
                    raw_code,
                    raw_name,
                    candidate,
                    status="已查證",
                    evidence=f"官方公司清單確認 {candidate.name} 的代號為 {candidate.code}。",
                    confidence="高",
                )
            return _result(
                raw_code,
                raw_name,
                candidate,
                status="疑似錯誤",
                evidence=f"官方清單中的 {candidate.name} 代號為 {candidate.code}，不是 {raw_code or '未提供'}。",
                confidence="中",
            )

        if len(companies_by_name) > 1:
            candidates = "、".join(f"{item.code} {item.name}" for item in companies_by_name)
            return StockMentionVerification(
                raw_code=raw_code,
                raw_name=raw_name,
                status="待查證",
                evidence=f"公司名稱命中多筆候選：{candidates}。",
                confidence="低",
            )

        return StockMentionVerification(
            raw_code=raw_code,
            raw_name=raw_name,
            status="待查證",
            evidence="官方上市／上櫃公司清單找不到可確定的代號與公司名稱組合。",
            confidence="低",
        )


def verify_research_report_stock_mentions(
    report: ResearchReport,
    directory: TaiwanStockDirectory,
) -> ResearchReport:
    """Attach deterministic stock identity checks and normalize only verified names."""

    verifier = TaiwanStockMentionVerifier(directory)
    mentions = _report_mentions(report)
    results = {(code, name): verifier.verify(code, name) for code, name, _reference in mentions}
    references = {(code, name): reference for code, name, reference in mentions}
    issues = tuple(
        _verification_issue(result, references[(code, name)], directory.collected_at)
        for (code, name), result in results.items()
    )
    retained_issues = tuple(
        issue for issue in report.verification_issues if not _is_stock_identity_issue(issue)
    )

    return replace(
        report,
        stock_opinions=tuple(
            replace(
                item,
                stock=_verified_code(results.get((item.stock, item.company)), item.stock),
                company=_verified_name(results.get((item.stock, item.company)), item.company),
            )
            for item in report.stock_opinions
        ),
        stock_relations=tuple(
            replace(
                item,
                stock=_verified_code(results.get((item.stock, item.company)), item.stock),
                company=_verified_name(results.get((item.stock, item.company)), item.company),
            )
            for item in report.stock_relations
        ),
        company_profiles=tuple(
            replace(
                item,
                stock=_verified_code(results.get((item.stock, item.company)), item.stock),
                company=_verified_name(results.get((item.stock, item.company)), item.company),
            )
            for item in report.company_profiles
        ),
        verification_issues=retained_issues + issues,
    )


def _parse_company_payload(
    payload: Sequence[Mapping[str, object]],
    *,
    market: TaiwanStockMarket,
    source_url: str,
) -> tuple[TaiwanListedCompany, ...]:
    companies: list[TaiwanListedCompany] = []
    for item in payload:
        code = _field(item, "公司代號", "公司代碼", "SecuritiesCompanyCode")
        name = _field(item, "公司簡稱", "公司名稱", "CompanyAbbreviation")
        full_name = _field(item, "公司名稱", "CompanyName")
        industry = _field(item, "產業別", "Industry")
        source_updated_at = _field(item, "出表日期", "資料日期", "Date")
        if code and name:
            companies.append(
                TaiwanListedCompany(
                    code=code,
                    name=name,
                    full_name=full_name,
                    industry=industry,
                    market=market,
                    source_url=source_url,
                    source_updated_at=source_updated_at,
                )
            )
    return tuple(companies)


def _validate_sync_directory(directory: TaiwanStockDirectory) -> None:
    markets = {company.market for company in directory.companies}
    if not directory.companies:
        raise ValueError("Official company directory is empty.")
    if markets != {"listed", "otc"}:
        raise ValueError("Official company directory must contain both listed and OTC companies.")
    codes = [company.code for company in directory.companies]
    if len(codes) != len(set(codes)):
        raise ValueError("Official company directory contains duplicate stock codes.")


def _fetch_csv_records(url: str, *, timeout_seconds: float) -> list[Mapping[str, object]]:
    request = Request(url, headers={"Accept": "text/csv", "User-Agent": "psis-stock-validator/0.1"})
    context = ssl.create_default_context()
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        # TWSE currently serves a chain without Subject Key Identifier. Python 3.13's
        # strict flag rejects it; clearing only this optional flag keeps CA and host checks.
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    with urlopen(  # noqa: S310 - fixed official HTTPS endpoints with certificate verification.
        request,
        timeout=timeout_seconds,
        context=context,
    ) as response:
        text = response.read().decode("utf-8-sig")
    return [dict(item) for item in csv.DictReader(io.StringIO(text))]


def _field(item: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _normalize_name(value: str) -> str:
    normalized = "".join(value.split()).replace("臺", "台")
    for suffix in ("股份有限公司", "有限公司"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized.casefold()


def _result(
    raw_code: str,
    raw_name: str,
    company: TaiwanListedCompany,
    *,
    status: VerificationStatus,
    evidence: str,
    confidence: str,
) -> StockMentionVerification:
    return StockMentionVerification(
        raw_code=raw_code,
        raw_name=raw_name,
        status=status,
        canonical_code=company.code,
        canonical_name=company.name,
        market=company.market,
        evidence=evidence,
        source_url=company.source_url,
        confidence=confidence,
    )


def _report_mentions(report: ResearchReport) -> tuple[tuple[str, str, SourceReference | None], ...]:
    candidates: Iterable[tuple[str, str, SourceReference | None]] = (
        *((item.stock, item.company, item.reference) for item in report.stock_opinions),
        *((item.stock, item.company, item.reference) for item in report.stock_relations),
        *((item.stock, item.company, item.reference) for item in report.company_profiles),
        *((item.stock, "", item.reference) for item in report.technical_notes),
    )
    mentions: dict[str, tuple[str, str, SourceReference | None]] = {}
    for code, name, reference in candidates:
        cleaned_code = code.strip()
        cleaned_name = name.strip()
        if not cleaned_code and not cleaned_name:
            continue
        key = cleaned_code or f"name:{_normalize_name(cleaned_name)}"
        existing = mentions.get(key)
        if existing is None or (not existing[1] and cleaned_name):
            mentions[key] = (cleaned_code, cleaned_name, reference)
    return tuple(mentions.values())


def _verification_issue(
    result: StockMentionVerification,
    reference: SourceReference | None,
    collected_at: str,
) -> VerificationIssue:
    raw_target = " ".join(value for value in (result.raw_code, result.raw_name) if value) or "未判定"
    candidate = " ".join(value for value in (result.canonical_code, result.canonical_name) if value)
    evidence = result.evidence
    if candidate and result.status != "已查證":
        evidence = f"{evidence}；候選：{candidate}"
    if collected_at:
        evidence = f"{evidence}；清單取得時間：{collected_at}"
    return VerificationIssue(
        item_type="股票代號／公司名稱",
        target=raw_target,
        claim=f"{result.raw_code or '未提供代號'} 是 {result.raw_name or '未提供公司名稱'}",
        status=result.status,
        evidence=evidence,
        external_sources=(result.source_url,) if result.source_url else (),
        reference=reference,
        confidence=result.confidence,
    )


def _verified_name(result: StockMentionVerification | None, original: str) -> str:
    if result is not None and result.status == "已查證" and result.canonical_name:
        return result.canonical_name
    return original


def _verified_code(result: StockMentionVerification | None, original: str) -> str:
    if result is not None and result.status == "已查證" and result.canonical_code:
        return result.canonical_code
    return original


def _is_stock_identity_issue(issue: VerificationIssue) -> bool:
    return any(keyword in issue.item_type for keyword in ("股票", "公司名稱", "公司名", "代號", "代碼"))
