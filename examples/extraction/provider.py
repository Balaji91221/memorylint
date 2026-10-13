"""Demonstration bridge only: replace complete() with your chosen model client."""
import json
import sys
from pathlib import Path

def complete(request):
    # The fixture costs zero. A real provider must reserve/enforce the supplied
    # token/cost budgets before calling a model and report actual usage afterward.
    assert request["prompt_version"] == "explicit-repository-claims-v1"
    assert "allowed_sources" in request
    return json.loads(Path(__file__).with_name("response.json").read_text())

if __name__ == "__main__":
    print(json.dumps(complete(json.load(sys.stdin))))
