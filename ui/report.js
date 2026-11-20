"use strict";

const scan = JSON.parse(document.getElementById("firsttrace-data").textContent);
const $ = id => document.getElementById(id);
const FUNDING = ["Pre-equity", "Pre-seed", "Seed", "Series A", "Series B", "Series C+", "Growth", "Unverified"];
const FUNDED = new Set(["Seed", "Seed reported", "Series A", "Series B", "Series C+", "Growth"]);
const PRODUCT = ["Idea / research", "Prototype", "Pilot / beta", "Launched", "Unverified"];
const VIEWS = ["All leads", "New signals", "Watchlist", "Held"];
const DECISIONS = ["Watch", "Needs verification", "Pass"];
const DECISION_KEYS = {w: "Watch", v: "Needs verification", p: "Pass"};
const STORAGE_KEY = "firsttrace.workspace.v1";
const SCANNED_KEY = "firsttrace.justScanned";
const CHANGE_LABELS = {
  project: "New project", trace: "New source", release: "New release", funding: "Funding update",
  product: "Product update", footprint: "New footprint", legal: "Legal entity update", site: "New website signal",
};
const DATE_TYPES = {archived: "Archive capture, not a launch date", published: "Publication date"};
const PLACE_NAMES = {"München": "Munich"};
const WINDOW_LABELS = ["Early traces · our window", "First funding round", "Everyone knows them"];

const blankFilters = () => ({query: "", funding: [], product: [], source: "", grant: false, momentum: false});
let filters = blankFilters();
let view = "All leads";
let selected = null;
let lastIndex = 0;
let shownLead = null;
let feedbackTimer;
let workspace = {decisions: {}, presets: []};
let results = [];

try {
  const stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
  if (stored && typeof stored === "object") {
    workspace = {decisions: stored.decisions || {}, presets: Array.isArray(stored.presets) ? stored.presets : []};
  }
} catch {
  // A browser can disable local storage for a local file.
}

/* ---------- small helpers ---------- */

function node(tag, className, label) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (label != null) item.textContent = label;
  return item;
}

function button(label, className, action) {
  const item = node("button", className, label);
  item.type = "button";
  item.addEventListener("click", action);
  return item;
}

function sourceLink(url, label) {
  const item = node("a", "", label);
  if (typeof url === "string" && url.startsWith("https://")) {
    item.href = url;
    item.target = "_blank";
    item.rel = "noopener noreferrer";
  }
  return item;
}

function plural(count, word, many = `${word}s`) {
  return `${count} ${count === 1 ? word : many}`;
}

function formatDate(value) {
  if (!value) return "";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-GB", {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"});
}

function timeNode(value, className = "") {
  const item = node("time", className, formatDate(value));
  item.dateTime = value.slice(0, 10);
  return item;
}

function notify(message) {
  clearTimeout(feedbackTimer);
  const toast = $("feedback");
  toast.hidden = true;
  toast.textContent = message;
  void toast.offsetWidth;
  toast.hidden = false;
  feedbackTimer = setTimeout(() => { toast.hidden = true; }, 3000);
}

function persist(message) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(workspace));
    notify(message);
  } catch {
    notify(`${message} · saved for this session only`);
  }
}

