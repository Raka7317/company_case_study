from app.services import financial_validation_service as fvs
from app.utils.numbers import parse_number, find_numbers


def test_parse_number_handles_parentheses_as_negative():
    assert parse_number("(1,234.50)") == -1234.50


def test_parse_number_handles_currency_symbol():
    assert parse_number("$13,125.00") == 13125.00


def test_find_numbers_multiple():
    assert find_numbers("12,500.00 625.00 13,125.00") == [12500.00, 625.00, 13125.00]


def test_invoice_validation_pass():
    extracted = {
        "subtotal": {"value": 12500.00}, "tax_amount": {"value": 625.00},
        "discount": {"value": 0.00}, "total_amount": {"value": 13125.00},
        "line_items": [],
    }
    result = fvs.validate("invoice", extracted)
    assert result["overall_status"] == "PASS"
    assert result["checks"][0]["status"] == "PASS"


def test_invoice_validation_fail_on_mismatch():
    extracted = {
        "subtotal": {"value": 100.00}, "tax_amount": {"value": 5.00},
        "discount": {"value": 0.00}, "total_amount": {"value": 999.00},
        "line_items": [],
    }
    result = fvs.validate("invoice", extracted)
    assert result["overall_status"] == "FAIL"


def test_balance_sheet_not_applicable_when_missing():
    extracted = {"total_assets": {"value": None}, "total_liabilities": {"value": None}, "total_equity": {"value": None}}
    result = fvs.validate("balance_sheet", extracted)
    assert result["checks"][0]["status"] == "NOT_APPLICABLE"
