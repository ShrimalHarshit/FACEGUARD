/* manage_users.js — user management interactions */

// ── Role change dropdowns ──────────────────────────────────────────────────
document.querySelectorAll(".role-select").forEach(sel => {
  const original = sel.value;

  sel.addEventListener("change", async () => {
    const userId  = sel.dataset.userId;
    const newRole = sel.value;

    const confirmed = confirm(
      `Change this user's role to "${newRole}"?`
    );

    if (!confirmed) {
      sel.value = original;
      return;
    }

    try {
      const data = await apiPatch(`/api/users/${userId}/role`, { role: newRole });

      if (data.success) {
        showToast(`Role updated to ${newRole}`, "success");
        // Re-color the row visually
        const row = sel.closest("tr");
        if (row) {
          row.style.transition = "background 0.4s";
          row.style.background = "var(--bg3)";
          setTimeout(() => { row.style.background = ""; }, 1000);
        }
      } else {
        showToast(data.error || "Failed to update role", "error");
        sel.value = original;
      }
    } catch {
      showToast("Network error. Please try again.", "error");
      sel.value = original;
    }
  });
});

// ── Delete user ────────────────────────────────────────────────────────────
async function deleteUser(userId, name) {
  const confirmed = confirm(
    `Delete user "${name}"?\n\nThis will also remove their face data. This cannot be undone.`
  );
  if (!confirmed) return;

  try {
    const data = await apiDelete(`/api/users/${userId}`);

    if (data.success) {
      showToast(`User "${name}" deleted.`, "success");
      // Animate row out
      const row = document.querySelector(`tr[data-id="${userId}"]`);
      if (row) {
        row.style.transition = "opacity 0.4s, transform 0.4s";
        row.style.opacity = "0";
        row.style.transform = "translateX(20px)";
        setTimeout(() => row.remove(), 420);
      }
    } else {
      showToast(data.error || "Delete failed.", "error");
    }
  } catch {
    showToast("Network error.", "error");
  }
}

// expose to inline onclick
window.deleteUser = deleteUser;