function download(name, type, text) {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const link = node("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ---------- lead accessors ---------- */

const legal = lead => lead.web?.legal || {};
const signal = (lead, key) => (lead.web?.signals || []).find(row => row.key === key);
const place = lead => PLACE_NAMES[lead.location] || lead.location || "";
const decision = lead => workspace.decisions[lead.id] || "";
const changes = lead => lead.changes || [];
const windowOf = lead => lead.window || {zone: 0, label: "Not assessed", reason: ""};

function fundingStage(lead) {
  const label = lead.assessment.funding?.label || "Unverified";
  return label === "Seed reported" ? "Seed" : label;
}

function fundingLabel(lead) {
  const label = lead.assessment.funding?.label;
  return !label || label === "Unverified" ? "Funding unverified" : label;
}

function productStage(lead) {
  return lead.assessment.product?.label || "Unverified";
}

function teamSource(lead) {
  return lead.assessment.team || {label: lead.review.team, url: lead.review.team_url};
}

function people(lead) {
  const facts = legal(lead);
  if (facts.directors?.length) return {names: facts.directors, note: facts.people_note, url: lead.web.legal_url};
  const team = teamSource(lead);
  return team.label ? {names: [team.label], note: "Team source", url: team.url} : null;
}

function companyLine(lead) {
  const facts = legal(lead);
  if (facts.stage === "Being incorporated") return "Not incorporated yet";
  if (facts.stage === "No company form stated") return "No company form yet";
  return facts.entity || "";
}

function summaryText(lead) {
  return lead.review.product || lead.assessment.note || lead.web?.summary
    || lead.descriptions?.[0]?.text || "Source listing only. Verify the team, product and funding before outreach.";
}

function latestDate(lead) {
  return [...lead.traces.map(trace => trace.date), ...lead.releases.map(release => release.date)].filter(Boolean).sort().pop() || "";
}

/* ---------- search engine: BM25 over everything FirstTrace read ---------- */

const STOP = new Set(("a an and are as at be by de der die das den dem des ein eine einer und oder fuer mit von zu im in " +
  "is it of on or the to for with that who what which we our their they startup startups team teams founders founder " +
  "company companies looking find show me yet still keep any some all from like").split(" "));

function fold(text) {
  return String(text || "").toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .normalize("NFD").replace(/[̀-ͯ]/g, "");
}

function stem(token) {
  if (token.length <= 4) return token;
  for (const suffix of ["ungen", "ung", "ern", "en", "er", "es", "e", "s"]) {
    if (token.endsWith(suffix) && token.length - suffix.length >= 4) return token.slice(0, -suffix.length);
  }
  return token;
}

function tokens(text) {
  return fold(text).split(/[^a-z0-9]+/).filter(token => token.length > 1 && !STOP.has(token)).map(stem);
}

const SYNONYMS = Object.fromEntries(Object.entries({
  ai: "ki artificial intelligence ml machine llm genai kuenstliche",
  ki: "ai llm intelligence",
  api: "schnittstelle apis interface",
  security: "sicherheit cyber cybersecurity secure schutz schwachstelle firewall",
  doctor: "arzt aerzte praxis praxen clinic clinical klinisch medical medizin patient abrechnung",
  practice: "praxis praxen",
  health: "gesundheit medical medizin patient clinic care",
  medical: "medizin health klinisch medtech",
  energy: "energie strom power grid solar",
  construction: "bau beton building",
  finance: "finanz payment zahlung ueberweisung bank banking fintech",
  fintech: "finanz payment zahlung bank",
  payment: "zahlung ueberweisung",
  logistics: "logistik supply transport bestandsplanung inventory",
  manufacturing: "fertigung produktion industrie 3d druck printing factory",
  robot: "robotik roboter automation automatisierung",
  agriculture: "agrar landwirtschaft farm soil boden",
  climate: "klima co2 carbon nachhaltig sustainability emission",
  quantum: "quanten qubit",
  space: "satellit raumfahrt orbit satellite",
  navigation: "gps satellitensignal",
  children: "kinder jugendliche kids",
  compliance: "regtech recht legal",
  data: "daten analytics",
  developer: "entwickler code software programming devtools",
  phone: "telefon voice",
  insurance: "versicherung",
  education: "bildung lernen learning",
  mobility: "mobilitaet vehicle fahrzeug",
  battery: "batterie",
  chip: "halbleiter photonic photonik semiconductor",
}).map(([key, list]) => [stem(fold(key)), list.split(" ").map(word => stem(fold(word)))]));

const INTENTS = [
  {key: "precompany", label: "Not incorporated yet",
    pattern: /\b(not (?:yet )?incorporated|pre-?company|before incorporation|in gruendung|being incorporated|no company yet)\b/,
    test: lead => ["Being incorporated", "No company form stated"].includes(legal(lead).stage)},
  {key: "incorporated", label: "Incorporated", pattern: /\b(incorporated|gmbh|registered company)\b/,
    test: lead => (legal(lead).stage || "").startsWith("Incorporated")},
  {key: "unfunded", label: "No round seen",
    pattern: /\b(not funded(?: yet)?|unfunded|pre-?seed|before (?:a |the )?(?:seed|round)|no investors?|pre-?equity|not raised)\b/,
    test: lead => !FUNDED.has(lead.assessment.funding?.label) && !signal(lead, "investors")},
  {key: "raising", label: "Talking to investors", pattern: /\b(raising|fundrais\w*|talking to investors(?: now)?|seeking invest\w*)\b/,
    test: lead => Boolean(signal(lead, "raising"))},
  {key: "hiring", label: "Hiring", pattern: /\bhiring\b/, test: lead => Boolean(signal(lead, "hiring"))},
  {key: "pilot", label: "Pilot or beta", pattern: /\b(pilots?|beta|early access|waitlist)\b/,
    test: lead => Boolean(signal(lead, "pilot") || signal(lead, "beta")) || productStage(lead) === "Pilot / beta"},
  {key: "momentum", label: "Advancing in competitions", pattern: /\b(finalists?|winners?|jur(?:y|ies)|advancing|competitions?)\b/,
    test: lead => Boolean(lead.momentum)},
  {key: "new", label: "New since last scan", pattern: /\b(new signals?|this week|since last scan)\b/, test: lead => changes(lead).length > 0},
  {key: "releases", label: "Public releases", pattern: /\b(open source|github|releases?)\b/, test: lead => lead.releases.length > 0},
  {key: "open", label: "Window open", pattern: /\b(open window|window open|call now|call this week)\b/, test: lead => windowOf(lead).zone === 1},
];
const PLACES = {
  munich: "muenchen", muenchen: "muenchen", munchen: "muenchen", erlangen: "erlangen", wuerzburg: "wuerzburg",
  wurzburg: "wuerzburg", nuremberg: "nuernberg", nuernberg: "nuernberg", nurnberg: "nuernberg", bamberg: "bamberg",
  garching: "garching", regensburg: "regensburg", augsburg: "augsburg", ingolstadt: "ingolstadt", haar: "haar",
};

function documentText(lead) {
  const facts = legal(lead);
  return [
    [lead.name, 3], [lead.descriptions?.map(item => item.text).join(" "), 2], [lead.web?.title, 2], [lead.web?.summary, 2],
    [lead.review.product, 2], [lead.review.market, 1], [lead.assessment.note, 1], [lead.tags.join(" "), 1],
    [lead.web?.text, 1], [facts.entity, 2], [(facts.directors || []).join(" "), 2], [lead.review.team, 2],
    [lead.assessment.team?.label, 2], [(lead.web?.signals || []).map(row => row.label).join(" "), 1],
    [lead.traces.map(trace => `${trace.source} ${trace.title}`).join(" "), 1], [lead.momentum, 1], [place(lead), 1],
    [facts.address, 1],
  ];
}

const index = (() => {
  const docs = new Map();
  const frequency = new Map();
  let total = 0;
  for (const lead of scan.leads) {
    const counts = new Map();
    let length = 0;
    for (const [text, weight] of documentText(lead)) {
      for (const token of tokens(text)) {
        counts.set(token, (counts.get(token) || 0) + weight);
        length += weight;
      }
    }
    docs.set(lead.id, {counts, length});
    total += length;
    for (const token of counts.keys()) frequency.set(token, (frequency.get(token) || 0) + 1);
  }
  return {docs, frequency, vocabulary: [...frequency.keys()], average: total / Math.max(1, scan.leads.length)};
})();

function expand(term) {
  const found = new Map();
  const add = (token, weight) => found.set(token, Math.max(found.get(token) || 0, weight));
  const variants = [[term, 1], ...(SYNONYMS[term] || []).map(word => [word, 0.7])];
  for (const [word, weight] of variants) {
    for (const token of index.vocabulary) {
      if (token === word) add(token, weight);
      else if (word.length >= 3 && token.startsWith(word)) add(token, weight * 0.8);
      else if (word.length >= 5 && token.includes(word)) add(token, weight * 0.5);
    }
  }
  return found;
}

function parseQuery(query) {
  let text = ` ${fold(query)} `;
  const intents = [];
  for (const intent of INTENTS) {
    if (intent.key === "incorporated" && intents.some(item => item.key === "precompany")) continue;
    if (intent.pattern.test(text)) {
      intents.push(intent);
      text = text.replace(intent.pattern, " ");
    }
  }
  let city = null;
  for (const [word, key] of Object.entries(PLACES)) {
    const pattern = new RegExp(`\\b(?:in |near |around )?${word}\\b`);
    if (pattern.test(text)) {
      city = {word, key};
      text = text.replace(pattern, " ");
      break;
    }
  }
  text = text.replace(/\b(bavaria|bayern|germany|deutschland|now|ones?|first)\b/g, " ");
  return {terms: [...new Set(tokens(text))], intents, city};
}

function search(query) {
  const parsed = parseQuery(query);
  const expansions = parsed.terms.map(expand);
  const scores = new Map();
  const matched = new Map();
  const count = scan.leads.length;
  for (const lead of scan.leads) {
    if (parsed.city && !fold(`${place(lead)} ${lead.location} ${legal(lead).address || ""}`).includes(parsed.city.key)
      && !(parsed.city.key === "muenchen" && fold(`${place(lead)} ${legal(lead).address || ""}`).includes("munich"))) continue;
    if (!parsed.intents.every(intent => intent.test(lead))) continue;
    const doc = index.docs.get(lead.id);
    let score = 0;
    const hits = new Set();
    let terms = 0;
    expansions.forEach(expansion => {
      let best = 0;
      for (const [token, weight] of expansion) {
        const tf = doc.counts.get(token);
        if (!tf) continue;
        const idf = Math.log(1 + (count - index.frequency.get(token) + 0.5) / (index.frequency.get(token) + 0.5));
        const part = weight * idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * doc.length / index.average));
        best = Math.max(best, part);
        hits.add(token);
      }
      score += best;
      if (best) terms += 1;
    });
    // Most of the described thesis must be present, not just one common word.
    if (expansions.length && terms < Math.max(1, Math.ceil(expansions.length * 0.6))) continue;
    scores.set(lead.id, score);
    matched.set(lead.id, hits);
  }
  return {parsed, scores, matched};
}

