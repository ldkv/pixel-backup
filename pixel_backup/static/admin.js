function formatBytes(bytes) {
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024)
        return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
}

function formatDate(iso) {
    return new Date(iso).toLocaleString();
}

// Cutoffs are always shown and entered in UTC, not the browser's or cron's timezone.
function formatCutoff(iso) {
    return (
        new Date(iso).toLocaleString(undefined, { timeZone: "UTC" }) + " UTC"
    );
}

function fromCutoffInputValue(value) {
    return value ? new Date(value + "Z").toISOString() : null;
}

function renderUserConfigRow(uc) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
    <td>${uc.username}</td>
    <td>${uc.source_dir}</td>
    <td>${uc.sync_order}</td>
    <td>${formatCutoff(uc.sync_cutoff_at)}</td>
    <td>
      <div class="row-actions">
        <button class="secondary" data-action="edit">Edit</button>
        <button class="danger" data-action="remove">Remove</button>
      </div>
    </td>
  `;
    tr.querySelector('[data-action="edit"]').addEventListener("click", () =>
        renderUserConfigEditRow(tr, uc),
    );
    tr.querySelector('[data-action="remove"]').addEventListener("click", () =>
        deleteUserConfig(uc.id),
    );
    return tr;
}

function renderUserConfigEditRow(tr, uc) {
    tr.innerHTML = `
    <td><input class="inline-input" data-field="username" value="${uc.username}"></td>
    <td><input class="inline-input" data-field="source_dir" value="${uc.source_dir}"></td>
    <td><input class="inline-input" data-field="sync_order" type="number" value="${uc.sync_order}"></td>
    <td>${formatCutoff(uc.sync_cutoff_at)}</td>
    <td>
      <div class="row-actions">
        <button data-action="save">Save</button>
        <button class="secondary" data-action="cancel">Cancel</button>
      </div>
    </td>
  `;
    tr.querySelector('[data-action="cancel"]').addEventListener("click", () => {
        tr.replaceWith(renderUserConfigRow(uc));
    });
    tr.querySelector('[data-action="save"]').addEventListener(
        "click",
        async () => {
            const body = {
                username: tr.querySelector('[data-field="username"]').value,
                source_dir: tr.querySelector('[data-field="source_dir"]').value,
                sync_order: parseInt(
                    tr.querySelector('[data-field="sync_order"]').value,
                    10,
                ),
            };
            const res = await fetch(`/user_configs/${uc.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (res.ok) {
                loadUserConfigs();
                loadBatches();
            } else {
                const err = await res.json().catch(() => ({}));
                alert(err.detail || "Failed to update user config.");
            }
        },
    );
}

async function loadUserConfigs() {
    const res = await fetch("/user_configs");
    const configs = await res.json();
    const body = document.getElementById("user-configs-body");
    body.innerHTML = "";
    if (configs.length === 0) {
        body.innerHTML =
            '<tr class="empty-row"><td colspan="5">No user configs yet.</td></tr>';
    } else {
        for (const uc of configs) {
            body.appendChild(renderUserConfigRow(uc));
        }
    }
    updateBatchesUserFilter(configs);
}

function updateBatchesUserFilter(configs) {
    const select = document.getElementById("batches-user-filter");
    const current = select.value;
    select.innerHTML = '<option value="">All users</option>';
    for (const uc of configs) {
        const option = document.createElement("option");
        option.value = uc.username;
        option.textContent = uc.username;
        select.appendChild(option);
    }
    if (configs.some((uc) => uc.username === current)) {
        select.value = current;
    }
}

