"""
Implements the minimum financial validation rules from section 4.4 of the
case study. Every check returns formula / operands / calculated_value /
reported_value / variance / status, using NOT_APPLICABLE whenever a
required input field is missing (never inventing values).
"""
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
TOL = settings.VALIDATION_TOLERANCE
TOL_PCT = settings.VALIDATION_TOLERANCE_PCT


def _val(field):
    """Extract numeric .value from an extracted-field dict, else None."""
    if not isinstance(field, dict):
        return field if isinstance(field, (int, float)) else None
    v = field.get("value")
    return v if isinstance(v, (int, float)) else None


def _tolerance_ok(calculated, reported) -> bool:
    if calculated is None or reported is None:
        return False
    diff = abs(calculated - reported)
    return diff <= max(TOL, abs(reported) * TOL_PCT)


def _check(name, formula, operands: dict, calculated, reported, period=None):
    missing = any(v is None for v in operands.values()) or reported is None
    if missing:
        return {
            "name": name, "formula": formula, "operands": operands,
            "calculated_value": calculated, "reported_value": reported,
            "variance": None, "status": "NOT_APPLICABLE", "period": period,
        }
    variance = round(calculated - reported, 4)
    status = "PASS" if _tolerance_ok(calculated, reported) else "FAIL"
    return {
        "name": name, "formula": formula, "operands": operands,
        "calculated_value": round(calculated, 4), "reported_value": round(reported, 4),
        "variance": variance, "status": status, "period": period,
    }


def validate(document_type: str, extracted: dict) -> dict:
    if document_type == "invoice":
        checks = _validate_invoice(extracted)
    elif document_type == "balance_sheet":
        checks = _validate_balance_sheet(extracted)
    elif document_type == "profit_and_loss":
        checks = _validate_profit_and_loss(extracted)
    elif document_type == "cash_flow_statement":
        checks = _validate_cash_flow(extracted)
    else:
        checks = []

    statuses = [c["status"] for c in checks]
    if "FAIL" in statuses:
        overall = "FAIL"
    elif all(s == "NOT_APPLICABLE" for s in statuses) and statuses:
        overall = "NOT_APPLICABLE"
    else:
        overall = "PASS"

    issues = [f"{c['name']}: reported {c['reported_value']} vs calculated {c['calculated_value']}"
              for c in checks if c["status"] == "FAIL"]
    return {"checks": checks, "overall_status": overall, "issues": issues}


def _validate_invoice(e: dict) -> list[dict]:
    checks = []
    subtotal, tax, discount, total = (_val(e.get(k)) for k in
                                       ("subtotal", "tax_amount", "discount", "total_amount"))
    discount = discount if discount is not None else 0.0
    if subtotal is not None:
        checks.append(_check(
            "invoice_total_check", "subtotal + tax_amount - discount",
            {"subtotal": subtotal, "tax_amount": tax, "discount": discount},
            (subtotal + (tax or 0) - discount) if tax is not None or True else None,
            total,
        ))

    line_items = e.get("line_items") or []
    if line_items:
        line_sum = 0.0
        line_calc_ok = True
        for li in line_items:
            qty, price, amount = li.get("quantity"), li.get("unit_price"), li.get("amount")
            if qty is not None and price is not None and amount is not None:
                checks.append(_check(
                    f"line_total_check[{li.get('description', '')[:20]}]",
                    "quantity * unit_price", {"quantity": qty, "unit_price": price},
                    qty * price, amount,
                ))
            if amount is not None:
                line_sum += amount
            else:
                line_calc_ok = False
        if line_calc_ok and line_items:
            checks.append(_check(
                "line_items_sum_reconciliation", "sum(line_items.amount)",
                {"line_item_count": len(line_items)}, line_sum, subtotal if subtotal is not None else total,
            ))
    return checks


def _validate_balance_sheet(e: dict) -> list[dict]:
    assets = _val(e.get("total_assets"))
    liabilities = _val(e.get("total_liabilities"))
    equity = _val(e.get("total_equity"))
    checks = []
    combined = None
    if liabilities is not None and equity is not None:
        combined = liabilities + equity
    checks.append(_check(
        "assets_equals_liabilities_plus_equity",
        "total_liabilities + total_equity", {"total_liabilities": liabilities, "total_equity": equity},
        combined, assets,
    ))
    return checks


def _validate_profit_and_loss(e: dict) -> list[dict]:
    revenue = _val(e.get("revenue"))
    cogs = _val(e.get("cost_of_sales"))
    gross_profit = _val(e.get("gross_profit"))
    opex = _val(e.get("operating_expenses"))
    op_profit = _val(e.get("operating_profit"))
    tax = _val(e.get("tax"))
    net_profit = _val(e.get("net_profit"))

    checks = []
    checks.append(_check(
        "gross_profit_check", "revenue - cost_of_sales",
        {"revenue": revenue, "cost_of_sales": cogs},
        (revenue - cogs) if revenue is not None and cogs is not None else None, gross_profit,
    ))
    checks.append(_check(
        "operating_profit_check", "gross_profit - operating_expenses",
        {"gross_profit": gross_profit, "operating_expenses": opex},
        (gross_profit - opex) if gross_profit is not None and opex is not None else None, op_profit,
    ))
    checks.append(_check(
        "net_profit_check", "operating_profit - tax",
        {"operating_profit": op_profit, "tax": tax},
        (op_profit - tax) if op_profit is not None and tax is not None else None, net_profit,
    ))
    return checks


def _validate_cash_flow(e: dict) -> list[dict]:
    ocf = _val(e.get("operating_cash_flow"))
    icf = _val(e.get("investing_cash_flow"))
    fcf = _val(e.get("financing_cash_flow"))
    opening = _val(e.get("opening_cash"))
    net_change = _val(e.get("net_change_in_cash"))
    closing = _val(e.get("closing_cash"))

    checks = []
    net_calc = None
    if ocf is not None and icf is not None and fcf is not None:
        net_calc = ocf + icf + fcf
    checks.append(_check(
        "net_change_in_cash_check",
        "operating_cash_flow + investing_cash_flow + financing_cash_flow",
        {"operating_cash_flow": ocf, "investing_cash_flow": icf, "financing_cash_flow": fcf},
        net_calc, net_change,
    ))
    closing_calc = None
    if opening is not None and net_change is not None:
        closing_calc = opening + net_change
    checks.append(_check(
        "closing_cash_check", "opening_cash + net_change_in_cash",
        {"opening_cash": opening, "net_change_in_cash": net_change},
        closing_calc, closing,
    ))
    return checks
