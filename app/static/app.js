const fetchBtn = document.getElementById("fetch-btn");
const fetchStatus = document.getElementById("fetch-status");
const tbody = document.getElementById("tickets-tbody");

fetchBtn.addEventListener("click", async () => {
  fetchStatus.textContent = "Checking inbox...";
  try {
    const res = await fetch("/api/fetch", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      fetchStatus.textContent = "Error: " + (data.detail || "fetch failed");
      return;
    }
    fetchStatus.textContent = `Found ${data.new_tickets} new email(s). Reloading...`;
    setTimeout(() => window.location.reload(), 600);
  } catch (err) {
    fetchStatus.textContent = "Fetch failed: " + err;
  }
});

tbody.addEventListener("click", async (e) => {
  const row = e.target.closest("tr");
  if (!row) return;
  const id = row.dataset.id;

  if (e.target.classList.contains("save-btn")) {
    const draftCell = row.querySelector("[data-field='draft_reply']");
    await fetch(`/api/tickets/${id}/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft_reply: draftCell.textContent.trim() }),
    });
    flashRow(row, "Saved");
  }

  if (e.target.classList.contains("approve-btn")) {
    await fetch(`/api/tickets/${id}/approve`, { method: "POST" });
    row.querySelector(".status-cell").textContent = "approved";
    row.className = "status-approved";
  }

  if (e.target.classList.contains("reject-btn")) {
    await fetch(`/api/tickets/${id}/reject`, { method: "POST" });
    row.querySelector(".status-cell").textContent = "rejected";
    row.className = "status-rejected";
  }

  if (e.target.classList.contains("send-btn")) {
    flashRow(row, "Sending...");
    const res = await fetch(`/api/tickets/${id}/send`, { method: "POST" });
    const data = await res.json();
    row.querySelector(".status-cell").textContent = `${data.status}${data.message ? " — " + data.message : ""}`;
    row.className = `status-${data.status}`;
  }
});

function flashRow(row, message) {
  const cell = row.querySelector(".status-cell");
  const original = cell.textContent;
  cell.textContent = message;
  setTimeout(() => { if (cell.textContent === message) cell.textContent = original; }, 1500);
}
