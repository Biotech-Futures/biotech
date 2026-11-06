"use strict";

const state = {
  metadata: null,
  token: "",
  currentStatus: null,
  pollTimer: null,
  initialized: false,
  jobStateKnown: false,
  jobActive: false,
  formValid: false,
  statusLoading: false,
  scaleConfig: null,
  scaleLoading: false,
  scaleRequest: 0,
  scaleTimer: null,
  scaleSeed: "3888",
  mode: "manual",
};

const CONFIG_STORAGE_KEY = "biotech.localDbGui.config.v7";
const LEGACY_CONFIG_STORAGE_KEYS = [
  "biotech.localDbGui.config.v6",
  "biotech.localDbGui.config.v5",
  "biotech.localDbGui.config.v4",
  "biotech.localDbGui.config.v3",
  "biotech.localDbGui.config.v2",
];
const PRE_SCENARIO_CONFIG_STORAGE_KEY = "biotech.localDbGui.config.v2";

const elements = {
  form: document.querySelector("#config-form"),
  scaleForm: document.querySelector("#scale-form"),
  modeManual: document.querySelector("#mode-manual"),
  modeAuto: document.querySelector("#mode-auto"),
  countFields: document.querySelector("#count-fields"),
  scenario: document.querySelector("#scenario"),
  scenarioLabel: document.querySelector("#scenario-label"),
  scenarioHelp: document.querySelector("#scenario-help"),
  seed: document.querySelector("#seed"),
  asOf: document.querySelector("#as-of"),
  formError: document.querySelector("#form-error"),
  totalUsers: document.querySelector("#total-users"),
  rsvpCapacity: document.querySelector("#rsvp-capacity"),
  explicitRows: document.querySelector("#explicit-rows"),
  generateButton: document.querySelector("#generate-button"),
  resetDefaults: document.querySelector("#reset-defaults"),
  commandPreview: document.querySelector("#command-preview"),
  copyCommand: document.querySelector("#copy-command"),
  copyStatus: document.querySelector("#copy-status"),
  jobState: document.querySelector("#job-state"),
  jobMessages: document.querySelector("#job-messages"),
  jobError: document.querySelector("#job-error"),
  jobResult: document.querySelector("#job-result"),
  databaseStatus: document.querySelector("#database-status"),
  refreshStatus: document.querySelector("#refresh-status"),
  loadCurrent: document.querySelector("#load-current"),
  emailQuantities: document.querySelector("#email-quantity-fields"),
  emailMode: document.querySelector("#email-mode"),
  emailCustom: document.querySelector("#email-custom-fields"),
  emailBatchCard: document.querySelector("#custom-batch-card"),
  emailBatches: document.querySelector("#email-batches"),
  emailType: document.querySelector("#email-type"),
  emailStatus: document.querySelector("#email-status"),
  emailRecipients: document.querySelector("#email-recipients"),
  emailStart: document.querySelector("#email-start"),
  emailEnd: document.querySelector("#email-end"),
  emailSummary: document.querySelector("#email-summary"),
  emailRecipientHelp: document.querySelector("#email-recipient-help"),
  emailRecent: document.querySelector("#email-recent"),
  scaleStudents: document.querySelector("#scale-students"),
  scaleVariation: document.querySelector("#scale-variation"),
  scalePreview: document.querySelector("#scale-preview"),
  scaleStatus: document.querySelector("#scale-status"),
  scaleError: document.querySelector("#scale-error"),
  scaleGenerate: document.querySelector("#scale-generate"),
  scaleReroll: document.querySelector("#scale-reroll"),
};

const DATABASE_COUNT_FIELDS = [
  ["users", "Users"],
  ["role_assignments", "Role assignments"],
  ["student_profiles", "Student profiles"],
  ["mentor_profiles", "Mentor profiles"],
  ["supervisor_profiles", "Supervisor profiles"],
  ["admin_profiles", "Admin profiles"],
  ["admin_scopes", "Admin scopes"],
  ["student_supervisors", "Student-supervisor links"],
  ["mentor_availability", "Mentor availability"],
  ["user_interests", "User interests"],
  ["groups", "Groups"],
  ["memberships", "Memberships"],
  ["messages", "Messages"],
  ["login_events", "Login events"],
  ["tasks", "Tasks"],
  ["resources", "Resources"],
  ["resource_audiences", "Resource audiences"],
  ["resource_access_events", "Resource accesses"],
  ["announcements", "Announcements"],
  ["announcement_audiences", "Announcement audiences"],
  ["deliveries", "Delivery summaries"],
  ["email_metrics", "Email send batches"],
  ["email_recipients", "Email recipient outcomes"],
  ["email_markers", "Synthetic email ownership markers"],
  ["events", "Events"],
  ["rsvps", "RSVPs"],
  ["manifests", "Dataset manifests"],
];

