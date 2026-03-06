const form = document.getElementById("download-form");
const urlInput = document.getElementById("url");
const statusEl = document.getElementById("status");
const submitBtn = document.getElementById("submit-btn");
const resultEl = document.getElementById("result");

const rTitle = document.getElementById("r-title");
const rExtractor = document.getElementById("r-extractor");
const rDuration = document.getElementById("r-duration");
const rFilename = document.getElementById("r-filename");
const fileLink = document.getElementById("file-link");

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return "-";
  const value = Math.floor(Number(seconds));
  const h = Math.floor(value / 3600);
  const m = Math.floor((value % 3600) / 60);
  const s = value % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const url = urlInput.value.trim();
  if (!url) {
    statusEl.textContent = "Informe uma URL valida.";
    return;
  }

  submitBtn.disabled = true;
  resultEl.classList.add("hidden");
  statusEl.textContent = "Baixando video... isso pode levar alguns segundos.";

  try {
    const response = await fetch("/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Falha no download.");
    }

    rTitle.textContent = data.title || "Sem titulo";
    rExtractor.textContent = data.extractor || "-";
    rDuration.textContent = formatDuration(data.duration);
    rFilename.textContent = data.filename;
    fileLink.href = `/files/${encodeURIComponent(data.filename)}`;

    resultEl.classList.remove("hidden");
    statusEl.textContent = "Download concluido com sucesso.";
  } catch (error) {
    statusEl.textContent = `Erro: ${error.message}`;
  } finally {
    submitBtn.disabled = false;
  }
});
