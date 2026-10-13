"""Conservative validators compare declarations, not arbitrary natural-language truth."""

from .models import Claim, Evidence, Finding

SUPPORTED = {"package_manager", "runtime", "script"}


def normalize(kind: str, value: str) -> str:
    if kind == "runtime":
        value = value.strip()
        return value[1:] if value.startswith("v") and value[1:2].isdigit() else value
    return value.strip()


def validate(claim: Claim, evidence: tuple[Evidence, ...]) -> Finding:
    if claim.kind not in SUPPORTED:
        return Finding(claim, "unsupported", f"Unsupported claim kind: {claim.kind}", evidence)
    if claim.kind == "package_manager" and claim.value not in {"npm", "pnpm", "yarn", "bun"}:
        return Finding(claim, "unsupported", "Package manager value must be npm, pnpm, yarn, or bun.", evidence)
    supported = [e for e in evidence if e.selector != "unsupported_source"]
    if len(supported) != len(evidence) or not supported:
        return Finding(claim, "unsupported", "One or more referenced sources cannot validate this claim type.", evidence)
    values = {normalize(claim.kind, e.value) for e in supported if e.value is not None}
    missing = [e for e in supported if e.value is None]
    if len(values) > 1 or (values and missing and claim.kind == "script"):
        return Finding(claim, "conflict", "Referenced sources contain different declarations; choose the intended scope or authority before correcting memory.", evidence)
    if not values:
        return Finding(claim, "stale_candidate", "The documented declaration is absent from every referenced supported source.", evidence)
    actual = next(iter(values))
    if normalize(claim.kind, claim.value) != actual:
        return Finding(claim, "stale_candidate", "The memory differs from the current source declaration; review the proposed value.", evidence, actual)
    return Finding(claim, "valid", "Memory matches the referenced declarations (no claim of runtime compatibility).", evidence)