function syncControls() {
  const unavailable = !state.initialized || !state.jobStateKnown;
  const formLocked = unavailable || state.jobActive;
  for (const input of document.querySelectorAll("#config-form input, #config-form select, #config-form button[type=button], #scale-form input, #scale-form button[type=button]")) {
    input.disabled = formLocked;
  }
  const custom = elements.emailMode.value === "custom";
  elements.emailCustom.hidden = !custom;
  elements.emailBatchCard.hidden = !custom;
  for (const input of elements.emailCustom.querySelectorAll("input, select, button")) {
    input.disabled = formLocked || !custom;
  }
  elements.emailBatches.disabled = formLocked || !custom;
  const presetInput = document.querySelector("#count-deliveries");
  if (presetInput) {
    presetInput.disabled = formLocked || custom;
    presetInput.closest("label").hidden = custom;
  }
  elements.generateButton.disabled = formLocked || !state.formValid;
  elements.resetDefaults.disabled = formLocked;
  elements.copyCommand.disabled = formLocked || (state.mode === "auto" ? state.scaleLoading || !state.scaleConfig : !state.formValid);
  elements.refreshStatus.disabled = unavailable || state.jobActive || state.statusLoading;
  elements.loadCurrent.disabled =
    formLocked || state.statusLoading || !state.currentStatus?.manifest?.config;
  elements.scaleGenerate.disabled = formLocked || state.scaleLoading || !state.scaleConfig;
  elements.scaleReroll.disabled = formLocked || state.scaleLoading;
  elements.modeManual.disabled = formLocked;
  elements.modeAuto.disabled = formLocked;
}

function setMode(mode) {
  if (state.jobActive || !["manual", "auto"].includes(mode)) return;
  state.mode = mode;
  elements.form.hidden = mode !== "manual";
  elements.scaleForm.hidden = mode !== "auto";
  elements.modeManual.setAttribute("aria-pressed", String(mode === "manual"));
  elements.modeAuto.setAttribute("aria-pressed", String(mode === "auto"));
  updateCommandPreview();
  syncControls();
}

function selectedModeConfig() {
  if (state.mode === "manual") return currentConfig();
  if (state.scaleLoading || !state.scaleConfig) throw new Error("Wait for a valid automatic preview before generating.");
  return state.scaleConfig;
}

function updateCommandPreview() {
  try {
    elements.commandPreview.textContent = commandFor(selectedModeConfig());
  } catch (error) {
    elements.commandPreview.textContent = `Fix the selected mode's configuration to preview its command.\n请先修正当前模式的配置，再查看等效命令。\n${bilingualError(error.message)}`;
  }
}

function scheduleScalePreview(reroll = false) {
  window.clearTimeout(state.scaleTimer);
  state.scaleRequest += 1;
  state.scaleConfig = null;
  state.scaleLoading = true;
  if (reroll) state.scaleSeed = String(crypto.getRandomValues(new Uint32Array(1))[0]);
  elements.scaleError.hidden = true;
  elements.scalePreview.replaceChildren();
  renderBilingual(elements.scaleStatus, "Inputs changed. Waiting to calculate a new preset…");
  updateCommandPreview();
  syncControls();
  const requestId = state.scaleRequest;
  state.scaleTimer = window.setTimeout(() => calculateScalePreview(requestId), 200);
}

async function calculateScalePreview(requestId) {
  if (requestId !== state.scaleRequest) return;
  try {
    const students = Number(elements.scaleStudents.value);
    const variation = Number(elements.scaleVariation.value);
    if (!elements.scaleStudents.value.trim() || !Number.isInteger(students) || students < 1 || students > 10000) {
      throw new Error("Target students must be a whole number from 1 to 10,000.");
    }
    if (!elements.scaleVariation.value.trim() || !Number.isFinite(variation) || variation < 0 || variation > 50) {
      throw new Error("Variation must be a number from 0 to 50.");
    }
    renderBilingual(elements.scaleStatus, "Calculating preset…");
    const result = await fetchJson("/api/scale-preview", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Local-DB-Token": state.token },
      body: JSON.stringify({ students, variation_percent: variation, seed: state.scaleSeed, as_of: new Date().toISOString() }),
    });
    if (requestId !== state.scaleRequest) return;
    validateRelationships(result.config);
    state.scaleConfig = result.config;
    const fragment = document.createDocumentFragment();
    for (const field of state.metadata.count_fields.filter(field => field.name !== "deliveries")) {
      const card = document.createElement("div");
      card.className = "summary-card";
      const label = document.createElement("span");
      renderBilingual(label, field.label);
      const count = document.createElement("strong");
      count.textContent = formatNumber(result.config[field.name]);
      card.append(label, count);
      fragment.append(card);
    }
    const mailCard = document.createElement("div");
    mailCard.className = "summary-card";
    const mailLabel = document.createElement("span");
    renderBilingual(mailLabel, "Email send batches");
    const mailCount = document.createElement("strong");
    mailCount.textContent = formatNumber(result.config.deliveries * 2);
    mailCard.append(mailLabel, mailCount);
    fragment.append(mailCard);
    elements.scalePreview.replaceChildren(fragment);
    const ratio = (students / 120).toLocaleString("en-AU", { maximumFractionDigits: 3 });
    elements.scaleStatus.textContent = `${formatNumber(students)} students · ${ratio}× baseline · ±${variation}% · seed ${state.scaleSeed}\n${formatNumber(students)} 名学生 · 基准规模的 ${ratio} 倍 · 随机浮动 ±${variation}% · 随机种子 ${state.scaleSeed}`;
  } catch (error) {
    if (requestId !== state.scaleRequest) return;
    state.scaleConfig = null;
    elements.scaleStatus.textContent = "";
    elements.scaleError.textContent = bilingualError(error.message);
    elements.scaleError.hidden = false;
  } finally {
    if (requestId === state.scaleRequest) {
      state.scaleLoading = false;
      updateCommandPreview();
      syncControls();
    }
  }
}

