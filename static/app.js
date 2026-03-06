const form = document.getElementById("download-form");
const searchForm = document.getElementById("search-form");
const searchQueryInput = document.getElementById("search-query");
const searchBtn = document.getElementById("search-btn");
const searchStatusEl = document.getElementById("search-status");
const searchResultsEl = document.getElementById("search-results");
const urlInput = document.getElementById("url");
const mediaTypeInput = document.getElementById("media-type");
const qualityInput = document.getElementById("quality");
const statusEl = document.getElementById("status");
const submitBtn = document.getElementById("submit-btn");
const resultEl = document.getElementById("result");

const rTitle = document.getElementById("r-title");
const rExtractor = document.getElementById("r-extractor");
const rDuration = document.getElementById("r-duration");
const rFilename = document.getElementById("r-filename");
const rThumb = document.getElementById("r-thumb");
const resultCoverWrap = document.getElementById("result-cover-wrap");
const fileLink = document.getElementById("file-link");
const docsEl = document.getElementById("docs");
const exampleLanguageInput = document.getElementById("example-language");
const exampleKindInput = document.getElementById("example-kind");
const exampleCodeEl = document.getElementById("example-code");
const copyExampleBtn = document.getElementById("copy-example-btn");
const copyStatusEl = document.getElementById("copy-status");
const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
const tabTriggers = Array.from(document.querySelectorAll("[data-tab-target]"));
const tabPanels = {
  url: document.getElementById("tab-url"),
  search: document.getElementById("tab-search"),
  docs: document.getElementById("tab-docs"),
};

const videoQualityOptions = [
  { value: "best", label: "Melhor disponivel" },
  { value: "1080", label: "1080p" },
  { value: "720", label: "720p" },
  { value: "480", label: "480p" },
  { value: "360", label: "360p" },
];

const audioQualityOptions = [
  { value: "320", label: "320 kbps" },
  { value: "192", label: "192 kbps" },
  { value: "128", label: "128 kbps" },
];

function fillQualityOptions() {
  const mediaType = mediaTypeInput.value === "audio" ? "audio" : "video";
  const list = mediaType === "audio" ? audioQualityOptions : videoQualityOptions;
  qualityInput.innerHTML = "";
  list.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    qualityInput.appendChild(option);
  });
}

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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderSearchResults(items) {
  if (!searchResultsEl) return;
  if (!items.length) {
    searchResultsEl.innerHTML = "<p class='status'>Nenhum resultado encontrado.</p>";
    searchResultsEl.classList.remove("hidden");
    return;
  }

  searchResultsEl.innerHTML = items.map((item) => {
    const duration = formatDuration(item.duration);
    const thumb = item.thumbnail
      ? `<img src="${escapeHtml(item.thumbnail)}" alt="thumb">`
      : "<div class='thumb-fallback'>Sem capa</div>";
    return `<article class="search-item">
      <div class="search-thumb">${thumb}</div>
      <div class="search-meta">
        <h4>${escapeHtml(item.title || "Sem titulo")}</h4>
        <p>${escapeHtml(item.channel || "Canal desconhecido")} - ${escapeHtml(duration)}</p>
        <div class="search-actions">
          <a href="${escapeHtml(item.webpage_url)}" target="_blank" rel="noopener">Abrir no YouTube</a>
          <button type="button" class="use-result-btn" data-url="${escapeHtml(item.webpage_url)}">Usar este link</button>
        </div>
      </div>
    </article>`;
  }).join("");
  searchResultsEl.classList.remove("hidden");
}

function getExampleCode() {
  if (!docsEl || !exampleLanguageInput || !exampleKindInput) return "";
  const baseUrl = (docsEl.dataset.apiBase || "").replace(/\/+$/, "");
  const language = exampleLanguageInput.value;
  const kind = exampleKindInput.value === "audio" ? "audio" : "video";
  const quality = kind === "audio" ? "320" : "720";
  const endpoint = `${baseUrl}/download/${kind}`;
  const sampleUrl = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";

  if (language === "python") {
    return `import requests

base_url = "${baseUrl}"
endpoint = "${endpoint}"
payload = {
    "url": "${sampleUrl}",
    "quality": "${quality}"
}

resp = requests.post(endpoint, json=payload, timeout=120)
resp.raise_for_status()
data = resp.json()
print(data)
# download do ficheiro:
# file_resp = requests.get(f"{base_url}/files/{data['filename']}", timeout=120)
# open(data["filename"], "wb").write(file_resp.content)`;
  }

  if (language === "javascript") {
    return `const endpoint = "${endpoint}";
const payload = {
  url: "${sampleUrl}",
  quality: "${quality}"
};

const response = await fetch(endpoint, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload)
});

if (!response.ok) throw new Error("Falha no download");
const data = await response.json();
console.log(data);
// download do ficheiro:
// window.open("${baseUrl}/files/" + encodeURIComponent(data.filename), "_blank");`;
  }

  return `curl -X POST "${endpoint}" \\
  -H "Content-Type: application/json" \\
  -d '{"url":"${sampleUrl}","quality":"${quality}"}'`;
}

