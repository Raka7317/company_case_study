const API_BASE = "/api/v1";

async function loadDocuments() {
  const tbody = document.getElementById("doc-table-body");
  try {
    const res = await fetch(`${API_BASE}/documents`);
    const data = await res.json();
    if (!data.documents || data.documents.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5">No documents processed yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = data.documents.map(d => `
      <tr>
        <td>${d.document_name}</td>
        <td>${d.document_type}</td>
        <td><span class="badge ${d.processing_status}">${d.processing_status}</span></td>
        <td>${new Date(d.created_at).toLocaleString()}</td>
        <td><button type="button" class="view-btn" onclick="location.href='/documents/${encodeURIComponent(d.document_name)}/view'">View Details</button></td>
      </tr>
    `).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5">Failed to load documents: ${e}</td></tr>`;
  }
}

document.getElementById("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById("file");
  const docType = document.getElementById("document_type").value;
  const statusMsg = document.getElementById("status-msg");
  const btn = document.getElementById("submit-btn");

  if (!fileInput.files.length) return;

  const form = new FormData();
  form.append("file", fileInput.files[0]);
  form.append("document_type", docType);

  btn.disabled = true;
  statusMsg.textContent = "Processing... this may take a few seconds.";

  try {
    const res = await fetch(`${API_BASE}/documents/process`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) {
      statusMsg.textContent = `Error: ${data?.error?.message || "Processing failed."}`;
    } else {
      statusMsg.textContent = `Done. Status: ${data.processing_status}`;
      fileInput.value = "";
      loadDocuments();
    }
  } catch (err) {
    statusMsg.textContent = `Request failed: ${err}`;
  } finally {
    btn.disabled = false;
  }
});

loadDocuments();