async function submitScaleGeneration(event) {
  event.preventDefault();
  if (state.mode !== "auto" || !state.scaleConfig || state.scaleLoading || state.jobActive || !state.jobStateKnown) return;
  // Reuse the displayed random quantities; only refresh the clock for today's demo.
  const config = { ...state.scaleConfig, as_of: new Date().toISOString() };
  state.scaleConfig = config;
  updateCommandPreview();
  await generateConfig(config, "auto");
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-AU").format(value);
}

function isoToDateTimeInput(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  const pad = (part) => String(part).padStart(2, "0");
  return [
    parsed.getUTCFullYear(),
    "-",
    pad(parsed.getUTCMonth() + 1),
    "-",
    pad(parsed.getUTCDate()),
    "T",
    pad(parsed.getUTCHours()),
    ":",
    pad(parsed.getUTCMinutes()),
    ":",
    pad(parsed.getUTCSeconds()),
  ].join("");
}

function dateTimeInputToIso(value) {
  const trimmed = value.trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(trimmed);
  if (!match) {
    throw new Error("Dataset clock must be a complete UTC date and time.");
  }
  const candidate = `${trimmed.length === 16 ? `${trimmed}:00` : trimmed}Z`;
  const parsed = new Date(candidate);
  const expected = match.slice(1).map((part) => Number(part || 0));
  const actual = [
    parsed.getUTCFullYear(),
    parsed.getUTCMonth() + 1,
    parsed.getUTCDate(),
    parsed.getUTCHours(),
    parsed.getUTCMinutes(),
    parsed.getUTCSeconds(),
  ];
  if (Number.isNaN(parsed.getTime()) || actual.some((part, index) => part !== expected[index])) {
    throw new Error("Dataset clock is not a valid UTC date and time.");
  }
  return candidate;
}

function createCountFields() {
  const fragment = document.createDocumentFragment();
  for (const field of state.metadata.count_fields) {
    const label = document.createElement("label");
    label.className = "field-card";
    label.htmlFor = `count-${field.name}`;

    const title = document.createElement("span");
    title.className = "field-label";
    renderBilingual(title, field.label);

    const input = document.createElement("input");
    input.id = `count-${field.name}`;
    input.name = field.name;
    input.type = "number";
    input.min = "0";
    input.max = String(state.metadata.count_limit);
    input.step = "1";
    input.required = true;
    input.inputMode = "numeric";
    input.disabled = true;

    const help = document.createElement("span");
    help.className = "field-help";
    renderBilingual(help, field.help);

    label.append(title, input, help);
    if (["announcements", "deliveries"].includes(field.name)) {
      elements.emailQuantities.insertBefore(label, elements.emailBatchCard);
    } else {
      fragment.append(label);
    }
  }
  elements.countFields.replaceChildren(fragment);
}

function createEmailOptions() {
  for (const [select, options] of [[elements.emailType, state.metadata.email_types], [elements.emailStatus, state.metadata.email_statuses]]) {
    select.replaceChildren(new Option(inlineBilingual("Mixed"), "mixed"), ...options.map(item => new Option(inlineBilingual(item.label), item.value)));
  }
}

function activeUserCapacity(config) {
  return config.admins + [config.students, config.mentors, config.supervisors].reduce((sum, count) =>
    sum + Math.floor(count / 8) * 4 + [1, 2, 3, 5].filter(position => count % 8 >= position).length, 0);
}

function emailNumberInputConfig() {
  return Object.fromEntries(["admins", "students", "mentors", "supervisors"].map(name =>
    [name, readWholeNumber(document.querySelector(`#count-${name}`), name)]));
}

function pickDifferent(values, current) {
  const alternatives = values.filter(value => String(value) !== String(current));
  const pool = alternatives.length ? alternatives : values;
  if (!pool.length) throw new Error("No valid random choice for this configuration.");
  const random = crypto.getRandomValues(new Uint32Array(1))[0] / 4294967296;
  return pool[Math.floor(random * pool.length)];
}