function renderExampleCode() {
  if (!exampleCodeEl) return;
  exampleCodeEl.textContent = getExampleCode();
}

async function readApiResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  const text = await response.text();
  return { detail: text || "Resposta invalida da API." };
}

function activateTab(tabName) {
  tabButtons.forEach((btn) => {
    const active = btn.dataset.tabTarget === tabName;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });
  Object.entries(tabPanels).forEach(([name, panel]) => {
    if (!panel) return;
    panel.classList.toggle("is-active", name === tabName);
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const url = urlInput.value.trim();
  const mediaType = mediaTypeInput.value === "audio" ? "audio" : "video";
  const quality = qualityInput.value;
  if (!url) {
    statusEl.textContent = "Informe uma URL valida.";
    return;
  }

  submitBtn.disabled = true;
  resultEl.classList.add("hidden");
  statusEl.textContent = mediaType === "audio"
    ? "Baixando audio... isso pode levar alguns segundos."
    : "Baixando video... isso pode levar alguns segundos.";

  try {
    const response = await fetch(`/download/${mediaType}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, quality }),
    });

    const data = await readApiResponse(response);
    if (!response.ok) {
      throw new Error(data.detail || "Falha no download.");
    }

    rTitle.textContent = data.title || "Sem titulo";
    rExtractor.textContent = data.extractor || "-";
    rDuration.textContent = formatDuration(data.duration);
    rFilename.textContent = data.filename;
    if (data.thumbnail && rThumb && resultCoverWrap) {
      rThumb.src = data.thumbnail;
      resultCoverWrap.classList.remove("hidden");
    } else if (rThumb && resultCoverWrap) {
      rThumb.removeAttribute("src");
      resultCoverWrap.classList.add("hidden");
    }
    fileLink.href = `/files/${encodeURIComponent(data.filename)}`;

    resultEl.classList.remove("hidden");
    statusEl.textContent = "Download concluido com sucesso.";
  } catch (error) {
    statusEl.textContent = `Erro: ${error.message}`;
  } finally {
    submitBtn.disabled = false;
  }
});

if (searchForm && searchQueryInput && searchBtn && searchStatusEl && searchResultsEl) {
  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const q = searchQueryInput.value.trim();
    if (q.length < 2) {
      searchStatusEl.textContent = "Digite pelo menos 2 caracteres.";
      return;
    }
    searchBtn.disabled = true;
    searchStatusEl.textContent = "Pesquisando no YouTube...";
    searchResultsEl.classList.add("hidden");
    searchResultsEl.innerHTML = "";
    try {
      const response = await fetch(`/search/youtube?q=${encodeURIComponent(q)}&limit=10`);
      const data = await readApiResponse(response);
      if (!response.ok) {
        throw new Error(data.detail || "Falha na pesquisa.");
      }
      renderSearchResults(data.items || []);
      searchStatusEl.textContent = `${data.count || 0} resultado(s) encontrado(s).`;
    } catch (error) {
      searchStatusEl.textContent = `Erro na pesquisa: ${error.message}`;
    } finally {
      searchBtn.disabled = false;
    }
  });

  searchResultsEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (!target.classList.contains("use-result-btn")) return;
    const chosenUrl = target.dataset.url || "";
    if (!chosenUrl) return;
    urlInput.value = chosenUrl;
    activateTab("url");
    statusEl.textContent = "Link selecionado da pesquisa. Agora escolha tipo/qualidade e clique em Baixar.";
    urlInput.scrollIntoView({ behavior: "smooth", block: "center" });
  });
}

mediaTypeInput.addEventListener("change", fillQualityOptions);
fillQualityOptions();

if (exampleLanguageInput && exampleKindInput) {
  exampleLanguageInput.addEventListener("change", renderExampleCode);
  exampleKindInput.addEventListener("change", renderExampleCode);
  renderExampleCode();
}

if (copyExampleBtn && exampleCodeEl && copyStatusEl) {
  copyExampleBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(exampleCodeEl.textContent || "");
      copyStatusEl.textContent = "Exemplo copiado.";
    } catch {
      copyStatusEl.textContent = "Nao foi possivel copiar automaticamente.";
    }
  });
}

if (tabButtons.length) {
  tabTriggers.forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.tabTarget || "url"));
  });
  activateTab("url");
}

