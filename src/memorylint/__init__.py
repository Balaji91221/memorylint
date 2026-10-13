"""MemoryLint SDK; scans are read-only unless an index is explicitly requested."""

from .models import Claim, Evidence, Finding, ScanResult
from .scanner import scan_memory
from .index import DependencyIndex
from .review import ProposedPatch, propose_patch, apply_patch
from .extraction import ExtractionLimits, CommandProvider, FixtureProvider, extract_claims

__all__ = ["Claim", "Evidence", "Finding", "ScanResult", "scan_memory", "DependencyIndex",
           "ProposedPatch", "propose_patch", "apply_patch", "ExtractionLimits", "CommandProvider",
           "FixtureProvider", "extract_claims"]