function randomizeEmail(field) {
  try {
    if (field === "type") {
      const hasAnnouncements = Number(document.querySelector("#count-announcements").value) > 0;
      const choices = state.metadata.email_types.map(item => item.value).filter(value => hasAnnouncements || value !== "announcement");
      elements.emailType.value = pickDifferent(choices, elements.emailType.value);
    } else if (field === "status") {
      const choices = state.metadata.email_statuses.map(item => item.value).filter(value => Number(elements.emailRecipients.value) >= 2 || value !== "partial");
      elements.emailStatus.value = pickDifferent(choices, elements.emailStatus.value);
    } else {
      const minimum = elements.emailStatus.value === "partial" ? 2 : 1;
      const batches = readWholeNumber(elements.emailBatches, "Email batches");
      const maximum = Math.min(activeUserCapacity(emailNumberInputConfig()), Math.floor(state.metadata.count_limit / Math.max(1, batches)));
      if (maximum < minimum) throw new Error("Increase the number of active users or reduce the batch count before randomizing recipients.");
      // Sample the interval without allocating an array proportional to user count.
      const current = Number(elements.emailRecipients.value);
      const exclude = current >= minimum && current <= maximum && Number.isInteger(current) && maximum > minimum;
      const size = maximum - minimum + 1 - Number(exclude);
      let chosen = minimum + Math.floor((crypto.getRandomValues(new Uint32Array(1))[0] / 4294967296) * size);
      if (exclude && chosen >= current) chosen += 1;
      elements.emailRecipients.value = String(chosen);
    }
    updateDerivedValues();
  } catch (error) {
    showFormError(error.message);
  }
}

function scenarioFieldMetadata() {
  return state.metadata.distribution_fields?.find((field) => field.name === "scenario");
}

function createScenarioOptions() {
  const field = scenarioFieldMetadata();
  if (!field || !Array.isArray(field.options) || !field.options.length) {
    throw new Error("The server did not provide any dataset scenarios.");
  }

  renderBilingual(elements.scenarioLabel, field.label || "Scenario");
  const fragment = document.createDocumentFragment();
  for (const item of field.options) {
    if (!item || typeof item.value !== "string" || typeof item.label !== "string") {
      throw new Error("The server provided invalid dataset scenario metadata.");
    }
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = inlineBilingual(item.label);
    fragment.append(option);
  }
  elements.scenario.replaceChildren(fragment);
  updateScenarioHelp();
}

function updateScenarioHelp() {
  const field = scenarioFieldMetadata();
  const selected = field?.options?.find((item) => item.value === elements.scenario.value);
  renderBilingual(elements.scenarioHelp, selected?.description || field?.help || "");
}

function applyConfig(config) {
  const selected = { ...state.metadata.defaults, ...config };
  for (const field of state.metadata.count_fields) {
    const input = document.querySelector(`#count-${field.name}`);
    input.value = String(selected[field.name]);
    input.setAttribute("aria-invalid", "false");
  }
  elements.scenario.value = String(selected.scenario);
  elements.seed.value = String(selected.seed);
  elements.asOf.value = isoToDateTimeInput(selected.as_of);
  elements.emailMode.value = selected.email_mode;
  elements.emailBatches.value = String(selected.email_batches);
  elements.emailType.value = selected.email_type;
  elements.emailStatus.value = selected.email_status;
  elements.emailRecipients.value = String(selected.email_recipients);
  const clock = new Date(selected.as_of).getTime();
  elements.emailStart.value = isoToDateTimeInput(selected.email_start || clock - 23 * 3600000);
  elements.emailEnd.value = isoToDateTimeInput(selected.email_end || clock - 5 * 60000);
  elements.scenario.setAttribute("aria-invalid", "false");
  elements.seed.setAttribute("aria-invalid", "false");
  elements.asOf.setAttribute("aria-invalid", "false");
  updateScenarioHelp();
  clearFormError();
  updateDerivedValues();
}

function readWholeNumber(input, label) {
  const value = Number(input.value);
  const valid =
    input.value.trim() !== "" &&
    Number.isInteger(value) &&
    value >= 0 &&
    value <= state.metadata.count_limit;
  input.setAttribute("aria-invalid", valid ? "false" : "true");
  if (!valid) {
    throw new Error(`${label} must be a whole number from 0 to ${formatNumber(state.metadata.count_limit)}.`);
  }
  return value;
}

function readSeed() {
  const value = elements.seed.value.trim();
  const valid = /^-?(0|[1-9]\d*)$/.test(value) && value.length <= 200;
  elements.seed.setAttribute("aria-invalid", valid ? "false" : "true");
  if (!valid) {
    throw new Error("Random seed must be a whole decimal number.");
  }
  return value;
}

function readScenario() {
  const value = elements.scenario.value;
  const valid = scenarioFieldMetadata()?.options?.some((item) => item.value === value) === true;
  elements.scenario.setAttribute("aria-invalid", valid ? "false" : "true");
  if (!valid) {
    throw new Error("Select one of the dataset scenarios supplied by the server.");
  }
  return value;
}

