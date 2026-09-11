"""
Field & table extraction.

Primary path: send the OCR/parsed text to an LLM with a strict "return
JSON only, use null for anything not present" instruction, per document
type. This is what the case study calls "AI-based field & table
extraction". Either Anthropic Claude or OpenAI can be used -- whichever
API key is configured (Anthropic takes priority if both are set).

Fallback path: if no API key is configured, or the LLM call fails for
any reason, a deterministic regex/keyword based extractor runs instead
so the pipeline always produces a result. Every value returned is
either taken verbatim from the extracted text or is null -- nothing is
invented.
"""
import json
import re
from app.core.config import settings
from app.core.logging import get_logger
from app.services.ocr_service import PageText
from app.utils.numbers import parse_number, find_numbers

logger = get_logger(__name__)

REQUIRED_FIELDS = {
    "invoice": ["invoice_number", "invoice_date", "vendor_name", "customer_name",
                "currency", "subtotal", "tax_amount", "discount", "total_amount"],
    "balance_sheet": ["total_assets", "total_liabilities", "total_equity"],
    "profit_and_loss": ["revenue", "cost_of_sales", "gross_profit",
                         "operating_expenses", "operating_profit", "tax", "net_profit"],
    "cash_flow_statement": ["operating_cash_flow", "investing_cash_flow", "financing_cash_flow",
                             "opening_cash", "net_change_in_cash", "closing_cash"],
}

_SYNONYMS = {
    "total_assets": ["total assets"],
    "total_liabilities": ["total liabilities", "total capital and liabilities", "total capital & liabilities"],
    "total_equity": ["total equity", "shareholders equity", "shareholders' equity", "total capital"],
    "revenue": ["revenue", "total income", "interest earned", "net sales", "total revenue"],
    "cost_of_sales": ["cost of sales", "cost of goods sold", "cogs"],
    "gross_profit": ["gross profit"],
    "operating_expenses": ["operating expenses", "operating expenditure", "total expenditure"],
    "operating_profit": ["operating profit", "profit before tax", "operating income"],
    "tax": ["tax", "income tax", "provision for tax"],
    "net_profit": ["net profit", "profit for the year", "net income", "profit after tax"],
    "operating_cash_flow": ["net cash flow from operating activities", "cash flow from operating activities",
                             "net cash generated from operating activities"],
    "investing_cash_flow": ["net cash flow from investing activities", "cash flow from investing activities"],
    "financing_cash_flow": ["net cash flow from financing activities", "cash flow from financing activities"],
    "opening_cash": ["opening cash", "cash and cash equivalents at beginning", "cash at beginning of the year"],
    "net_change_in_cash": ["net increase in cash", "net change in cash", "net (decrease)/increase in cash"],
    "closing_cash": ["closing cash", "cash and cash equivalents at end", "cash at end of the year"],
}


def _full_text_with_pages(pages: list[PageText]) -> str:
    return "\n".join(f"[PAGE {p.page_number}]\n{p.text}" for p in pages)


def extract_fields(document_type: str, pages: list[PageText]) -> tuple[dict, str]:
    """Returns (extracted_data, method) where method is 'llm' or 'rule_based'.

    Provider priority: Anthropic -> OpenAI -> Google Gemini -> rule-based
    fallback. Only whichever provider has an API key configured is used;
    this order is just a tie-break if more than one happens to be set.
    Gemini (Google AI Studio) is the only one of the three with a genuine
    no-billing-required free tier -- see .env.example.
    """
    if settings.ANTHROPIC_API_KEY:
        try:
            data = _extract_with_anthropic(document_type, pages)
            if data:
                return data, "llm"
        except Exception as exc:  # noqa: BLE001
            logger.error("Anthropic extraction failed, falling back to rule-based: %s", exc)
    elif settings.OPENAI_API_KEY:
        try:
            data = _extract_with_openai(document_type, pages)
            if data:
                return data, "llm"
        except Exception as exc:  # noqa: BLE001
            logger.error("OpenAI extraction failed, falling back to rule-based: %s", exc)
    elif settings.GOOGLE_API_KEY:
        try:
            data = _extract_with_gemini(document_type, pages)
            if data:
                return data, "llm"
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini extraction failed, falling back to rule-based: %s", exc)
    return _extract_rule_based(document_type, pages), "rule_based"


