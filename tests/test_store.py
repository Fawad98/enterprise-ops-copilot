# tests/test_store.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp_server"))
from store import OrderStore


def test_replacement_refused_on_refunded_order():
    s = OrderStore()
    result = s.create_replacement("ORD-1019", "test")
    assert "error" in result
    assert "refunded" in result["error"]


def test_replacement_capped_per_order():
    s = OrderStore()
    first = s.create_replacement("ORD-1012", "damaged")
    assert first["replacement_for"] == "ORD-1012"
    assert first["total"] == 0.0
    second = s.create_replacement("ORD-1012", "again")
    assert "error" in second


def test_unfiltered_list_refused():
    s = OrderStore()
    result = s.list()
    assert isinstance(result, dict) and "error" in result


def test_filtered_list_permitted():
    s = OrderStore()
    result = s.list(status="refunded")
    assert isinstance(result, list)