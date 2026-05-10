const copyButtons = document.querySelectorAll("[data-copy]");

function writeClipboard(value) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(value);
  }

  const field = document.createElement("textarea");
  field.value = value;
  field.setAttribute("readonly", "");
  field.style.position = "fixed";
  field.style.top = "-999px";
  document.body.appendChild(field);
  field.select();

  try {
    const copied = document.execCommand("copy");
    return copied ? Promise.resolve() : Promise.reject(new Error("copy failed"));
  } finally {
    field.remove();
  }
}

function selectCommand(button) {
  const code = button.closest(".install-row")?.querySelector("code");

  if (!code) {
    return false;
  }

  const range = document.createRange();
  range.selectNodeContents(code);

  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);

  return true;
}

copyButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const value = button.getAttribute("data-copy") || "";
    const originalText = button.textContent;

    try {
      await writeClipboard(value);
      button.textContent = "Copied";
    } catch {
      button.textContent = selectCommand(button) ? "Selected" : "Copy failed";
    }

    window.setTimeout(() => {
      button.textContent = originalText;
    }, 1600);
  });
});
