#!/usr/bin/env python3
"""Invariants registry — Reflex #5 «причинная память».

Loads data/invariants.json (PROTECTED) and verifies each invariant against the
current state of the codebase / public/ site.

PROTECTED CONTRACT:
  • This file is in brain_toolsmith.PROTECTED_AGENTS — the brain cannot weaken
    or remove invariants via edit_agents.
  • data/invariants.json is also PROTECTED — only deliberate owner commits add
    new invariants (after a root cause is solved). The brain can PROPOSE a new
    invariant via needs_help; the owner decides.

check_type semantics:
  structural  — fast regex/presence check, no LLM, runs in milliseconds.
  semantic    — delegates to page_reviewer (LLM); used only for halal/brand
                integrity where regex produces false negatives (ar-pork lesson).

Usage:
    from invariants import verify_invariants
    violations = verify_invariants()          # returns list of dicts
    ok = len(violations) == 0

    # Or from CLI for smoke-testing:
    python3 scripts/invariants.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT    = Path(__file__).resolve().parent.parent
DATA    = ROOT / "data"
PUBLIC  = ROOT / "public"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

REGISTRY = DATA / "invariants.json"


def _load_registry() -> list[dict]:
    try:
        d = json.loads(REGISTRY.read_text(encoding="utf-8"))
        return d.get("invariants", [])
    except Exception as e:
        print(f"⚠️  invariants: cannot load registry: {e}", file=sys.stderr)
        return []


# ── Structural checkers ────────────────────────────────────────────────────────

def _check_card_link_wrapper(inv: dict) -> list[str]:
    """index.html must have product-card-link anchors (in rendered HTML or JS template)."""
    detail = inv.get("check_detail", {})
    fpath = ROOT / detail.get("file", "public/index.html")
    pattern = detail.get("pattern", r'class=["\'][^"\']*product-card-link')
    try:
        html = fpath.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{inv['id']}: cannot read {fpath}: {e}"]

    if not re.search(pattern, html, re.I):
        return [
            f"{inv['id']}: product-card-link anchor missing in {fpath.name}. "
            "Product cards are not clickable."
        ]
    return []


def _check_no_fake_reviews(inv: dict) -> list[str]:
    """fix_schema.py must contain the explicit carve-out for aggregateRating.

    We check the CODE, not every page in public/ — pre-existing pages may still
    have aggregateRating from older generations and will be cleaned by fix_schema
    over time.  The invariant protects the enricher from re-adding the field.
    """
    detail = inv.get("check_detail", {})
    fpath = SCRIPTS / detail.get("file", "fix_schema.py").replace("scripts/", "")
    required = detail.get("required_patterns", [
        "aggregateRating are intentionally NOT touched",
    ])
    try:
        src = fpath.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{inv['id']}: cannot read {fpath}: {e}"]

    missing = [p for p in required if p not in src]
    if missing:
        return [
            f"{inv['id']}: fix_schema.py no longer has the aggregateRating carve-out. "
            f"Missing: {missing}. Someone may have added fake ratings back."
        ]
    return []


def _check_fix_links_script_stash(inv: dict) -> list[str]:
    """fix_links.py must contain the three script-stash patterns."""
    detail = inv.get("check_detail", {})
    fpath = SCRIPTS / detail.get("file", "fix_links.py").replace("scripts/", "")
    required = detail.get("required_patterns", [])
    try:
        src = fpath.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{inv['id']}: cannot read {fpath}: {e}"]

    missing = [p for p in required if p not in src]
    if missing:
        return [
            f"{inv['id']}: fix_links.py script-stash missing: {missing}. "
            "fix_links may unwrap JS template literals again."
        ]
    return []


def _check_contacts_canonical(inv: dict) -> list[str]:
    """brand_system.py must hardcode the canonical phone + email."""
    detail = inv.get("check_detail", {})
    fpath = SCRIPTS / detail.get("file", "brand_system.py").replace("scripts/", "")
    required = detail.get("required_patterns", [])
    try:
        src = fpath.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{inv['id']}: cannot read {fpath}: {e}"]

    missing = [p for p in required if p not in src]
    if missing:
        return [
            f"{inv['id']}: canonical contacts missing from brand_system.py: {missing}. "
            "If contacts changed, update this invariant deliberately."
        ]
    return []


def _check_docs_in_process_code_anchor(inv: dict) -> list[str]:
    """generate_geo_bulk.py must contain in_process cert blocks and docs_status branch."""
    detail = inv.get("check_detail", {})
    anchor = detail.get("code_anchor", {})
    fname = anchor.get("file", "scripts/generate_geo_bulk.py").replace("scripts/", "")
    fpath = SCRIPTS / fname
    # Support both list (new) and single string (legacy) patterns
    required_raw = anchor.get("required_patterns") or anchor.get("required_pattern")
    if isinstance(required_raw, str):
        required = [required_raw]
    elif isinstance(required_raw, list):
        required = required_raw
    else:
        required = ["CERT_BLOCK_AR_IN_PROCESS"]

    try:
        src = fpath.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{inv['id']}: cannot read {fpath}: {e}"]

    missing = [p for p in required if not re.search(p, src, re.I)]
    if missing:
        return [
            f"{inv['id']}: in-process cert anchor missing from {fname}: {missing}. "
            "AR/Gulf pages may overclaim certifications for in_process markets."
        ]
    return []


# ── Semantic checker (delegates to page_reviewer) ─────────────────────────────

def _check_ar_no_pork_semantic(inv: dict) -> list[str]:
    """Scan all /ar/ pages with خنزير → page_reviewer semantic verdict."""
    detail = inv.get("check_detail", {})
    scope_glob = detail.get("scope", "public/ar/**/*.html")
    pre_filter = detail.get("pre_filter_pattern", "خنزير")
    meta_extra = detail.get("meta", {})

    pre_re = re.compile(pre_filter, re.UNICODE)

    # Determine scope
    scope_dir = PUBLIC / "ar"
    candidate_files = list(scope_dir.rglob("*.html")) if scope_dir.exists() else []

    flagged = [f for f in candidate_files
               if pre_re.search(f.read_text(encoding="utf-8", errors="ignore"))]

    if not flagged:
        return []  # no خنزير pages → invariant trivially satisfied

    try:
        import page_reviewer as pr
    except Exception as e:
        return [f"{inv['id']}: page_reviewer import failed: {e}"]

    violations: list[str] = []
    for fpath in flagged:
        meta = {"CONTAINS_KHANZIR": True, "invariant_check": True, **meta_extra}
        try:
            result = pr.review_page(fpath, meta=meta)
        except Exception as e:
            violations.append(f"{inv['id']}: page_reviewer error on {fpath.name}: {e}")
            continue
        if result.get("verdict") in ("reject", "hold"):
            reasons = "; ".join(result.get("reasons", []))[:120]
            violations.append(
                f"{inv['id']}: pork-as-product violation in {fpath.name}: {reasons}"
            )
    return violations


# ── Dispatcher ────────────────────────────────────────────────────────────────

def _check_single_prod_branch(inv: dict) -> list[str]:
    """ALL .github/workflows/*.yml must not reference non-main long-lived branches.

    Scans every workflow file for explicit branch references that point to a
    branch other than main.  Catches:
      - checkout: ref: STARTUP-AIO
      - on.push.branches: [STARTUP-AIO]
      - branches: [STARTUP-AIO]  (any context)

    Exemptions (legitimate non-main refs):
      - 'pull_request' triggers that list source branches (expected)
      - commented-out lines
    """
    workflows_dir = ROOT / ".github" / "workflows"
    if not workflows_dir.exists():
        return []

    # Any explicit long-lived branch that is NOT main.
    # We check for the known historical offender and the general pattern of
    # hardcoded non-main branch names in checkout ref or push branches blocks.
    FORBIDDEN_BRANCHES = [
        r"STARTUP-AIO",
        r"STARTUP_AIO",
    ]

    violations: list[str] = []
    for fpath in sorted(workflows_dir.glob("*.yml")):
        try:
            src = fpath.read_text(encoding="utf-8")
        except Exception as e:
            violations.append(f"{inv['id']}: cannot read {fpath.name}: {e}")
            continue

        # Strip comment lines before scanning
        active_lines = "\n".join(
            line for line in src.splitlines()
            if not line.lstrip().startswith("#")
        )

        for branch in FORBIDDEN_BRANCHES:
            if re.search(branch, active_lines):
                # Confirm it's a real branch reference, not just a string mention
                # (e.g. in a commit message or echo). Look for YAML keys around it.
                context_re = re.compile(
                    r'(?:ref:|branches:|\[)[^\n]*' + branch,
                    re.I,
                )
                if context_re.search(active_lines):
                    violations.append(
                        f"{inv['id']}: {fpath.name} references non-prod branch "
                        f"'{branch}' in a checkout ref or push trigger. "
                        "All workflows must target main."
                    )
                    break  # one report per file

    return violations


_STRUCTURAL_CHECKS: dict[str, Any] = {
    "card-link-wrapper":            _check_card_link_wrapper,
    "no-fake-reviews":              _check_no_fake_reviews,
    "fix-links-script-stash":       _check_fix_links_script_stash,
    "contacts-canonical":           _check_contacts_canonical,
    "single-prod-branch":           _check_single_prod_branch,
}

_SEMANTIC_CHECKS: dict[str, Any] = {
    "ar-no-pork-as-product":        _check_ar_no_pork_semantic,
    # docs-in-process: semantic side via page_reviewer at publish time;
    # code anchor checked separately via _CODE_ANCHOR_CHECKS (always structural).
    "docs-in-process-no-overclaim": _check_docs_in_process_code_anchor,
}

# Code-anchor checks always run regardless of semantic flag — they are fast regex
# on source files, not LLM calls, even when the invariant is classified "semantic".
_CODE_ANCHOR_CHECKS: dict[str, Any] = {
    "docs-in-process-no-overclaim": _check_docs_in_process_code_anchor,
}


def verify_invariants(semantic: bool = True) -> list[dict]:
    """Run all registered invariant checks.

    Args:
        semantic: if False, skip LLM-based (page_reviewer) checks — fast mode
                  suitable for pre-commit hooks on every deploy.
                  If True (default), also runs semantic checks.

    Returns:
        List of violation dicts: {"id", "description", "violations": [str]}.
        Empty list = all invariants satisfied.
    """
    registry = _load_registry()
    all_violations: list[dict] = []

    for inv in registry:
        inv_id = inv.get("id", "unknown")
        check_type = inv.get("check_type", "structural")
        violations: list[str] = []

        print(f"  🔎 [{inv_id}] ({check_type}) …", end=" ", flush=True)

        if check_type == "structural":
            fn = _STRUCTURAL_CHECKS.get(inv_id)
            if fn:
                violations = fn(inv)
            else:
                print(f"⚠️  no checker registered for structural invariant '{inv_id}'")
                continue

        elif check_type == "semantic":
            # Always run code-anchor part (fast, no LLM).
            anchor_fn = _CODE_ANCHOR_CHECKS.get(inv_id)
            if anchor_fn:
                violations = anchor_fn(inv)

            if not semantic:
                # Fast mode: skip LLM part, only anchor was checked above.
                if not anchor_fn:
                    print("skip (fast mode)")
                    continue
            else:
                # Full mode: also run LLM semantic check.
                sem_fn = _SEMANTIC_CHECKS.get(inv_id)
                if sem_fn:
                    violations += sem_fn(inv)
                elif not anchor_fn:
                    print(f"⚠️  no checker registered for semantic invariant '{inv_id}'")
                    continue

        if violations:
            print(f"✗ {len(violations)} violation(s)")
            all_violations.append({
                "id": inv_id,
                "description": inv.get("description", ""),
                "violations": violations,
            })
        else:
            print("✅")

    return all_violations


def _emit_violations(violations: list[dict], context: str = "") -> None:
    """Emit needs_help (structural) or emergency (semantic halal) to daily_ledger."""
    if not violations:
        return
    halal_ids = {"ar-no-pork-as-product"}
    for v in violations:
        is_halal = v["id"] in halal_ids
        category = "emergency" if is_halal else "needs_help"
        msg = (
            f"🚨 invariant violated [{v['id']}]{' (' + context + ')' if context else ''}:\n"
            + "\n".join(f"  • {line}" for line in v["violations"][:5])
        )
        print(f"\n{msg}")
        try:
            from daily_ledger import append_event
            append_event(category, msg)
        except Exception as e:
            print(f"  ledger failed: {e}")
            if is_halal:
                try:
                    from telegram_notify import notify_emergency
                    notify_emergency(msg)
                except Exception:
                    pass


def main() -> int:
    print("\n📋 Invariant verification\n" + "─" * 50)
    violations = verify_invariants(semantic=True)
    if violations:
        _emit_violations(violations, context="manual run")
        print(f"\n🚨 {len(violations)} invariant(s) violated.")
        return 2
    print(f"\n✅ All invariants satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
