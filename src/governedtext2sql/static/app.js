"use strict";
const MODES = {
  baseline: {
    name: "LLM → SQL",
    color: "blue",
    subtitle: "Physical schema · direct generation",
  },
  semantic: {
    name: "LLM + Semantic RAG",
    color: "amber",
    subtitle: "Business catalog · lexical retrieval",
  },
  vkg: {
    name: "VKG + Ontop",
    color: "green",
    subtitle: "Ontology · SPARQL · SQL unfolding",
  },
};
const $ = (selector) => document.querySelector(selector);
const state = {
  key: "",
  session: null,
  busy: false,
  results: {},
  question: "",
  startedAt: null,
};
const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 6 });
const ms = (value) => `${number.format(Math.round(value * 100) / 100)} ms`;
function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}
function notice(message, info = false) {
  $("#notice").textContent = message;
  $("#notice").className = `notice${info ? " info" : ""}`;
  $("#notice").hidden = !message;
}
function selected() {
  return [...document.querySelectorAll("input[name=mode]:checked")].map(
    (input) => input.value,
  );
}
function updateSelection() {
  const count = selected().length;
  $("#mode-count").textContent = count;
  $("#run-label").textContent = count === 1 ? "Run approach" : "Run comparison";
  $("#run-button").disabled = state.busy || !state.session || count === 0;
  $("#select-all").textContent = count === 3 ? "Deselect all" : "Select all";
}
function resetConnection() {
  state.key = "";
  state.session = null;
  $("#environment").textContent = "Not connected";
  $("#environment").className = "environment";
  $("#connection-title").textContent = "Connect your workspace";
  $("#connection-description").textContent =
    "Use your API key to run queries with your assigned tenant and role.";
  $("#connect-button").textContent = "Connect ↗";
  updateSelection();
}
async function api(path, options = {}, key = state.key) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", "X-API-Key": key },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const messages = {
      401: "Authentication failed. Reconnect with a valid API key.",
      422: "This question is unsupported or was denied by policy. Try one of the three examples.",
      503: "The model, database or Ontop is unavailable. Check the service configuration and try again.",
    };
    const error = new Error(
      messages[response.status] || `Request failed (HTTP ${response.status}).`,
    );
    error.status = response.status;
    throw error;
  }
  return data;
}
$("#connection-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const key = $("#api-key").value.trim();
  if (!key) return;
  const button = $("#connect-button");
  button.disabled = true;
  button.textContent = "Connecting…";
  notice("");
  // Clear any previous identity before checking new credentials.
  resetConnection();
  state.results = {};
  state.question = "";
  renderEmpty();
  button.textContent = "Connecting…";
  try {
    const session = await api("/v1/session", {}, key);
    state.key = key;
    state.session = session;
    state.results = {};
    state.question = "";
    renderEmpty();
    $("#api-key").value = "";
    $("#api-key").placeholder = "Key held in memory only";
    $("#environment").textContent =
      session.planner === "fixture" ? "Demo planner" : "Live LLM";
    $("#environment").className = "environment connected";
    $("#connection-title").textContent =
      `${session.subject} · ${session.tenant} tenant`;
    $("#connection-description").textContent =
      `${session.role} · ${session.model || "Deterministic fixture"} · API key stays in this tab’s memory`;
    button.textContent = "Reconnect ↗";
    if (session.planner === "fixture")
      notice(
        "Demo planner active. The baseline deliberately counts contacts; semantic and VKG paths use customer-level definitions. No live LLM is being called.",
        true,
      );
    else
      notice(
        "Live model active. Requests use your configured server-side model. Latency and result agreement reflect this run only.",
        true,
      );
  } catch (error) {
    resetConnection();
    notice(
      error.message || "Could not connect. Check that the API is running.",
    );
  } finally {
    button.disabled = false;
    updateSelection();
  }
});
function card(mode, status = "idle") {
  const metadata = MODES[mode];
  const node = element("article", `result-card ${metadata.color}`);
  node.id = `result-${mode}`;
  const head = element("div", "result-head");
  head.append(element("span", "", metadata.name));
  const labels = {
    idle: "AWAITING QUERY",
    running: "RUNNING",
    success: "EXECUTED",
    error: "NOT EXECUTED",
  };
  head.append(element("span", `badge ${status}`, labels[status]));
  const body = element("div", "result-body");
  node.append(head, body);
  return { node, body };
}
function renderEmpty() {
  $("#results").replaceChildren();
  for (const mode of Object.keys(MODES)) {
    const { node, body } = card(mode);
    body.append(
      element(
        "div",
        "empty-symbol",
        mode === "vkg" ? "⌬" : mode === "semantic" ? "▤" : "⌘",
      ),
      element("p", "empty-text", "A little context changes everything."),
    );
    $("#results").append(node);
  }
  $("#comparison-summary").hidden = true;
  $("#latency-panel").hidden = true;
  $("#export-button").disabled = true;
  $("#run-caption").textContent =
    "Run a question to inspect results, generated queries and the work behind each approach.";
}
function renderLoading(mode) {
  const { node, body } = card(mode, "running");
  const loading = element("div", "loading");
  loading.append(
    element("span", "spinner"),
    element("span", "", "Planning and executing…"),
  );
  body.append(loading);
  $("#results").append(node);
}
function renderResult(mode, result) {
  const { node, body } = card(mode, result.ok ? "success" : "error");
  if (!result.ok) {
    body.append(
      element("div", "error-message", result.error),
      element(
        "p",
        "query-note",
        "No result is shown for this approach. Other approaches complete independently.",
      ),
    );
  } else {
    const data = result.data;
    const value =
      data.metric === "conversion_rate" ||
      /conversion rate/i.test(state.question)
        ? `${number.format(data.value * 100)}%`
        : number.format(data.value);
    body.append(
      element("div", "result-value", value),
      element(
        "div",
        "value-caption",
        data.metric ? data.metric.replaceAll("_", " ") : "Direct SQL aggregate",
      ),
    );
    const metadata = element("div", "result-meta");
    const duration = element("span", "", "Total time ");
    duration.append(element("strong", "", ms(data.latency_ms)));
    metadata.append(duration, element("span", "", "Read-only execution"));
    body.append(metadata);
    const tabs = element("div", "tabs");
    tabs.setAttribute("role", "tablist");
    tabs.setAttribute("aria-label", `${MODES[mode].name} details`);
    const content = element("div");
    content.id = `panel-${mode}`;
    content.setAttribute("role", "tabpanel");
    const labels = ["Query", "Pipeline", "Context"];
    labels.forEach((label, index) => {
      const tab = element("button", "tab", label);
      tab.id = `tab-${mode}-${index}`;
      tab.type = "button";
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-controls", content.id);
      tab.setAttribute("aria-selected", String(index === 0));
      tab.tabIndex = index === 0 ? 0 : -1;
      tab.addEventListener("click", () => {
        [...tabs.children].forEach((button) => {
          button.setAttribute("aria-selected", String(button === tab));
          button.tabIndex = button === tab ? 0 : -1;
        });
        content.setAttribute("aria-labelledby", tab.id);
        renderDetail(content, mode, data, label);
      });
      tab.addEventListener("keydown", (event) => {
        let next;
        if (event.key === "ArrowRight") next = (index + 1) % labels.length;
        if (event.key === "ArrowLeft")
          next = (index + labels.length - 1) % labels.length;
        if (event.key === "Home") next = 0;
        if (event.key === "End") next = labels.length - 1;
        if (next !== undefined) {
          event.preventDefault();
          tabs.children[next].focus();
          tabs.children[next].click();
        }
      });
      tabs.append(tab);
    });
    content.setAttribute("aria-labelledby", `tab-${mode}-0`);
    renderDetail(content, mode, data, "Query");
    body.append(tabs, content);
    body.append(
      element(
        "p",
        "query-note",
        `Request ${data.request_id.slice(0, 8)} · ${data.planner === "fixture" ? "Demo fixture" : "Live LLM"}`,
      ),
    );
  }
  $(`#result-${mode}`).replaceWith(node);
}
function renderDetail(container, mode, data, tab) {
  container.replaceChildren();
  if (tab === "Query") {
    const label = element(
      "div",
      "code-label",
      `${data.language.toUpperCase()} · GENERATED QUERY`,
    );
    const copy = element("button", "copy-button", "Copy ↗");
    copy.type = "button";
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(data.query);
        copy.textContent = "Copied ✓";
      } catch {
        copy.textContent = "Select text to copy";
      }
    });
    label.append(copy);
    const pre = element("pre", "query-code");
    pre.append(element("code", "", data.query));
    container.append(label, pre);
    container.append(
      element(
        "p",
        "query-note",
        mode === "vkg"
          ? "This SPARQL is sent to Ontop. Ontop generates and executes SQL internally; its actual unfolded SQL is not returned by this API."
          : "This SQL is executed against PostgreSQL. Tenant isolation is enforced by row-level security.",
      ),
    );
  } else if (tab === "Pipeline") {
    const list = element("ol", "pipeline");
    for (const stage of data.stages || []) {
      const item = element("li");
      item.append(
        element("span", "stage-time", ms(stage.latency_ms)),
        element("strong", "", stage.name),
        element("small", "", stage.detail),
      );
      list.append(item);
    }
    container.append(list, element("p", "query-note", data.governance));
  } else if (data.retrieved_context?.length) {
    for (const doc of data.retrieved_context) {
      const chunk = element("div", "context-chunk");
      chunk.append(
        element("strong", "", doc.title),
        element("p", "", doc.text),
        element("small", "", `Catalog: ${doc.id} · lexical score ${doc.score}`),
      );
      container.append(chunk);
    }
  } else if (mode === "vkg") {
    const chunk = element("div", "context-chunk");
    chunk.append(
      element("strong", "", "OWL + R2RML grounding"),
      element(
        "p",
        "",
        "EligibleCustomer ⊆ MarketableCustomer ⊆ Customer. SQL-backed mappings ground age ≥ 18, active status and consent; Ontop infers the superclass used by the query.",
      ),
      element(
        "small",
        "",
        "Ontology reasoning supports meaning. Server policy enforces tenant access.",
      ),
    );
    container.append(chunk);
  } else
    container.append(
      element(
        "p",
        "query-note",
        "Direct generation uses the physical schema. No business catalog is retrieved for this approach.",
      ),
    );
}
function renderSummary() {
  const entries = Object.entries(state.results);
  const successful = entries.filter(([, result]) => result.ok);
  const summary = $("#comparison-summary");
  summary.hidden = false;
  let text = `${successful.length} of ${entries.length} approaches executed successfully.`;
  let diverged = false;
  if (successful.length > 1) {
    const values = successful.map(([, result]) => result.data.value);
    diverged = values.some((value) => Math.abs(value - values[0]) > 1e-7);
    text += diverged
      ? " Results differ. Inspect the queries and business context to understand why."
      : " Results agree on this question. Agreement alone does not establish correctness.";
    const fastest = successful.reduce((a, b) =>
      a[1].data.latency_ms < b[1].data.latency_ms ? a : b,
    );
    text += ` Fastest this run: ${MODES[fastest[0]].name}.`;
  }
  summary.className = `comparison-summary${diverged ? " diverged" : ""}`;
  summary.textContent = text;
  $("#latency-panel").hidden = successful.length === 0;
  const chart = $("#latency-chart");
  chart.replaceChildren();
  const max = Math.max(
    ...successful.map(([, result]) => result.data.latency_ms),
    1,
  );
  for (const [mode, result] of successful) {
    const row = element("div", `chart-row ${MODES[mode].color}`);
    const track = element("div", "bar-track");
    const bar = element("div", "bar");
    bar.style.width = `${(result.data.latency_ms / max) * 100}%`;
    track.append(bar);
    row.append(
      element("span", "", MODES[mode].name),
      track,
      element("strong", "", ms(result.data.latency_ms)),
    );
    chart.append(row);
  }
  $("#export-button").disabled = entries.length === 0;
}
async function run() {
  if (state.busy || !state.session) return;
  const modes = selected();
  const question = $("#question").value.trim();
  if (question.length < 5 || !modes.length) {
    notice(
      "Enter a question of at least five characters and select an approach.",
    );
    return;
  }
  state.busy = true;
  state.results = {};
  state.question = question;
  state.startedAt = new Date().toISOString();
  $("#results").replaceChildren();
  $("#comparison-summary").hidden = true;
  $("#latency-panel").hidden = true;
  $("#export-button").disabled = true;
  updateSelection();
  $("#run-caption").textContent = `Running: “${question}”`;
  document
    .querySelectorAll(
      "input[name=mode], #question, .examples button, #select-all, #connect-button, #api-key",
    )
    .forEach((input) => (input.disabled = true));
  modes.forEach(renderLoading);
  try {
    await Promise.all(
      modes.map(async (mode) => {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 60000);
        try {
          const data = await api("/v1/query", {
            method: "POST",
            body: JSON.stringify({ question, mode }),
            signal: controller.signal,
          });
          state.results[mode] = { ok: true, data };
        } catch (error) {
          state.results[mode] = {
            ok: false,
            error:
              error.name === "AbortError"
                ? "The request timed out. Check your services and try again."
                : error.message,
          };
          if (error.status === 401) {
            resetConnection();
            notice("Your API key is no longer valid. Reconnect to continue.");
          }
        } finally {
          clearTimeout(timeout);
        }
        renderResult(mode, state.results[mode]);
      }),
    );
    $("#run-caption").textContent =
      `Completed: “${question}” · ${new Date(state.startedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    renderSummary();
  } finally {
    state.busy = false;
    document
      .querySelectorAll(
        "input[name=mode], #question, .examples button, #select-all, #connect-button, #api-key",
      )
      .forEach((input) => (input.disabled = false));
    updateSelection();
  }
}
$("#run-button").addEventListener("click", run);
$("#question").addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    run();
  }
});
$("#select-all").addEventListener("click", () => {
  const all = selected().length !== 3;
  document
    .querySelectorAll("input[name=mode]")
    .forEach((input) => (input.checked = all));
  updateSelection();
});
document
  .querySelectorAll("input[name=mode]")
  .forEach((input) => input.addEventListener("change", updateSelection));
document.querySelectorAll("[data-question]").forEach((button) =>
  button.addEventListener("click", () => {
    $("#question").value = button.dataset.question;
    $("#question").focus();
  }),
);
$("#export-button").addEventListener("click", () => {
  const payload = {
    question: state.question,
    started_at: state.startedAt,
    planner: state.session?.planner,
    tenant: state.session?.tenant,
    results: state.results,
    interpretation:
      "Single-run measurements. Agreement is not an accuracy score. Fixture baseline errors are intentional.",
  };
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
  );
  const link = element("a");
  link.href = url;
  link.download = `governedtext2sql-${Date.now()}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
renderEmpty();
updateSelection();