async function loadBatches() {
    const username = document.getElementById("batches-user-filter").value;
    const url = username
        ? `/batches?username=${encodeURIComponent(username)}`
        : "/batches";
    const res = await fetch(url);
    const batches = await res.json();
    const body = document.getElementById("batches-body");
    body.innerHTML = "";
    if (batches.length === 0) {
        body.innerHTML =
            '<tr class="empty-row"><td colspan="6">No batches yet.</td></tr>';
        return;
    }
    for (const b of batches) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
      <td>${b.username}</td>
      <td>${b.files_count}</td>
      <td>${formatBytes(b.total_bytes)}</td>
      <td>${formatDate(b.synced_at)}</td>
      <td>${b.resynced_at ? formatDate(b.resynced_at) : ""}</td>
      <td>
        <div class="row-actions">
          <button class="secondary" data-action="resync">Resync</button>
        </div>
      </td>
    `;
        tr.querySelector('[data-action="resync"]').addEventListener(
            "click",
            () => resyncBatch(b.id),
        );
        body.appendChild(tr);
    }
}

async function resyncBatch(id) {
    const statusEl = document.getElementById("sync-status");
    const dryRun = document.getElementById("dry-run-checkbox").checked;
    if (!dryRun && !confirm("Relink the missing files of this batch?")) return;
    statusEl.textContent = "Starting...";
    statusEl.className = "status-msg";
    const res = await fetch(`/batches/${id}/resync?dry_run=${dryRun}`, {
        method: "POST",
    });
    if (res.ok) {
        statusEl.textContent = "Resync started.";
        statusEl.className = "status-msg success";
    } else {
        const err = await res.json().catch(() => ({}));
        statusEl.textContent = err.detail || "Failed to start resync.";
        statusEl.className = "status-msg error";
    }
}

async function deleteUserConfig(id) {
    if (!confirm("Remove this user config?")) return;
    const res = await fetch(`/user_configs/${id}`, { method: "DELETE" });
    if (res.ok) {
        loadUserConfigs();
        loadBatches();
    } else {
        alert("Failed to remove user config.");
    }
}

function errorDetail(err, fallback) {
    if (Array.isArray(err.detail))
        return err.detail.map((d) => d.msg).join("; ");
    return err.detail || fallback;
}

const globalConfigInputs = document.querySelectorAll(
    "#global-config-form [data-field]",
);

async function loadGlobalConfig() {
    const res = await fetch("/global_config");
    const config = await res.json();
    for (const input of globalConfigInputs) {
        input.value = config[input.dataset.field] ?? "";
    }
}

document
    .getElementById("global-config-form")
    .addEventListener("submit", async (e) => {
        e.preventDefault();
        const statusEl = document.getElementById("global-config-status");
        statusEl.textContent = "";
        statusEl.className = "status-msg";
        const body = {};
        for (const input of globalConfigInputs) {
            body[input.dataset.field] =
                input.type === "number" ? Number(input.value) : input.value;
        }
        const res = await fetch("/global_config", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (res.ok) {
            statusEl.textContent = "Saved.";
            statusEl.className = "status-msg success";
            loadGlobalConfig();
        } else {
            const err = await res.json().catch(() => ({}));
            statusEl.textContent = errorDetail(
                err,
                "Failed to save global config.",
            );
            statusEl.className = "status-msg error";
        }
    });

document
    .getElementById("batches-user-filter")
    .addEventListener("change", loadBatches);

document
    .getElementById("add-user-config-form")
    .addEventListener("submit", async (e) => {
        e.preventDefault();
        const statusEl = document.getElementById("add-user-config-status");
        statusEl.textContent = "";
        statusEl.className = "status-msg";
        const body = {
            username: document.getElementById("uc-username").value,
            source_dir: document.getElementById("uc-source-dir").value,
            sync_order: parseInt(
                document.getElementById("uc-sync-order").value,
                10,
            ),
            sync_cutoff_at: fromCutoffInputValue(
                document.getElementById("uc-cutoff-at").value,
            ),
        };
        const res = await fetch("/user_configs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (res.ok) {
            e.target.reset();
            statusEl.textContent = "Added.";
            statusEl.className = "status-msg success";
            loadUserConfigs();
        } else {
            const err = await res.json().catch(() => ({}));
            statusEl.textContent = err.detail || "Failed to add user config.";
            statusEl.className = "status-msg error";
        }
    });

document.getElementById("sync-btn").addEventListener("click", async () => {
    const btn = document.getElementById("sync-btn");
    const statusEl = document.getElementById("sync-status");
    const dryRun = document.getElementById("dry-run-checkbox").checked;
    btn.disabled = true;
    statusEl.textContent = "Starting...";
    statusEl.className = "status-msg";
    try {
        const res = await fetch(`/sync?dry_run=${dryRun}`, { method: "POST" });
        if (res.ok) {
            statusEl.textContent = "Sync started.";
            statusEl.className = "status-msg success";
        } else {
            const err = await res.json().catch(() => ({}));
            statusEl.textContent = err.detail || "Failed to start sync.";
            statusEl.className = "status-msg error";
        }
    } finally {
        btn.disabled = false;
    }
});

loadGlobalConfig();
loadUserConfigs();
loadBatches();