function snippet(lead, hits) {
  const texts = [
    ...(lead.descriptions || []).map(item => item.text), lead.web?.summary, lead.review.product, lead.assessment.note,
    ...(lead.web?.text || "").split(/(?<=[.!?])\s+|\n/),
  ].filter(text => text && text.length > 12);
  let best = null;
  let bestScore = 0;
  for (const text of texts) {
    const found = tokens(text).filter(token => hits.has(token)).length;
    if (found > bestScore) {
      best = text;
      bestScore = found;
    }
  }
  return best ? highlighted(best.length > 220 ? `${best.slice(0, 217)}…` : best, hits) : null;
}

function highlighted(text, hits) {
  const holder = node("span", "snippet");
  for (const part of text.split(/([\p{L}\p{N}]+)/u)) {
    const token = stem(fold(part));
    if (part && hits.has(token)) holder.append(node("mark", "", part));
    else holder.append(document.createTextNode(part));
  }
  return holder;
}

/* ---------- filters and views ---------- */

function matches(lead, options = filters) {
  return (!options.funding.length || options.funding.includes(fundingStage(lead)))
    && (!options.product.length || options.product.includes(productStage(lead)))
    && (!options.source || (options.source === "GitHub releases" && lead.releases.length > 0)
      || lead.traces.some(trace => trace.source === options.source))
    && (!options.grant || Boolean(lead.assessment.grant) || lead.traces.some(trace => trace.source === "UnternehmerTUM"))
    && (!options.momentum || Boolean(lead.momentum));
}

function inView(lead, currentView) {
  switch (currentView) {
    case "Held": return Boolean(lead.hold) || decision(lead) === "Pass";
    case "Watchlist": return Boolean(decision(lead)) && decision(lead) !== "Pass";
    case "New signals": return changes(lead).length > 0;
    default: return true;
  }
}

function filterGroup(id, category, labels) {
  const all = button("All", "pill", () => update([]));
  const chips = labels.map(label => {
    const chip = button("", "pill", () => {
      const current = filters[category];
      update(current.includes(label) ? current.filter(item => item !== label) : [...current, label]);
    });
    chip.append(node("span", "", label), node("span", "count"));
    return chip;
  });
  $(id).append(all, ...chips);
  function update(value) {
    filters[category] = value;
    renderQueue();
  }
  return () => {
    all.setAttribute("aria-pressed", String(!filters[category].length));
    chips.forEach((chip, index) => {
      const label = labels[index];
      const count = scan.leads.filter(lead => inView(lead, view) && matches(lead, {...filters, [category]: [label]})).length;
      chip.setAttribute("aria-pressed", String(filters[category].includes(label)));
      chip.lastChild.textContent = String(count);
      chip.classList.toggle("empty", count === 0);
      chip.setAttribute("aria-label", `${label}, ${plural(count, "lead")}`);
    });
  };
}