function readConfig() {
  const config = {};
  for (const field of state.metadata.count_fields) {
    const input = document.querySelector(`#count-${field.name}`);
    config[field.name] = readWholeNumber(input, field.label);
  }
  config.scenario = readScenario();
  config.seed = readSeed();
  config.email_mode = elements.emailMode.value;
  config.email_batches = readWholeNumber(elements.emailBatches, "Email batches");
  config.email_type = elements.emailType.value;
  config.email_status = elements.emailStatus.value;
  config.email_recipients = readWholeNumber(elements.emailRecipients, "Email recipients");
  config.email_start = config.email_mode === "custom" ? dateTimeInputToIso(elements.emailStart.value) : "";
  config.email_end = config.email_mode === "custom" ? dateTimeInputToIso(elements.emailEnd.value) : "";
  try {
    config.as_of = dateTimeInputToIso(elements.asOf.value);
    elements.asOf.setAttribute("aria-invalid", "false");
  } catch (error) {
    elements.asOf.setAttribute("aria-invalid", "true");
    throw error;
  }
  return config;
}

function validateRelationships(config) {
  const totalUsers = config.admins + config.supervisors + config.mentors + config.students;
  const participantUsers = config.supervisors + config.mentors + config.students;
  const custom = config.email_mode === "custom";
  const needsAnnouncements = custom ? config.email_batches && ["announcement", "mixed"].includes(config.email_type) : config.deliveries;
  if (config.messages && (!config.groups || !participantUsers)) {
    throw new Error("Messages require at least one group and one participant user.");
  }
  if (config.login_events && !totalUsers) {
    throw new Error("Login events require at least one user.");
  }
  if ((config.resources || config.announcements || (custom ? config.email_batches : config.deliveries)) && !config.admins) {
    throw new Error("Resources, announcements, and deliveries require at least one admin.");
  }
  if (config.resource_accesses && (!config.resources || !totalUsers)) {
    throw new Error("Resource accesses require at least one resource and one user.");
  }
  if (needsAnnouncements && !config.announcements) {
    throw new Error("Announcement email batches require at least one announcement. Choose a system email type to generate without announcements.");
  }
  if (custom && config.email_batches) {
    if (config.email_recipients < 1 || config.email_recipients > activeUserCapacity(config)) {
      throw new Error(`Recipients per batch must be between 1 and ${activeUserCapacity(config)} active synthetic users.`);
    }
    if (config.email_status === "partial" && config.email_recipients < 2) {
      throw new Error("Partially delivered requires at least 2 recipients.");
    }
    if (config.email_batches * config.email_recipients > state.metadata.count_limit) {
      throw new Error("Email batches × recipients exceeds the 2,000,000-row safety limit.");
    }
    const start = new Date(config.email_start).getTime();
    const end = new Date(config.email_end).getTime();
    if (end - start < (config.email_batches - 1) * 1000) {
      throw new Error("The last batch must be at or after the first, with at least 1 second between batches.");
    }
    if (end + 20000 > new Date(config.as_of).getTime()) {
      throw new Error("The last batch must be at least 20 seconds before the dataset clock. Use recent 24 hours to reset these dates.");
    }
  }
  if (config.tasks && !config.groups && !totalUsers) {
    throw new Error("Tasks require at least one group or one user.");
  }
  if (config.rsvps && (!config.events || !totalUsers)) {
    throw new Error("RSVPs require at least one event and one user.");
  }
  if (config.rsvps > config.events * totalUsers) {
    throw new Error("RSVPs cannot exceed the number of unique event and user pairs.");
  }
}

function currentConfig() {
  const config = readConfig();
  validateRelationships(config);
  return config;
}

function commandFor(config) {
  const lines = ["./tools/local_db/run bootstrap \\"];
  state.metadata.count_fields.forEach((field) => {
    lines.push(`  --${field.name.replaceAll("_", "-")} ${config[field.name]} \\`);
  });
  lines.push(`  --scenario ${config.scenario} \\`);
  lines.push(`  --seed ${config.seed} \\`);
  for (const field of ["email_mode", "email_batches", "email_type", "email_status", "email_recipients", "email_start", "email_end"]) {
    if (config[field] !== "") lines.push(`  --${field.replaceAll("_", "-")} ${config[field]} \\`);
  }
  lines.push(`  --as-of ${config.as_of}`);
  return lines.join("\n");
}

function showFormError(message) {
  elements.formError.textContent = bilingualError(message);
  elements.formError.hidden = false;
}

function clearFormError() {
  elements.formError.textContent = "";
  elements.formError.hidden = true;
}

