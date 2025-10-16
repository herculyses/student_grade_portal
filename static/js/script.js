// ---------- Auto-hide flash messages ----------
document.addEventListener("DOMContentLoaded", () => {
  const alerts = document.querySelectorAll(".alert");
  alerts.forEach(a => {
    setTimeout(() => {
      a.style.transition = "opacity 0.5s";
      a.style.opacity = "0";
      setTimeout(() => a.remove(), 500);
    }, 2500);
  });
});

// ---------- Confirm delete ----------
document.addEventListener("click", function(e) {
  if (e.target.matches(".btn-danger")) {
    if (!confirm("Are you sure you want to delete the selected records?")) {
      e.preventDefault();
    }
  }
});
