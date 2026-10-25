"""The **accepted** ratchet baseline: the receipt the last green wave accepted.

Why this module exists (wave 15 / W2)
--------------------------------------
Wave 14 (Z4) measured a residual that grew by **+9,359 px (+9.3 %)** and the
ratchet **did not catch it**.  The reason was an instrument defect, not a
measurement problem: the ratchet baseline lived *inside the package
directory* (``<package>/baseline/baseline-report.json``).  A run in a **new**
package directory therefore started from the historical wave-4 reference
report (168,357 px) instead of the previous wave's accepted receipt (wave 13:
100,210 px) -- so the wave-13 -> wave-14 regression was never compared with
anything.

The fix is to keep the baseline **outside every package directory** and to
promote it only from a receipt that is green all the way:

* the baseline lives in one stable directory (default
  ``build/s49-package/baseline-accepted/``), so changing the package
  directory cannot reset it;
* only a receipt with ``ok: true`` and ``failed_step: null`` may be
  promoted -- a package whose build step or judgment step was red is
  **not** an accepted state and must never become the baseline;
* the baseline records the ROM sha256 of both sides, so a later wave can
  say "not comparable" instead of silently passing.

Nothing here measures anything: it only moves a report document around and
keeps its provenance.
"""

from __future__ import annotations

import datetime
import json
import pathlib

from s49_fidelity_report.capture import write_text

ACCEPTED_SCHEMA = "konoha.s49-accepted-baseline.v1"

#: The packages the pipeline writes are named ``s49-package*``.
PACKAGE_GLOB = "s49-package*"

#: Where the judgment bench's report lands inside a package directory.
REPORT_RELATIVE = ("work", "s49-report", "report.json")


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _read_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _is_under(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def package_report_path(package: pathlib.Path) -> pathlib.Path:
    return package.joinpath(*REPORT_RELATIVE)


class AcceptedBaseline:
    """The store: one accepted report plus the receipt that accepted it."""

    def __init__(self, root: pathlib.Path):
        self.root = pathlib.Path(root)
        self.report_path = self.root / "report.json"
        self.receipt_path = self.root / "receipt.json"

    # -- reading ---------------------------------------------------------
    def exists(self) -> bool:
        return self.report_path.is_file()

    def load_report(self) -> dict | None:
        if not self.report_path.is_file():
            return None
        return _read_json(self.report_path)

    def load_receipt(self) -> dict | None:
        if not self.receipt_path.is_file():
            return None
        return _read_json(self.receipt_path)

    def describe(self) -> dict:
        """A short description of the accepted baseline, for a receipt."""
        receipt = self.load_receipt() or {}
        report = self.load_report() or {}
        summary = (report.get("summary") or {}).get("field_residual") or {}
        captures = report.get("captures") or {}
        return {
            "root": str(self.root),
            "exists": self.exists(),
            "accepted_at": receipt.get("accepted_at"),
            "source_package": receipt.get("source_package"),
            "source_receipt": receipt.get("source_receipt"),
            "rom": {side: (captures.get(side) or {}).get("rom_sha256")
                    for side in ("original", "remake")},
            "content_sha256": report.get("content_sha256"),
            "field_residual_sum": summary.get("sum"),
            "history": receipt.get("history") or [],
        }

    # -- writing ---------------------------------------------------------
    def promote(self, report: dict, *, source_package: str,
                source_receipt: str, note: str = "") -> dict:
        """Make *report* the accepted baseline and write the receipt.

        The previous accepted receipt is kept in the history of the new one,
        so the chain of accepted waves stays readable.
        """
        self.root.mkdir(parents=True, exist_ok=True)
        previous = self.load_receipt() or {}
        summary = (report.get("summary") or {}).get("field_residual") or {}
        captures = report.get("captures") or {}
        history = list(previous.get("history") or [])
        if previous.get("accepted_at"):
            history.append({
                "accepted_at": previous.get("accepted_at"),
                "source_package": previous.get("source_package"),
                "source_receipt": previous.get("source_receipt"),
                "rom": previous.get("rom"),
                "field_residual_sum": previous.get("field_residual_sum"),
            })
        write_text(self.report_path,
                   json.dumps(report, ensure_ascii=False, indent=1) + "\n")
        receipt = {
            "schema": ACCEPTED_SCHEMA,
            "accepted_at": _now(),
            "source_package": source_package,
            "source_receipt": source_receipt,
            "rom": {side: (captures.get(side) or {}).get("rom_sha256")
                    for side in ("original", "remake")},
            "content_sha256": report.get("content_sha256"),
            "field_residual_sum": summary.get("sum"),
            "field_residual": summary,
            "note": note,
            "history": history,
        }
        write_text(self.receipt_path,
                   json.dumps(receipt, ensure_ascii=False, indent=1) + "\n")
        return receipt


def find_last_accepted_package(build_root: pathlib.Path) -> dict | None:
    """The most recent package whose receipt is green all the way.

    "Green all the way" means ``ok: true`` **and** ``failed_step: null``
    **and** the judgment bench really produced a report.  A package whose
    build step was red (the ROM could not be pinned) or whose judgment step
    was red (the bench crashed) is **not** an accepted state and is skipped
    even when it has a report on disk.
    """
    build_root = pathlib.Path(build_root)
    if not build_root.is_dir():
        return None
    candidates = []
    for receipt_path in build_root.glob(f"{PACKAGE_GLOB}/receipt.json"):
        try:
            candidates.append((receipt_path.stat().st_mtime, receipt_path))
        except OSError:
            continue
    for _mtime, receipt_path in sorted(candidates, reverse=True):
        package = receipt_path.parent
        document = _read_json(receipt_path)
        if not document:
            continue
        if document.get("ok") is not True:
            continue
        if document.get("failed_step") is not None:
            continue
        report_path = package_report_path(package)
        if not report_path.is_file():
            continue
        return {
            "package": str(package),
            "receipt": str(receipt_path),
            "report": str(report_path),
            "accepted_at": document.get("generated_at"),
            "report_document": _read_json(report_path),
        }
    return None


def promote_package(package: pathlib.Path, root: pathlib.Path,
                    note: str = "") -> tuple[bool, str]:
    """Promote a package to the accepted baseline.

    Returns ``(ok, detail)``.  A package that is not green all the way is
    **refused**: that is the whole point of the store -- a failed run must
    never become the thing the next wave is compared against.
    """
    package = pathlib.Path(package)
    receipt_path = package / "receipt.json"
    if not receipt_path.is_file():
        return False, f"the package has no receipt: {receipt_path}"
    document = _read_json(receipt_path)
    if not document:
        return False, f"the package's receipt is not valid JSON: {receipt_path}"
    if document.get("ok") is not True or document.get("failed_step") is not None:
        return False, (
            f"the package is NOT an accepted state (ok={document.get('ok')}, "
            f"failed_step={document.get('failed_step')}) => it must not become "
            "the ratchet baseline")
    report_path = package_report_path(package)
    if not report_path.is_file():
        return False, f"the package has no judgment bench report: {report_path}"
    report = _read_json(report_path)
    if not report:
        return False, f"the package's report is not valid JSON: {report_path}"
    store = AcceptedBaseline(root)
    receipt = store.promote(report, source_package=str(package),
                            source_receipt=str(receipt_path), note=note)
    return True, (f"accepted {package} (accepted_at {receipt['accepted_at']}, "
                  f"field residual sum {receipt.get('field_residual_sum')} px, "
                  f"ROM {str(receipt.get('rom', {}).get('remake'))[:16]}...)")