function updateDerivedValues() {
  try {
    const config = readConfig();
    validateRelationships(config);
    const totalUsers = config.admins + config.supervisors + config.mentors + config.students;
    const explicitRows = state.metadata.count_fields.reduce(
      (total, field) => total + (config.email_mode === "custom" && field.name === "deliveries" ? 0 : config[field.name]),
      0,
    ) + (config.email_mode === "custom" ? config.email_batches : 0);
    const capacity = activeUserCapacity(config);
    elements.emailRecipients.max = String(capacity);
    elements.emailRecipientHelp.textContent = `1–${capacity} distinct active synthetic users per batch. Increase the user counts above to raise this limit.\n每批可选择 1–${capacity} 个不同的活跃账号；不同批次可以重复使用同一账号。增加上方用户数量可提高上限。`;
    const englishSummary = config.email_mode === "custom"
      ? `${config.announcements} announcements · ${config.email_batches} total email batches · ${formatNumber(config.email_batches * config.email_recipients)} recipient outcomes. ${config.email_type === "mixed" ? "Types rotate across all nine categories." : "Every batch uses the selected type."} ${config.email_status === "mixed" && config.email_recipients === 1 ? "With one recipient, Mixed uses delivered and failed only." : ""}`
      : `${config.announcements} announcements · ${config.deliveries} announcement batches + ${config.deliveries} system batches = ${config.deliveries * 2} total email batches. Types, outcomes, recipients and dates follow the Analytics preset.`;
    const chineseSummary = config.email_mode === "custom"
      ? `${config.announcements} 条公告 · ${config.email_batches} 批邮件 · ${formatNumber(config.email_batches * config.email_recipients)} 条收件人结果。${config.email_type === "mixed" ? "邮件类型在九类之间轮换。" : "所有批次使用选定的邮件类型。"}${config.email_status === "mixed" && config.email_recipients === 1 ? "每批只有 1 人时，混合结果仅包含全部成功和全部失败。" : ""}`
      : `${config.announcements} 条公告 · ${config.deliveries} 批公告邮件＋${config.deliveries} 批系统邮件＝${config.deliveries * 2} 批。类型、结果、人数和日期按统计演示预设生成。`;
    elements.emailSummary.textContent = englishSummary + "\n" + chineseSummary;
    elements.totalUsers.textContent = formatNumber(totalUsers);
    elements.rsvpCapacity.textContent = formatNumber(config.events * totalUsers);
    elements.explicitRows.textContent = formatNumber(explicitRows);
    state.formValid = true;
    clearFormError();
  } catch (error) {
    elements.totalUsers.textContent = "—";
    elements.rsvpCapacity.textContent = "—";
    elements.explicitRows.textContent = "—";
    state.formValid = false;
    showFormError(error.message);
  }
  updateCommandPreview();
  syncControls();
}

async function fetchJson(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    credentials: "same-origin",
    ...options,
  });
  let body = null;
  try {
    body = await response.json();
  } catch (_error) {
    body = null;
  }
  if (!response.ok) {
    throw new Error(body?.error || `Request failed with HTTP ${response.status}.`);
  }
  return body;
}

function setJobActive(active) {
  state.jobActive = active;
  renderBilingual(elements.generateButton, active ? "Generating…" : "Generate manual data");
  renderBilingual(elements.scaleGenerate, active ? "Generating…" : "Generate automatic data");
  syncControls();
}

function renderJob(job) {
  const jobState = job.state || "idle";
  state.jobStateKnown = true;
  renderBilingual(elements.jobState, jobState);
  elements.jobState.className = `state-pill state-${jobState}`;
  setJobActive(jobState === "queued" || jobState === "running");

  const messages = Array.isArray(job.messages) && job.messages.length
    ? job.messages
    : ["No generation job has been submitted in this GUI session."];
  const fragment = document.createDocumentFragment();
  for (const message of messages) {
    const item = document.createElement("li");
    renderBilingual(item, String(message));
    fragment.append(item);
  }
  elements.jobMessages.replaceChildren(fragment);

  if (job.error) {
    elements.jobError.textContent = bilingualError(job.error);
    elements.jobError.hidden = false;
  } else {
    elements.jobError.textContent = "";
    elements.jobError.hidden = true;
  }

  if (job.result) {
    elements.jobResult.textContent = JSON.stringify(job.result, null, 2);
    elements.jobResult.hidden = false;
  } else {
    elements.jobResult.textContent = "";
    elements.jobResult.hidden = true;
  }
}

async function pollJob() {
  window.clearTimeout(state.pollTimer);
  try {
    const job = await fetchJson("/api/job");
    renderJob(job);
    if (job.state === "queued" || job.state === "running") {
      state.pollTimer = window.setTimeout(pollJob, 700);
    } else if (job.state === "succeeded") {
      await refreshDatabaseStatus();
    }
  } catch (error) {
    state.jobStateKnown = false;
    elements.jobError.textContent = `Could not refresh generation status; retrying…\n暂时无法刷新生成进度，正在重试。\n${bilingualError(error.message)}`;
    elements.jobError.hidden = false;
    syncControls();
    state.pollTimer = window.setTimeout(pollJob, 1500);
  }
}