const syncFunding = filterGroup("funding-filters", "funding", FUNDING);
const syncProduct = filterGroup("product-filters", "product", PRODUCT);
const EXAMPLES = [
  "AI for medical practices", "API security in Munich", "Not incorporated yet", "Talking to investors now",
  "Finalists, not funded yet", "Hiring, open window",
];
$("suggested-searches").append(...EXAMPLES.map(example => button(example, "example", () => {
  filters.query = example;
  view = "All leads";
  lastIndex = 0;
  renderQueue();
  $("calls").scrollIntoView({behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
})));
const views = VIEWS.map(label => button(label, "view", () => {
  view = label;
  renderQueue();
}));
$("views").append(...views);

function syncControls() {
  if ($("query").value !== filters.query) $("query").value = filters.query;
  $("source-filter").value = filters.source;
  $("grant-filter").checked = filters.grant;
  $("momentum-filter").checked = filters.momentum;
  syncFunding();
  syncProduct();
  const active = filters.funding.length + filters.product.length + Boolean(filters.source) + filters.grant + filters.momentum;
  $("filter-count").textContent = active ? `${active} active` : "";
}

/* ---------- lead brief ---------- */

function section(parent, title, className = "") {
  const item = node("section", className);
  item.append(node("h3", "", title));
  parent.append(item);
  return item;
}

function scoreRing(score, size = "") {
  const ring = node("span", `ring ${size}`);
  ring.style.setProperty("--p", String(score ?? 0));
  ring.append(node("span", "", String(score ?? "–")));
  ring.setAttribute("aria-label", `HTGF readiness ${score} of 100`);
  return ring;
}

function windowChip(lead) {
  const current = windowOf(lead);
  return node("span", `window-chip zone-${current.zone}`, current.label);
}

function windowBar(lead) {
  const current = windowOf(lead);
  const wrap = node("div", "window");
  const track = node("div", "window-track");
  WINDOW_LABELS.forEach((label, index) => {
    const segment = node("div", `segment segment-${index + 1}${current.zone === index + 1 ? " active" : ""}`);
    segment.append(node("span", "", label));
    track.append(segment);
  });
  const position = {0: 3, 1: current.label.includes("pre-company") ? 10 : 30, 2: 62, 3: 88}[current.zone];
  const marker = node("span", "window-marker");
  marker.style.left = `${position}%`;
  marker.title = current.label;
  track.append(marker);
  const caption = node("p", "window-caption");
  caption.append(node("strong", "", current.label), ` · ${current.reason}`);
  wrap.append(track, caption);
  return wrap;
}

function timeline(lead, parent) {
  const traces = lead.traces.map(trace => ({...trace, label: `${trace.source} · ${trace.title}`, kind: "trace"}));
  const releases = lead.releases.map(release => ({...release, label: `GitHub · ${release.title}`, kind: "release"}));
  const footprint = (lead.footprint || []).map(row => ({...row, label: `${row.source} · ${row.title}`, kind: "footprint"}));
  const highlights = releases.length > 2 ? [releases[0], releases[releases.length - 1]] : releases;
  const entries = [...traces, ...highlights, ...footprint]
    .sort((left, right) => (left.date || "9999").localeCompare(right.date || "9999"));
  parent.append(timelineList(entries));
  if (releases.length > 2) {
    const more = node("details", "more-releases");
    more.append(node("summary", "", `${releases.length - 2} more releases`), timelineList(releases.slice(1, -1)));
    parent.append(more);
  }
}

function timelineList(entries) {
  const list = node("ol", "timeline");
  for (const entry of entries) {
    const row = node("li", entry.date ? entry.kind : `${entry.kind} undated`);
    const when = entry.date ? timeNode(entry.date) : node("time", "", "Publication date unavailable");
    if (entry.date_type === "archived") when.append(" · archive capture");
    if (entry.date_type) when.title = DATE_TYPES[entry.date_type] || entry.date_type;
    row.append(when, sourceLink(entry.url, entry.label));
    if (entry.identity_url) {
      const association = node("small");
      association.append(sourceLink(entry.identity_url, "Verify team match"));
      row.append(association);
    }
    list.append(row);
  }
  return list;
}

function factRow(list, label, value, link) {
  if (!value) return;
  const row = node("div");
  const detail = node("dd");
  if (typeof value === "string") detail.append(value);
  else detail.append(value);
  if (link) detail.append(" ", link);
  row.append(node("dt", "", label), detail);
  list.append(row);
}

function research(lead, panel) {
  const web = lead.web;
  const block = section(panel, "Found automatically", "research");
  if (!web) {
    block.append(node("p", "muted", scan.cutoff
      ? "Company research reflects today’s websites, so it is hidden in a retrospective view."
      : "No company website could be matched to this team with a legal notice naming it. FirstTrace never guesses identity."));
    return;
  }
  const facts = web.legal || {};
  const match = node("p", web.match === "Analyst-verified domain" ? "match verified" : "match auto");
  match.append(web.match === "Analyst-verified domain" ? "✓ Analyst-verified website" : `Auto-matched: ${web.match}. Confirm before outreach.`);
  block.append(match);
  if (web.stale) block.append(node("p", "muted", `Researched ${formatDate(web.checked_at)}. The site did not answer in the latest scan.`));
  const list = node("dl", "facts-list");
  factRow(list, "Website", sourceLink(web.url, web.domain), null);
  factRow(list, "Legal stage", facts.stage && facts.stage !== "Unknown" ? facts.stage : "");
  if (facts.entity) {
    const entity = node("span", "", facts.entity);
    if (!facts.brand_match) entity.append(node("small", "note", ` Different from the brand “${lead.name}”: a database search for the brand can miss it.`));
    factRow(list, "Legal entity", entity);
  }
  factRow(list, "Register", facts.register ? `${facts.register}${facts.court ? ` · Amtsgericht ${facts.court}` : ""}` : "");
  factRow(list, "Address", facts.address ? `${facts.address}${facts.german ? " · Germany" : ""}` : "");
  if (facts.directors?.length) factRow(list, "People", `${facts.directors.join(", ")} · ${facts.people_note}`);
  factRow(list, "Website says", web.summary || web.title);
  if (web.legal_url) factRow(list, "Source", sourceLink(web.legal_url, "Legal notice (Impressum)"), null);
  block.append(list);
  if (web.signals?.length) {
    const signals = node("ul", "signals");
    for (const row of web.signals) {
      const item = node("li", `signal signal-${row.key}`);
      item.append(node("strong", "", row.label), node("q", "", row.quote));
      signals.append(item);
    }
    block.append(signals);
  }
}

function setDecision(lead, label) {
  const active = decision(lead) === label;
  if (active) delete workspace.decisions[lead.id];
  else workspace.decisions[lead.id] = label;
  persist(active ? `${lead.name} · decision cleared` : `${lead.name} · ${label}`);
  renderQueue();
}

function outreach(lead) {
  const team = people(lead);
  const firstNames = team?.note?.startsWith("Managing") || team?.note?.startsWith("People")
    ? team.names.map(name => name.replace(/^(?:(?:Dr|Prof)\.\s*)+/, "").split(" ")[0]).join(" and ")
    : "";
  const traces = [...lead.traces].filter(trace => trace.date).sort((a, b) => b.date.localeCompare(a.date));
  const competition = traces.find(trace => trace.source === "BayStartUP");
  let hook = "your work";
  if (competition) {
    const [contest, stage] = competition.title.split(" · ");
    const name = contest.startsWith("Nordbayern") ? "the Nordbayern business plan competition" : "the Munich business plan competition";
    hook = `${stage ? stage.toLowerCase().replace("phase", "Phase") : "your listing"} in ${name} (${formatDate(competition.date)})`;
    hook = hook.startsWith("finalist") || hook.startsWith("winner") ? `your result as a ${hook}` : `your ${hook}`;
  } else if (lead.traces.some(trace => trace.source === "UnternehmerTUM")) {
    hook = "the UnternehmerTUM prototype grant";
  } else if (lead.releases.length) {
    hook = "your public releases on GitHub";
  }
  const extra = signal(lead, "pilot") ? " and saw that you are running pilots" : signal(lead, "beta") ? " and saw your early access program"
    : signal(lead, "hiring") ? " and noticed that you are hiring" : "";
  return [
    `Subject: ${lead.name} — hello from HTGF`, "",
    `Hi ${firstNames || "there"},`, "",
    `I work with the Digital Tech team at High-Tech Gründerfonds (HTGF). I came across ${lead.name} through ${hook}${extra}.`, "",
    "We back technical founders in Germany from the very first round, and we like to get to know teams early, well before a raise.", "",
    `Would you be open to a 20-minute call in the next two weeks? I would love to hear how ${lead.name} started and where you want to take it.`, "",
    "Best regards,", "[Your name]", "HTGF · Digital Tech",
  ].join("\n");
}

async function copyOutreach(lead) {
  const text = outreach(lead);
  try {
    await navigator.clipboard.writeText(text);
    notify("Outreach draft copied · review before sending");
  } catch {
    download(`${lead.name}-outreach.txt`, "text/plain", text);
    notify("Outreach draft downloaded · review before sending");
  }
}

function renderDetails(lead) {
  const panel = $("lead-details");
  const changed = shownLead !== (lead?.id || null);
  shownLead = lead?.id || null;
  panel.replaceChildren();
  if (!lead) {
    const title = node("h2", "", "No lead selected");
    title.id = "lead-title";
    panel.append(title, node("p", "muted location", "Try another search, a different view or clear your filters."));
    return;
  }
  if (changed) {
    panel.classList.remove("enter");
    void panel.offsetWidth;
    panel.classList.add("enter");
  }
  const back = node("a", "mobile-back", "↑ Back to leads");
  back.href = "#result-count";
  panel.append(back);

  const head = node("div", "brief-head");
  const titles = node("div");
  titles.append(lead.hold ? node("p", "eyebrow held", "Held for review") : windowChip(lead));
  const title = node("h2", "", lead.name);
  title.id = "lead-title";
  titles.append(title);
  const meta = [companyLine(lead), legal(lead).register, place(lead)].filter(Boolean);
  if (meta.length) titles.append(node("p", "location muted", meta.join(" · ")));
  head.append(titles, scoreRing(lead.score, "large"));
  panel.append(head);

  const badges = node("div", "badges");
  const funding = fundingLabel(lead);
  badges.append(node("span", funding === "Funding unverified" ? "badge warn" : "badge", funding));
  if (lead.assessment.product) badges.append(node("span", "badge good", productStage(lead)));
  if (lead.momentum) badges.append(node("span", "badge good", `Jury progression · ${lead.momentum}`));
  if (lead.assessment.grant) badges.append(node("span", "badge", lead.assessment.grant.label));
  for (const kind of changes(lead)) badges.append(node("span", "badge new", CHANGE_LABELS[kind] || kind));
  if (lead.hold) badges.append(node("span", "badge hold", "Held for review"));
  panel.append(badges);

  const toolbar = node("div", "toolbar");
  const actions = node("div", "actions");
  actions.setAttribute("role", "group");
  actions.setAttribute("aria-label", "Triage decision");
  for (const label of DECISIONS) {
    const action = button(label, "action", () => {
      setDecision(lead, label);
      const next = [...$("lead-details").querySelectorAll(".action")].find(item => item.dataset.label === label);
      (selected === lead.id && next ? next : $("lead-details")).focus();
    });
    action.dataset.label = label;
    const key = Object.keys(DECISION_KEYS).find(item => DECISION_KEYS[item] === label);
    const hint = node("kbd", "", key.toUpperCase());
    hint.setAttribute("aria-hidden", "true");
    action.append(hint);
    action.setAttribute("aria-pressed", String(decision(lead) === label));
    actions.append(action);
  }
  toolbar.append(actions, button("Copy outreach draft", "btn secondary small", () => copyOutreach(lead)),
    button("Print brief", "btn secondary small", () => window.print()));
  panel.append(toolbar);

  if (lead.hold) {
    const hold = node("div", "notice");
    hold.append(document.createTextNode(`${lead.hold} `), sourceLink(lead.hold_url, "Review source"));
    panel.append(hold);
  }

  if (lead.why_now) {
    const why = node("p", "why-now");
    why.append(node("strong", "", "Why now "), lead.why_now);
    panel.append(why);
  }
  panel.append(windowBar(lead));

  const summary = section(panel, "What they do");
  summary.append(node("p", "lede", summaryText(lead)));
  if (lead.review.market) summary.append(node("p", "", lead.review.market));
  for (const item of (lead.descriptions || []).slice(0, 3)) {
    const line = node("p", "quote-line");
    line.append(node("q", "", item.text), " ", sourceLink(item.url, item.source));
    summary.append(line);
  }

  const score = section(panel, `HTGF readiness · ${lead.score}/100`, "checks");
  const list = node("ul", "check-list");
  for (const row of lead.checks || []) {
    const item = node("li", row.earned === row.points ? "full" : row.earned ? "part" : "none");
    const label = node("span", "check-label");
    label.append(node("strong", "", row.label), node("span", "points", `${row.earned}/${row.points}`));
    const detail = node("span", "check-detail", row.detail);
    if (row.url) detail.append(" ", sourceLink(row.url, "source"));
    item.append(label, detail);
    list.append(item);
  }
  score.append(list, node("p", "muted", "Readiness to contact under HTGF’s stated criteria. Every point links to its observation. Not a prediction of success."));

  research(lead, panel);

  const trail = section(panel, "Evidence timeline");
  timeline(lead, trail);

  const ask = section(panel, "Ask on the first call", "questions");
  const questions = node("ol");
  for (const question of lead.questions || []) questions.append(node("li", "", question));
  ask.append(questions);

  const stage = section(panel, "Funding and product stage", "plain-list");
  const fundingNote = node("p");
  fundingNote.append(lead.review.funding || (lead.assessment.funding && lead.assessment.funding.label !== "Unverified"
    ? `${lead.assessment.funding.label} in the linked source.` : "Equity funding remains unverified."));
  const fundingUrl = lead.assessment.funding?.url || lead.review.funding_url;
  if (fundingUrl) fundingNote.append(" ", sourceLink(fundingUrl, "Funding source"));
  stage.append(fundingNote);
  if (lead.assessment.product) {
    const product = node("p");
    product.append("Product stage · ", sourceLink(lead.assessment.product.url, lead.assessment.product.label));
    stage.append(product);
  }
}

/* ---------- call list and results ---------- */

function callCandidates() {
  return scan.leads
    .filter(lead => !lead.hold && decision(lead) !== "Pass" && windowOf(lead).zone === 1)
    .sort((a, b) => b.score - a.score || latestDate(b).localeCompare(latestDate(a)) || a.name.localeCompare(b.name));
}

function openLead(id) {
  filters = {...filters, funding: [], product: [], source: "", grant: false, momentum: false};
  view = "All leads";
  selected = id;
  renderQueue();
  $("workspace").scrollIntoView({behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
  $("lead-details").focus({preventScroll: true});
}

function card(lead, rank, hits) {
  const item = node("li", "call");
  const top = node("div", "call-top");
  top.append(node("span", "rank", String(rank)), scoreRing(lead.score));
  item.append(top, node("h3", "", lead.name));
  item.append(windowChip(lead));
  const meta = [companyLine(lead), place(lead)].filter(Boolean).join(" · ");
  if (meta) item.append(node("p", "call-meta", meta));
  const text = hits && snippet(lead, hits);
  if (text) item.append(text);
  else if (lead.why_now) item.append(node("p", "call-why", lead.why_now));
  item.append(button("Open brief", "btn link small", () => openLead(lead.id)));
  return item;
}

function renderCalls(searching, ranked, matched) {
  const list = $("call-list");
  list.replaceChildren();
  if (searching) {
    $("calls-title").textContent = `Best matches for “${filters.query.trim()}”`;
    $("calls-summary").textContent = ranked.length
      ? `${plural(ranked.length, "match", "matches")} · top ${Math.min(6, ranked.length)} here, all of them in the inbox below.`
      : "No lead matches every part of this search. Remove a condition or try other words.";
    ranked.slice(0, 6).forEach((lead, index) => list.append(card(lead, index + 1, matched.get(lead.id))));
    return;
  }
  const calls = callCandidates().slice(0, 5);
  $("calls-title").textContent = "This week’s call list";
  $("calls-summary").textContent = calls.length
    ? "Open window, highest HTGF readiness, every point sourced. Pass a lead and the next one moves up."
    : "No lead with an open window yet. Run a scan or widen the sources.";
  calls.forEach((lead, index) => list.append(card(lead, index + 1)));
}

function renderUnderstood(parsed) {
  const bar = $("understood");
  bar.replaceChildren();
  if (!filters.query.trim()) {
    bar.hidden = true;
    return;
  }
  bar.append(node("span", "understood-label", "Understood as"));
  if (parsed.city) bar.append(node("span", "chip", `📍 ${parsed.city.word[0].toUpperCase()}${parsed.city.word.slice(1)}`));
  for (const intent of parsed.intents) bar.append(node("span", "chip", intent.label));
  if (parsed.terms.length) bar.append(node("span", "chip text", `about “${parsed.terms.join(" ")}”`));
  if (!parsed.city && !parsed.intents.length && !parsed.terms.length) bar.append(node("span", "chip text", "everything"));
  bar.hidden = false;
}

/* ---------- inbox ---------- */

function renderQueue({focusRow = false} = {}) {
  syncControls();
  const searching = Boolean(filters.query.trim());
  document.body.classList.toggle("searching", searching);
  const found = searching ? search(filters.query) : null;
  if (found) renderUnderstood(found.parsed);
  else renderUnderstood({terms: [], intents: []});
  const pool = scan.leads.filter(lead => matches(lead) && (!found || found.scores.has(lead.id)));
  const relevance = lead => found ? found.scores.get(lead.id) : 0;
  const top = found ? Math.max(0.0001, ...pool.map(relevance)) : 1;
  const ordered = found
    ? [...pool].sort((a, b) => Boolean(a.hold) - Boolean(b.hold)
      || (found.parsed.terms.length ? (relevance(b) / top * 70 + b.score * 0.3) - (relevance(a) / top * 70 + a.score * 0.3) : b.score - a.score)
      || a.name.localeCompare(b.name))
    : pool;
  for (const [index, label] of VIEWS.entries()) {
    const count = ordered.filter(lead => inView(lead, label)).length;
    views[index].textContent = `${label} · ${count}`;
    views[index].setAttribute("aria-pressed", String(label === view));
  }
  results = ordered.filter(lead => inView(lead, view));
  renderCalls(searching, ordered.filter(lead => !lead.hold), found?.matched);
  const current = results.find(lead => lead.id === selected) || results[Math.min(lastIndex, results.length - 1)];
  selected = current?.id || null;
  lastIndex = Math.max(0, results.indexOf(current));
  $("result-count").textContent = searching
    ? `${plural(results.length, "lead")} ${results.length === 1 ? "matches" : "match"} your search` : plural(results.length, "lead");
  const list = $("lead-list");
  const scrollTop = list.scrollTop;
  list.replaceChildren();
  if (!results.length) {
    const message = view === "New signals" && !scan.hasBaseline ? "Run a second live scan to compare against your baseline."
      : view === "Watchlist" ? "Watch a lead to keep it here." : "No matches in this view.";
    list.append(node("li", "empty", message));
  }
  for (const lead of results) {
    const row = node("li");
    const select = button("", "lead-row", () => {
      selected = lead.id;
      renderQueue({focusRow: true});
      if (matchMedia("(max-width: 760px)").matches) $("lead-details").focus();
    });
    select.setAttribute("aria-current", String(lead.id === selected));
    select.dataset.id = lead.id;
    const heading = node("span", "row-main");
    heading.append(node("strong", "", lead.name));
    if (changes(lead).length) heading.append(node("span", "row-new", changes(lead).includes("project") ? "New" : "Updated"));
    const score = node("span", `row-score zone-${windowOf(lead).zone}${lead.hold ? " held" : ""}`, String(lead.score ?? "–"));
    score.title = `HTGF readiness ${lead.score}/100 · ${windowOf(lead).label}`;
    heading.append(score);
    const caption = [place(lead), companyLine(lead) || fundingLabel(lead), lead.momentum && `↑ ${lead.momentum}`].filter(Boolean).join(" · ");
    select.append(heading, node("span", "row-caption", caption));
    const status = decision(lead) || (lead.hold ? "Held" : windowOf(lead).label);
    select.append(node("span", `row-tag ${lead.hold || decision(lead) === "Pass" ? "held" : `zone-${windowOf(lead).zone}`}`, status));
    if (found?.parsed.terms.length) {
      const text = snippet(lead, found.matched.get(lead.id));
      if (text) select.append(text);
    }
    row.append(select);
    list.append(row);
  }
  list.scrollTop = scrollTop;
  renderDetails(current);
  const active = list.querySelector('[aria-current="true"]');
  if (active) {
    const rowBox = active.getBoundingClientRect();
    const box = list.getBoundingClientRect();
    if (rowBox.top < box.top) list.scrollTop -= box.top - rowBox.top + 8;
    else if (rowBox.bottom > box.bottom) list.scrollTop += rowBox.bottom - box.bottom + 8;
  }
  if (focusRow) active?.focus({preventScroll: true});
}

function move(step) {
  const rows = [...$("lead-list").querySelectorAll(".lead-row")];
  if (!rows.length) return;
  const index = rows.findIndex(row => row.dataset.id === selected);
  const next = rows[Math.min(rows.length - 1, Math.max(0, index + step))];
  selected = next.dataset.id;
  renderQueue({focusRow: $("lead-list").contains(document.activeElement)});
}

/* ---------- saved searches ---------- */

function showPresets() {
  const bar = $("saved-searches");
  bar.replaceChildren();
  for (const preset of workspace.presets) {
    const tag = node("span", "saved-preset");
    tag.append(button(preset.label, "open-preset", () => {
      filters = {...blankFilters(), ...preset.filters};
      view = VIEWS.includes(preset.view) ? preset.view : "All leads";
      renderQueue();
    }));
    const remove = button("×", "delete-preset", () => {
      workspace.presets = workspace.presets.filter(item => item.id !== preset.id);
      persist("Saved search removed");
      showPresets();
      $("save-search").focus();
    });
    remove.setAttribute("aria-label", `Remove saved search ${preset.label}`);
    tag.append(remove);
    bar.append(tag);
  }
  bar.hidden = !workspace.presets.length;
}

$("save-search").addEventListener("click", () => {
  const label = [filters.query.trim(), ...filters.funding, ...filters.product, filters.source, filters.grant && "Grant-backed",
    filters.momentum && "Advancing"].filter(Boolean).join(" · ") || view;
  const settings = {...filters, query: filters.query.trim()};
  const id = JSON.stringify([view, settings]);
  if (workspace.presets.some(preset => preset.id === id)) {
    notify("This search is already saved");
    return;
  }
  workspace.presets.push({id, label, filters: settings, view});
  persist("Search saved · it reruns on every new scan");
  showPresets();
});

/* ---------- exports ---------- */

function exportLeads() {
  return filters.query.trim() ? results.filter(lead => !lead.hold).slice(0, 10) : callCandidates().slice(0, 5);
}

function briefMarkdown() {
  const leads = exportLeads();
  const lines = [
    `# FirstTrace weekly brief · ${formatDate(scan.observedAt)}`, "",
    `${scan.mode}, observed ${scan.observedAt.slice(0, 16).replace("T", " ")} UTC.${filters.query.trim() ? ` Search: “${filters.query.trim()}”.` : ""}`,
    "Readiness counts sourced checks under HTGF's stated criteria. It is not a prediction. Funding stays unverified until checked.", "",
  ];
  leads.forEach((lead, index) => {
    const facts = legal(lead);
    const team = people(lead);
    lines.push(`## ${index + 1}. ${lead.name} · ${lead.score}/100 · ${windowOf(lead).label}`, "");
    if (lead.why_now) lines.push(`**Why now:** ${lead.why_now}`);
    lines.push(`**What they do:** ${summaryText(lead)}`);
    const company = [facts.entity || companyLine(lead), facts.register && `${facts.register}${facts.court ? ` (Amtsgericht ${facts.court})` : ""}`, facts.address]
      .filter(Boolean).join(" · ");
    if (company) lines.push(`**Company:** ${company}`);
    if (team) lines.push(`**People:** ${team.names.join(", ")} (${team.note})`);
    if (lead.web?.url) lines.push(`**Website:** ${lead.web.url}`);
    lines.push("", "**Checks**");
    for (const row of lead.checks || []) lines.push(`- ${row.earned === row.points ? "✓" : row.earned ? "◐" : "✗"} ${row.label} (${row.earned}/${row.points}): ${row.detail}${row.url ? ` · ${row.url}` : ""}`);
    lines.push("", "**Ask on the first call**", ...(lead.questions || []).map(question => `- ${question}`));
    lines.push("", "**Sources**", ...new Set([...lead.traces.map(trace => `- ${trace.title}: ${trace.url}`), lead.web?.legal_url && `- Legal notice: ${lead.web.legal_url}`].filter(Boolean)), "");
  });
  return lines.join("\n");
}

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function crmCsv() {
  const header = ["Company", "Website", "Legal entity", "Register", "Register court", "Address", "People", "Readiness",
    "Window", "Why now", "First public trace", "Funding status", "Jury progression", "Decision", "Sources", "Observed at"];
  const rows = (filters.query.trim() ? results : scan.leads.filter(lead => !lead.hold)).map(lead => {
    const facts = legal(lead);
    const first = (lead.checks || []).find(row => row.label === "Young enough for HTGF");
    return [lead.name, lead.web?.url, facts.entity, facts.register, facts.court, facts.address, people(lead)?.names.join("; "),
      lead.score, windowOf(lead).label, lead.why_now, first?.detail.split(" (")[0].replace("First public trace ", ""),
      fundingLabel(lead), lead.momentum, decision(lead), [...new Set(lead.traces.map(trace => trace.url))].join(" "), scan.observedAt];
  });
  return [header, ...rows].map(row => row.map(csvCell).join(",")).join("\n");
}

$("export-brief").addEventListener("click", () => {
  download(`firsttrace-brief-${scan.observedAt.slice(0, 10)}.md`, "text/markdown", briefMarkdown());
  notify(`Weekly brief downloaded · ${plural(exportLeads().length, "lead")}`);
});
$("export-crm").addEventListener("click", () => {
  download(`firsttrace-crm-${scan.observedAt.slice(0, 10)}.csv`, "text/csv", crmCsv());
  notify("CRM export downloaded · one row per lead, with sources");
});

$("digest").addEventListener("click", () => {
  const updated = scan.leads.filter(lead => changes(lead).length && matches(lead));
  if (!updated.length) {
    notify(scan.hasBaseline ? "No new signals match these filters." : "A second live scan is needed for a digest.");
    return;
  }
  const lines = updated.map(lead => {
    const label = changes(lead).map(kind => CHANGE_LABELS[kind] || kind).join(", ");
    const urls = new Set([...lead.traces.map(trace => trace.url), ...lead.releases.map(release => release.url), lead.web?.legal_url].filter(Boolean));
    return `- ${lead.name} (${lead.score}/100) — ${label}\n  ${[...urls].join("\n  ")}`;
  });
  download("firsttrace-digest.md", "text/markdown", `# FirstTrace changes\n\nScan: ${scan.observedAt} (${scan.mode})\n\n${lines.join("\n")}\n`);
  notify(`Digest downloaded · ${plural(updated.length, "lead")}`);
});

/* ---------- events ---------- */

$("ask").addEventListener("submit", event => {
  event.preventDefault();
  $("calls").scrollIntoView({behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
});
$("query").addEventListener("input", event => { filters.query = event.target.value; lastIndex = 0; renderQueue(); });
$("query").addEventListener("keydown", event => {
  if (event.key === "Escape" && filters.query) {
    event.preventDefault();
    event.stopPropagation();
    filters.query = "";
    renderQueue();
  }
});
$("source-filter").addEventListener("change", event => { filters.source = event.target.value; renderQueue(); });
$("grant-filter").addEventListener("change", event => { filters.grant = event.target.checked; renderQueue(); });
$("momentum-filter").addEventListener("change", event => { filters.momentum = event.target.checked; renderQueue(); });
$("reset").addEventListener("click", () => { filters = {...blankFilters(), query: filters.query}; renderQueue(); notify("Filters cleared"); });

document.addEventListener("keydown", event => {
  const key = event.key.toLowerCase();
  if (event.altKey || ((event.ctrlKey || event.metaKey) && key !== "k")) return;
  const typing = event.target.matches("input, textarea, select, [contenteditable='true']");
  if ((key === "/" && !typing) || (key === "k" && (event.metaKey || event.ctrlKey))) {
    event.preventDefault();
    $("query").focus();
    $("query").select();
    return;
  }
  if (typing) return;
  const inList = Boolean(event.target.closest("#lead-list"));
  if (key === "j" || (inList && event.key === "ArrowDown")) {
    event.preventDefault();
    move(1);
  } else if (key === "k" || (inList && event.key === "ArrowUp")) {
    event.preventDefault();
    move(-1);
  } else if (DECISION_KEYS[key] && selected && !event.shiftKey) {
    const lead = scan.leads.find(item => item.id === selected);
    if (lead) {
      event.preventDefault();
      setDecision(lead, DECISION_KEYS[key]);
    }
  }
});

/* ---------- sources, stats, live scanning ---------- */

function renderSources() {
  for (const source of scan.sources) {
    const item = node("li");
    item.append(sourceLink(source.url, source.label));
    const count = {
      "GitHub releases": "repositories checked", "Founder footprint": "domains dated",
      "Company research (Impressum, § 5 DDG)": `companies researched${source.checked ? ` of ${source.checked} checked this scan` : ""}`,
    }[source.label] || (source.pages ? `listings from ${plural(source.pages, "roster page")}` : "listings fetched");
    const state = {fresh: "Fetched", partial: "Incomplete", failed: "Unavailable in this scan"}[source.state];
    const cached = source.cached ? ` · ${plural(source.cached, "repository", "repositories")} from the last successful fetch` : "";
    item.append(node("p", `muted state ${state ? source.state : "captured"}`, state ? `${state} · ${source.count} ${count}${cached}` : "Included in captured data"));
    $("source-list").append(item);
    if (["UnternehmerTUM", "BayStartUP", "GitHub releases"].includes(source.label)) {
      const option = node("option", "", source.label);
      option.value = source.label;
      $("source-filter").append(option);
    }
  }
  if (scan.cutoff || scan.errors.length) {
    $("source-warning").textContent = [
      scan.cutoff && `Retrospective view as of ${formatDate(scan.cutoff)}. Showing only dated traces published by then, from a later capture. Current company research is hidden.`,
      scan.errors.length && `Source issues in this scan. ${scan.errors.join(" · ")}`,
    ].filter(Boolean).join(" ");
    $("source-warning").hidden = false;
  }
  for (const lead of scan.leads) {
    const comparison = lead.review.comparison;
    if (!comparison) continue;
    const days = Math.round((Date.parse(comparison.baseline_date) - Date.parse(comparison.signal_date)) / 86400000);
    const note = node("p");
    note.append(`${lead.name} · ${days} days between `,
      sourceLink(comparison.signal_url, `competition nomination (${formatDate(comparison.signal_date)})`), " and ",
      sourceLink(comparison.baseline_url, `pre-seed coverage (${formatDate(comparison.baseline_date)})`), ".");
    $("historical-cases").append(note, node("p", "muted", "Dates compared retrospectively. FirstTrace did not measure a live discovery advantage."));
    $("historical").hidden = false;
  }
}

function renderStats() {
  const held = scan.leads.filter(lead => lead.hold).length;
  const researched = scan.leads.filter(lead => lead.web).length;
  const open = scan.leads.filter(lead => !lead.hold && windowOf(lead).zone === 1).length;
  const stats = [
    [scan.total, scan.cutoff ? "projects with dated traces" : "projects read"],
    [researched, "companies researched"],
    [open, "with an open window"],
    [held, "held aside with a reason"],
  ];
  $("stats").append(...stats.map(([value, label]) => {
    const item = node("div");
    item.append(node("dt", "", label), node("dd", "", String(value)));
    return item;
  }));
}

function setupScanning() {
  if (!scan.server) return;
  const control = $("run-scan");
  control.hidden = false;
  const label = $("run-scan-label");
  const banner = $("scan-banner");
  let polling = null;
  const reset = message => {
    control.disabled = false;
    control.classList.remove("busy");
    label.textContent = "Run live scan";
    banner.textContent = message;
    banner.hidden = false;
  };
  function busy(seconds) {
    control.disabled = true;
    control.classList.add("busy");
    label.textContent = `Scanning… ${Math.round(seconds || 0)}s`;
    banner.textContent = "Reading UnternehmerTUM, every BayStartUP roster, GitHub, company websites and legal notices. The page reloads when the scan is done (up to about a minute).";
    banner.hidden = false;
  }
  async function status() {
    const response = await fetch("/api/status", {cache: "no-store"});
    return response.json();
  }
  async function poll() {
    try {
      const current = await status();
      if (current.scanning) {
        busy(current.elapsed);
        return;
      }
      clearInterval(polling);
      polling = null;
      if (current.error) {
        reset(`Scan failed: ${current.error}. The previous results are still shown.`);
        return;
      }
      try { sessionStorage.setItem(SCANNED_KEY, JSON.stringify(current.last)); } catch { /* optional */ }
      location.reload();
    } catch {
      clearInterval(polling);
      polling = null;
      reset("The local desk is not reachable. Restart it with python3 scout.py --serve.");
    }
  }
  control.addEventListener("click", async () => {
    busy(0);
    try {
      const response = await fetch("/api/scan", {method: "POST", headers: {"X-FirstTrace": "scan"}});
      if (!response.ok && response.status !== 409) throw new Error(String(response.status));
    } catch {
      // poll() reports an unreachable desk.
    }
    polling = polling || setInterval(poll, 1000);
    poll();
  });
  status().then(current => {
    if (current.scanning) {
      busy(current.elapsed);
      polling = setInterval(poll, 1000);
    } else if (current.last && current.last.observed_at !== scan.observedAt) {
      banner.textContent = "A newer scan finished. ";
      banner.append(button("Reload", "text-button", () => location.reload()));
      banner.hidden = false;
    }
  }).catch(() => {});
  let result = null;
  try {
    result = JSON.parse(sessionStorage.getItem(SCANNED_KEY));
    sessionStorage.removeItem(SCANNED_KEY);
  } catch { /* optional */ }
  if (result) {
    const message = !result.has_baseline
      ? `Scan complete · ${result.scanned} projects read. Scan again later to see what changed.`
      : result.new_signals ? `Scan complete · ${plural(result.new_signals, "lead")} with new signals`
        : "Scan complete · no new signals since the previous scan";
    if (result.has_baseline && result.new_signals) view = "New signals";
    setTimeout(() => notify(message), 300);
  }
}

$("scan-mode").textContent = scan.cutoff ? `Retrospective · ${formatDate(scan.cutoff)}` : scan.mode;
$("scan-mode").classList.toggle("replay", scan.mode !== "Live scan");
$("scan-time").dateTime = scan.observedAt;
$("scan-time").textContent = `Observed ${formatDate(scan.observedAt)}, ${scan.observedAt.slice(11, 16)} UTC`;
$("scan-summary").textContent = `${plural(scan.total, "project")} ${scan.cutoff ? "with dated traces" : "read"} · ${scan.leads.length} surfaced · ranked by HTGF readiness`;
$("search-key").textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘K" : "/";
setupScanning();
renderStats();
renderSources();
showPresets();
renderQueue();
