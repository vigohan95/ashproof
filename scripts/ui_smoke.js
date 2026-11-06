// Run the task page's real inline script against a real timeline, with a stub DOM. This proves render() does not throw
// and that the fields reach the page. It is not a browser test: nothing is laid out or clicked.
//   node scripts/ui_smoke.js <page.html> <timeline.json>
const fs = require("fs");
const vm = require("vm");

const html = fs.readFileSync(process.argv[2], "utf8");
const timeline = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
const ids = [...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]);
const known = new Set(ids);
const missing = new Set();

function element(id) {
  const el = { id, style: {}, dataset: {}, className: "", textContent: "", innerHTML: "", disabled: false, value: "" };
  el.firstChild = { textContent: "" };
  el.addEventListener = () => {};
  el.classList = { add() {}, remove() {}, toggle() {} };
  return el;
}
const els = {};
const document = {
  getElementById(id) {
    if (!known.has(id)) missing.add(id);
    return (els[id] = els[id] || element(id));
  },
  querySelector: () => element("q"),
  querySelectorAll: () => [],
  createElement: () => element("c"),
  addEventListener() {},
};
const sandbox = {
  document,
  window: { location: {} },
  console,
  setInterval: () => 0,
  setTimeout: () => 0,
  clearInterval() {},
  clearTimeout() {},
  fetch: async () => ({ ok: true, status: 200, json: async () => timeline, text: async () => "" }),
};
sandbox.window.document = document;
vm.createContext(sandbox);
for (const s of scripts) vm.runInContext(s, sandbox);
vm.runInContext("render", sandbox)(timeline);

const out = {
  status: els.status && els.status.textContent,
  has_plan: !!(els.plan && els.plan.innerHTML.length),
  vm_rows: els.vms ? (els.vms.innerHTML.match(/<tr/g) || []).length : 0,
  step_rows: els.steps ? (els.steps.innerHTML.match(/<tr/g) || []).length : 0,
  logs: els["step-logs"] ? els["step-logs"].innerHTML.length : 0,
  verdict: els.verdict ? els.verdict.innerHTML.slice(0, 60) : "",
  events: els.events ? (els.events.innerHTML.match(/<li/g) || []).length : 0,
  error_shown: els["task-error"] ? els["task-error"].textContent.slice(0, 80) : "",
  ids_used_but_not_in_html: [...missing],
};
console.log(JSON.stringify(out));
process.exit(missing.size ? 1 : 0);