function databaseItem(label, value, extraClass = "") {
  const item = document.createElement("div");
  item.className = `database-item ${extraClass}`.trim();
  const title = document.createElement("span");
  renderBilingual(title, label);
  const content = document.createElement("strong");
  content.textContent = value;
  content.title = value;
  item.append(title, content);
  return item;
}

function databaseCountValue(counts, name) {
  const value = counts[name];
  return Number.isSafeInteger(value) && value >= 0 ? formatNumber(value) : "—";
}

function databaseCountLabel(name) {
  return name
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function scenarioDisplayName(value) {
  if (!value) return "—";
  const option = scenarioFieldMetadata()?.options?.find((item) => item.value === value);
  return inlineBilingual(option?.label || String(value));
}

function renderDatabaseStatus(payload) {
  state.currentStatus = payload;
  const wrapper = document.createElement("div");
  wrapper.className = "database-grid";
  const manifest = payload.manifest || null;
  const counts = payload.counts && typeof payload.counts === "object" ? payload.counts : {};
  wrapper.append(
    databaseItem("Dataset", payload.dataset_present ? manifest?.dataset || inlineBilingual("Detected") : inlineBilingual("Not generated")),
    databaseItem("Version", manifest?.version ? String(manifest.version) : "—"),
    databaseItem("Scenario", scenarioDisplayName(manifest?.config?.scenario)),
    databaseItem("Fingerprint", manifest?.fingerprint || "—"),
  );
  const displayedCounts = new Set();
  for (const [name, label] of DATABASE_COUNT_FIELDS) {
    wrapper.append(databaseItem(label, databaseCountValue(counts, name)));
    displayedCounts.add(name);
  }
  for (const name of Object.keys(counts).filter((key) => !displayedCounts.has(key)).sort()) {
    wrapper.append(databaseItem(databaseCountLabel(name), databaseCountValue(counts, name)));
  }
  wrapper.append(databaseItem("Target", payload.target || inlineBilingual("Unavailable"), "database-target"));
  if (payload.manifest_error) {
    wrapper.append(databaseItem("Manifest warning", payload.manifest_error, "database-target"));
  }
  elements.databaseStatus.replaceChildren(wrapper);
  syncControls();
}

async function refreshDatabaseStatus() {
  state.statusLoading = true;
  syncControls();
  renderBilingual(elements.databaseStatus, "Checking the local database…");
  try {
    renderDatabaseStatus(await fetchJson("/api/status"));
  } catch (error) {
    state.currentStatus = null;
    elements.databaseStatus.textContent = `Status unavailable.\n暂时无法读取数据库状态。\n${bilingualError(error.message)}`;
  } finally {
    state.statusLoading = false;
    syncControls();
  }
}

async function submitGeneration(event) {
  event.preventDefault();
  if (state.mode !== "manual" || state.jobActive || !state.jobStateKnown || !state.initialized) return;
  clearFormError();
  try {
    await generateConfig(currentConfig(), "manual");
  } catch (error) {
    showFormError(error.message);
  }
}

async function generateConfig(config, mode) {
  if (state.jobActive || !state.jobStateKnown || !state.initialized || state.mode !== mode) return;
  const showError = (message) => {
    if (mode === "auto") {
      elements.scaleError.textContent = bilingualError(message);
      elements.scaleError.hidden = false;
    } else {
      showFormError(message);
    }
  };
  if (mode === "auto") elements.scaleError.hidden = true;
  try {
    validateRelationships(config);
  } catch (error) {
    showError(error.message);
    return;
  }
  const explicitRows = state.metadata.count_fields.reduce(
    (total, field) => total + (config.email_mode === "custom" && field.name === "deliveries" ? 0 : config[field.name]),
    0,
  ) + (config.email_mode === "custom" ? config.email_batches : 0);
  const modeEnglish = mode === "auto" ? "Automatic" : "Manual";
  const modeChinese = mode === "auto" ? "自动" : "手动";
  const confirmed = window.confirm(
    `Mode: ${modeEnglish} · ${formatNumber(config.students)} students\n模式：${modeChinese} · ${formatNumber(config.students)} 名学生\n\nClear ALL existing data in this local demo database and rebuild approximately ${formatNumber(explicitRows)} explicit rows? Other databases are not changed.\n\n确认清空当前演示库的全部数据，并重新生成约 ${formatNumber(explicitRows)} 条基础记录？其他数据库不会改变。\n\n${state.currentStatus?.target || "Current local demo database / 当前本地演示库"}`,
  );
  if (!confirmed) return;

  setJobActive(true);
  try {
    const job = await fetchJson("/api/bootstrap", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Local-DB-Token": state.token,
      },
      body: JSON.stringify({ config, confirm_replace: true }),
    });
    if (mode === "manual") rememberConfig(config);
    renderJob(job);
    elements.jobState.scrollIntoView({ behavior: "smooth", block: "center" });
    await pollJob();
  } catch (error) {
    showError(error.message);
    state.jobStateKnown = false;
    syncControls();
    await pollJob();
  }
}

