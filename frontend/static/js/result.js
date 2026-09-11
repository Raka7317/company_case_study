const API_BASE = "/api/v1";

function fieldCell(key, field) {
  const value = field && typeof field === "object" ? field.value : field;
  const missing = value === null || value === undefined;
  return `<div class="item ${missing ? "missing" : ""}">
    <div class="label">${key}</div>
    <div class="value">${missing ? "— missing —" : value}</div>
  </div>`;
}

function renderChecks(checks) {
  if (!checks || checks.length === 0) return "<p>No validation checks were applicable.</p>";
  return `<table><thead><tr>
    <th>Check</th><th>Formula</th><th>Calculated</th><th>Reported</th><th>Variance</th><th>Status</th>
  </tr></thead><tbody>${checks.map(c => `
    <tr>
      <td>${c.name}</td>
      <td>${c.formula}</td>
      <td>${c.calculated_value ?? "—"}</td>
      <td>${c.reported_value ?? "—"}</td>
      <td>${c.variance ?? "—"}</td>
      <td><span class="badge ${c.status}">${c.status}</span></td>
    </tr>`).join("")}</tbody></table>`;
}

function renderLineItems(items) {
  if (!items || items.length === 0) return "<p>No line items extracted.</p>";
  const cols = [...new Set(items.flatMap(i => Object.keys(i)))].filter(c => c !== "page_number");
  return `<table><thead><tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead>
    <tbody>${items.map(it => `<tr>${cols.map(c => `<td>${
      Array.isArray(it[c]) ? it[c].join(", ") : (it[c] ?? "—")
    }</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function showTab(name) {
  document.querySelectorAll(".tab-panel").forEach(p => p.style.display = "none");
  document.getElementById(`tab-${name}`).style.display = "block";
  document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
  document.getElementById(`btn-${name}`).classList.add("active");
}

async function load() {
  const content = document.getElementById("content");
  try {
    const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(documentName)}`);
    if (!res.ok) {
      content.innerHTML = `<div class="card">Document not found.</div>`;
      return;
    }
    const doc = await res.json();
    const extracted = doc.extracted_data || {};
    const lineItems = extracted.line_items || [];
    const fieldEntries = Object.entries(extracted).filter(([k]) => k !== "line_items");

    content.innerHTML = `
      <div class="card">
        <h2>${doc.document_name} <span class="badge ${doc.processing_status}">${doc.processing_status}</span></h2>
        <p>Type: <b>${doc.document_type}</b> &nbsp;|&nbsp; OCR used: <b>${doc.processing_metadata?.ocr_used}</b>
           &nbsp;|&nbsp; Processed at: ${doc.processing_metadata?.processed_at || "—"}</p>
        <div class="tabs">
          <button class="tab active" id="btn-fields" onclick="showTab('fields')">Extracted Fields</button>
          <button class="tab" id="btn-items" onclick="showTab('items')">Line Items</button>
          <button class="tab" id="btn-validation" onclick="showTab('validation')">Validation</button>
          <button class="tab" id="btn-json" onclick="showTab('json')">Raw JSON</button>
        </div>
        <div class="tab-panel" id="tab-fields">
          <div class="kv-grid">${fieldEntries.map(([k, v]) => fieldCell(k, v)).join("")}</div>
        </div>
        <div class="tab-panel" id="tab-items" style="display:none">${renderLineItems(lineItems)}</div>
        <div class="tab-panel" id="tab-validation" style="display:none">
          <p>Overall: <span class="badge ${doc.validation?.overall_status}">${doc.validation?.overall_status}</span></p>
          ${renderChecks(doc.validation?.checks)}
        </div>
        <div class="tab-panel" id="tab-json" style="display:none">
          <pre class="json-view">${JSON.stringify(doc, null, 2)}</pre>
        </div>
      </div>
    `;
  } catch (e) {
    content.innerHTML = `<div class="card">Failed to load document: ${e}</div>`;
  }
}

load();
