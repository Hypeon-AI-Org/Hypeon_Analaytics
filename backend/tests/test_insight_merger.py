import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.insight_merger import merge_insights


def test_merge_similar():
    a = {"organization_id": "o1", "client_id": 1, "entity_type": "campaign", "entity_id": "c1_a1", "insight_type": "roas_decline", "evidence": [{"metric": "revenue", "value": 1}], "detected_by": ["trend_agent"], "confidence": 0.8}
    b = {"organization_id": "o1", "client_id": 1, "entity_type": "campaign", "entity_id": "c1_a1", "insight_type": "waste_zero_revenue", "evidence": [{"metric": "roas", "value": 0}], "detected_by": ["performance_agent"], "confidence": 0.9}
    merged = merge_insights([a, b])
    assert len(merged) == 1
    assert "performance_agent" in merged[0]["detected_by"] and "trend_agent" in merged[0]["detected_by"]
    assert len(merged[0]["evidence"]) == 2