async function copyCommand() {
  try {
    const config = selectedModeConfig();
    await navigator.clipboard.writeText(commandFor(config));
    renderBilingual(elements.copyStatus, "Command copied.");
  } catch (error) {
    elements.copyStatus.textContent = `Could not copy: ${error.message}\n复制失败，请手动选择命令文本。`;
  }
  window.setTimeout(() => {
    elements.copyStatus.textContent = "";
  }, 2500);
}

function loadStoredOrDefault() {
  let selected = { ...state.metadata.defaults };
  const storageKeys = [CONFIG_STORAGE_KEY, ...LEGACY_CONFIG_STORAGE_KEYS];
  for (const storageKey of storageKeys) {
    const raw = window.localStorage.getItem(storageKey);
    if (raw === null) continue;
    try {
      const stored = JSON.parse(raw);
      if (!stored || typeof stored !== "object" || Array.isArray(stored)) {
        throw new Error("Stored GUI configuration is not an object.");
      }
      const migrated = { ...stored };
      if (storageKey === PRE_SCENARIO_CONFIG_STORAGE_KEY) delete migrated.scenario;
      // Remember size/preferences, but start a new session with a fresh clock.
      // "Load its config" still restores an exact historical snapshot.
      if (migrated.email_mode !== "custom") delete migrated.as_of;
      selected = { ...selected, ...migrated };
      window.localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(selected));
      for (const legacyKey of LEGACY_CONFIG_STORAGE_KEYS) {
        window.localStorage.removeItem(legacyKey);
      }
      break;
    } catch (_error) {
      window.localStorage.removeItem(storageKey);
    }
  }
  applyConfig(selected);
}

function rememberConfig(config) {
  // A browser storage failure must never interrupt an accepted generation job.
  try {
    const selected = { ...state.metadata.defaults, ...config };
    window.localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(selected));
    for (const legacyKey of LEGACY_CONFIG_STORAGE_KEYS) window.localStorage.removeItem(legacyKey);
  } catch (_error) {
    // The database manifest remains available through Load its config.
  }
}

function clearStoredConfig() {
  try {
    window.localStorage.removeItem(CONFIG_STORAGE_KEY);
    for (const legacyKey of LEGACY_CONFIG_STORAGE_KEYS) window.localStorage.removeItem(legacyKey);
  } catch (_error) {
    // Restoring form defaults remains usable without browser storage.
  }
}

async function initialize() {
  try {
    state.metadata = await fetchJson("/api/config");
    state.token = state.metadata.csrf_token;
    createCountFields();
    createScenarioOptions();
    createEmailOptions();
    try { loadStoredOrDefault(); } catch (_error) { applyConfig(state.metadata.defaults); }
    state.scaleSeed = String(crypto.getRandomValues(new Uint32Array(1))[0]);
    elements.scaleStudents.addEventListener("input", () => scheduleScalePreview());
    elements.scaleVariation.addEventListener("input", () => scheduleScalePreview());
    elements.scaleReroll.addEventListener("click", () => scheduleScalePreview(true));
    elements.scaleForm.addEventListener("submit", submitScaleGeneration);
    elements.modeManual.addEventListener("click", () => setMode("manual"));
    elements.modeAuto.addEventListener("click", () => setMode("auto"));
    elements.form.addEventListener("input", updateDerivedValues);
    elements.form.addEventListener("change", updateDerivedValues);
    for (const field of ["type", "status", "recipients"]) {
      document.querySelector(`#random-email-${field}`).addEventListener("click", () => randomizeEmail(field));
    }
    elements.emailRecent.addEventListener("click", () => {
      const clock = Date.now();
      elements.asOf.value = isoToDateTimeInput(clock);
      elements.emailStart.value = isoToDateTimeInput(clock - 23 * 3600000);
      elements.emailEnd.value = isoToDateTimeInput(clock - 5 * 60000);
      updateDerivedValues();
    });
    elements.scenario.addEventListener("change", updateScenarioHelp);
    elements.form.addEventListener("submit", submitGeneration);
    elements.resetDefaults.addEventListener("click", () => {
      clearStoredConfig();
      applyConfig(state.metadata.defaults);
    });
    elements.copyCommand.addEventListener("click", copyCommand);
    elements.refreshStatus.addEventListener("click", refreshDatabaseStatus);
    elements.loadCurrent.addEventListener("click", () => {
      const config = state.currentStatus?.manifest?.config;
      if (config) {
        setMode("manual");
        rememberConfig(config);
        applyConfig(config);
      }
    });
    state.initialized = true;
    syncControls();
    scheduleScalePreview();
    await Promise.all([refreshDatabaseStatus(), pollJob()]);
  } catch (error) {
    state.initialized = false;
    state.jobStateKnown = false;
    showFormError(`GUI initialization failed: ${error.message}`);
    syncControls();
  }
}

translateStaticPage();
syncControls();
initialize();