def _build_extraction_prompt(document_type: str, pages: list[PageText]) -> tuple[str, str]:
    """Returns (text, prompt) shared by both LLM providers."""
    text = _full_text_with_pages(pages)[:15000]
    required = REQUIRED_FIELDS.get(document_type, [])

    prompt = f"""You are a financial document extraction engine. The document type is
"{document_type}". Below is the OCR/parsed text, with page markers like [PAGE 1].

Extract EVERY meaningful field, header value and line item visible in the text
(not only the ones listed below). At minimum include these fields if present:
{required}

Rules:
- Return ONLY valid JSON, no prose, no markdown fences.
- Every field must be an object: {{"value": <value or null>, "page_number": <int or null>, "source_text": "<verbatim snippet or null>"}}
- If a value is not present in the text, set "value" to null. Never invent numbers.
- Include a "line_items" array (list of objects) for invoice tables or statement line items, each with
  whatever keys are visible (e.g. description, quantity, unit_price, amount OR label, values per period).
- Parenthesised numbers like (1,234) represent negative values.

TEXT:
{text}
"""
    return text, prompt


# --------------------------------------------------------------------- #
# LLM-based extraction -- Anthropic
# --------------------------------------------------------------------- #
def _extract_with_anthropic(document_type: str, pages: list[PageText]) -> dict | None:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    _, prompt = _build_extraction_prompt(document_type, pages)

    resp = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    raw = re.sub(r"^```json|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(raw)


# --------------------------------------------------------------------- #
# LLM-based extraction -- OpenAI
# --------------------------------------------------------------------- #
def _extract_with_openai(document_type: str, pages: list[PageText]) -> dict | None:
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    _, prompt = _build_extraction_prompt(document_type, pages)

    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_tokens=4000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You return only valid JSON, exactly as instructed by the user."},
            {"role": "user", "content": prompt},
        ],
    )
    raw = resp.choices[0].message.content or ""
    raw = re.sub(r"^```json|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(raw)


# --------------------------------------------------------------------- #
# LLM-based extraction -- Google Gemini (free tier via Google AI Studio)
# --------------------------------------------------------------------- #
def _extract_with_gemini(document_type: str, pages: list[PageText]) -> dict | None:
    import google.generativeai as genai

    genai.configure(api_key=settings.GOOGLE_API_KEY)
    _, prompt = _build_extraction_prompt(document_type, pages)

    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    resp = model.generate_content(
        prompt,
        generation_config={
            "response_mime_type": "application/json",
            "max_output_tokens": 4000,
        },
    )
    raw = (resp.text or "").strip()
    raw = re.sub(r"^```json|```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


# --------------------------------------------------------------------- #
# Deterministic rule-based fallback
# --------------------------------------------------------------------- #
def _field(value=None, page_number=None, source_text=None):
    return {"value": value, "page_number": page_number, "source_text": source_text}


def _find_line(pages: list[PageText], patterns: list[str]):
    for p in pages:
        for line in p.text.splitlines():
            low = line.lower()
            for pat in patterns:
                if pat in low:
                    return line.strip(), p.page_number
    return None, None


def _find_line_regex(pages: list[PageText], regexes: list[str]):
    """Like _find_line but matches whole-word regex patterns instead of
    plain substrings -- needed for short words like "change" that would
    otherwise false-match inside unrelated words (e.g. "exchange").
    """
    for p in pages:
        for line in p.text.splitlines():
            for rx in regexes:
                if re.search(rx, line, re.I):
                    return line.strip(), p.page_number
    return None, None


def _extract_rule_based(document_type: str, pages: list[PageText]) -> dict:
    if document_type == "invoice":
        return _extract_invoice(pages)
    return _extract_financial_statement(document_type, pages)


def _extract_invoice(pages: list[PageText]) -> dict:
    data = {}
    full_text = "\n".join(p.text for p in pages)

    line, pg = _find_line(pages, ["invoice no", "invoice #", "invoice number", "bill no"])
    m = re.search(r"([A-Za-z0-9\-\/]{4,})$", line) if line else None
    data["invoice_number"] = _field(m.group(1) if m else None, pg, line)

    # Separators restricted to /, -, . (no whitespace) so this can't span
    # across two unrelated numbers that happen to sit next to each other
    # on the same line (e.g. a receipt/bill number followed by a real date).
    date_match = re.search(
        r"\b(\d{1,2}[\/\-\.](?:\d{1,2}|[A-Za-z]{3,9})[\/\-\.]\d{2,4})\b", full_text
    )
    date_line_pg = None
    if date_match:
        for p in pages:
            if date_match.group(1) in p.text:
                date_line_pg = p.page_number
                break
    data["invoice_date"] = _field(date_match.group(1) if date_match else None, date_line_pg, date_match.group(0) if date_match else None)

    line, pg = _find_line(pages, ["customer", "bill to", "sold to"])
    data["customer_name"] = _field(line.split(":")[-1].strip() if line and ":" in line else (line if line else None), pg, line)

    vendor_line = _find_vendor_name_line(pages)
    data["vendor_name"] = _field(vendor_line, 1 if vendor_line else None, vendor_line)

    cur_match = re.search(r"\b(USD|INR|EUR|GBP|MYR|SGD|RM|Rs\.?|₹|\$|€|£)\b", full_text)
    data["currency"] = _field(cur_match.group(1) if cur_match else None,
                               None, cur_match.group(0) if cur_match else None)

    for key, patterns in [
        ("subtotal", ["subtotal", "sub total", "sub-total", "net amt", "net amount"]),
        ("tax_amount", ["gst amount", "tax amount", " gst ", " vat "]),
        ("discount", ["discount"]),
        ("total_amount", ["total amount", "grand total", "amount due", "total due",
                           "total inclusive", "total incl", "total:"]),
    ]:
        line, pg = _find_line(pages, patterns)
        nums = [n for n in (find_numbers(line) if line else []) if abs(n) < 10_000_000]
        # Only attach the source line when we actually pulled a number from
        # it -- a matched keyword line with no usable number (e.g. a table
        # header like "NetAmt GST Total" with no digits on it) is not a
        # meaningful source for a null value.
        data[key] = _field(nums[-1], pg, line) if nums else _field(None, None, None)

    # Receipt-style "GST Summary" tables (Code % NetAmt GST Total, followed
    # by a "Total  <net>  <gst>  <total>" row) are common on till receipts
    # and don't match the generic label patterns above. Use them to fill
    # subtotal/tax_amount/total_amount only where those are still missing --
    # never override a value already found from an explicit label.
    _fill_from_gst_summary_table(pages, data)

    data["line_items"] = _extract_invoice_line_items(pages)
    return data


def _find_vendor_name_line(pages: list[PageText]) -> str | None:
    """The vendor name is almost always the first line of the document, but
    OCR sometimes mangles the very first line (watermarks/logos behind the
    text, page-edge noise). Walk down a few lines and skip ones that don't
    look like a plausible name (too short, or mostly non-letters), instead
    of blindly trusting line 1.
    """
    if not pages or not pages[0].text.strip():
        return None
    for line in pages[0].text.splitlines()[:5]:
        candidate = line.strip()
        if len(candidate) < 3:
            continue
        letters = sum(1 for c in candidate if c.isalpha())
        if letters / max(len(candidate), 1) < 0.5:
            continue
        return candidate
    return None


_GST_SUMMARY_TOTAL_ROW_RE = re.compile(
    r"^~?\W*total\s+(?P<net>[\d,]+\.\d{2})\s+(?P<gst>[\d,]+(?:\.\d+)?)\s+(?P<total>[\d,]+\.\d{2})\s*$",
    re.I,
)


def _fill_from_gst_summary_table(pages: list[PageText], data: dict) -> None:
    for p in pages:
        for line in p.text.splitlines():
            m = _GST_SUMMARY_TOTAL_ROW_RE.match(line.strip())
            if not m:
                continue
            if data["subtotal"]["value"] is None:
                data["subtotal"] = _field(parse_number(m.group("net")), p.page_number, line.strip())
            # Only trust the GST/tax figure if it's actually decimal-formatted
            # in the source text. OCR sometimes drops the "." from amounts
            # (e.g. "1.64" -> "164") -- reinterpreting a bare integer as a
            # decimal would be guessing, not extracting, so we leave it null
            # rather than invent a value.
            if data["tax_amount"]["value"] is None and "." in m.group("gst"):
                data["tax_amount"] = _field(parse_number(m.group("gst")), p.page_number, line.strip())
            if data["total_amount"]["value"] is None:
                data["total_amount"] = _field(parse_number(m.group("total")), p.page_number, line.strip())
            return


def _extract_invoice_line_items(pages: list[PageText]) -> list[dict]:
    items = []
    row_re = re.compile(
        r"^(?P<desc>[A-Za-z][A-Za-z0-9 &\-\./]{2,40}?)\s+(?P<qty>\d+(?:\.\d+)?)\s+"
        r"(?P<price>[\d,]+\.\d{2})\s+(?P<amount>[\d,]+\.\d{2})\s*$"
    )
    for p in pages:
        for line in p.text.splitlines():
            m = row_re.match(line.strip())
            if m:
                items.append({
                    "description": m.group("desc").strip(),
                    "quantity": parse_number(m.group("qty")),
                    "unit_price": parse_number(m.group("price")),
                    "amount": parse_number(m.group("amount")),
                    "page_number": p.page_number,
                })
    return items


def _extract_financial_statement(document_type: str, pages: list[PageText]) -> dict:
    data = {}
    required = REQUIRED_FIELDS.get(document_type, [])
    for key in required:
        syns = _SYNONYMS.get(key, [key.replace("_", " ")])
        line, pg = _find_line(pages, syns)
        nums = find_numbers(line) if line else []
        # Indian/bank-style statements often prefix the amount with a small
        # schedule/footnote reference number (e.g. "Interest earned 13
        # 283,649.02 170,754.05"). Treat a lone small integer followed by
        # more numbers as that reference, not the value, and skip it.
        if len(nums) >= 2 and nums[0] == int(nums[0]) and abs(nums[0]) < 100:
            nums = nums[1:]
        data[key] = _field(nums[0] if nums else None, pg, line)

    # Fallback for statements (e.g. bank formats) that only print a bare
    # "Total" line under each section instead of "Total Assets" / "Total
    # Liabilities". Never fabricated -- taken verbatim from the document.
    if document_type == "balance_sheet" and data.get("total_assets", {}).get("value") is None:
        bare_totals = []
        for p in pages:
            for line in p.text.splitlines():
                stripped = line.strip()
                if re.match(r"^total\b", stripped, re.I) and find_numbers(stripped):
                    bare_totals.append((stripped, p.page_number))
        if bare_totals:
            last_line, last_pg = bare_totals[-1]
            nums = find_numbers(last_line)
            data["total_assets"] = _field(nums[0] if nums else None, last_pg, last_line)

    # currency + period headers (best effort)
    full_text = "\n".join(p.text for p in pages)
    cur_match = re.search(r"\b(USD|INR|EUR|GBP|Rs\.?|₹|\$|€|£|in\s+(?:Lakhs|Crores|Millions))\b", full_text, re.I)
    data["currency"] = _field(cur_match.group(1) if cur_match else None, None, cur_match.group(0) if cur_match else None)

    period_matches = re.findall(r"(?:as at|for the year ended|period ended)[^\n]{0,40}", full_text, re.I)
    data["reporting_periods"] = _field(period_matches[:4] if period_matches else None)

    data["line_items"] = _extract_statement_line_items(pages)
    return data


_LABEL_ROW_RE = re.compile(
    r"^(?P<label>[A-Za-z][A-Za-z0-9 &\-\./',()]{2,60}?)\s{1,}(?P<nums>(?:\(?-?[₹$€£]?[\d,]+(?:\.\d+)?\)?\s*){1,4})$"
)


def _extract_statement_line_items(pages: list[PageText]) -> list[dict]:
    items = []
    for p in pages:
        for line in p.text.splitlines():
            line = line.strip()
            if len(line) < 5:
                continue
            m = _LABEL_ROW_RE.match(line)
            if m:
                values = find_numbers(m.group("nums"))
                if values:
                    items.append({
                        "label": m.group("label").strip(),
                        "values": values,
                        "page_number": p.page_number,
                    })
    return items