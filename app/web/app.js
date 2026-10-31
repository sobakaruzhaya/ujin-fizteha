(() => {
  "use strict";

  const DEFAULT_DEVICE = "smart_plug_1";
  const SIGNAL_LABELS = {
    power_switch: "Реле",
    power_w: "Мощность",
    energy_kwh: "Энергия",
    voltage: "Напряжение",
    current_a: "Ток",
    load_w: "Нагрузка",
    power_limit_w: "Лимит",
    auto_off_seconds: "Авто-выкл",
    overload_alarm: "Защита",
    anomaly: "Аномалия",
    reset_protection: "Сброс защиты",
  };
  const EVENT_LABELS = {
    alarm: "Авария",
    state_change: "Состояние",
    scenario_triggered: "Сценарий",
    scenario_saved: "Сценарий сохранён",
    scenario_toggled: "Сценарий переключён",
    command: "Команда",
    demo_started: "Демо",
    reset: "Сброс",
    log: "Лог",
  };

  const elements = {
    body: document.body,
    connection: document.getElementById("connection"),
    connectionText: document.getElementById("connection-text"),
    modeLabel: document.getElementById("mode-label"),
    onlineDot: document.getElementById("online-dot"),
    updated: document.getElementById("updated"),
    alarm: document.getElementById("alarm"),
    alarmText: document.getElementById("alarm-text"),
    power: document.getElementById("power-w"),
    relay: document.getElementById("relay-state"),
    energy: document.getElementById("energy-kwh"),
    limit: document.getElementById("limit-w"),
    protection: document.getElementById("protection"),
    voltageCurrent: document.getElementById("voltage-current"),
    chainSignal: document.getElementById("chain-signal"),
    chainRule: document.getElementById("chain-rule"),
    chainAction: document.getElementById("chain-action"),
    limitInput: document.getElementById("limit-input"),
    events: document.getElementById("events"),
    eventsCount: document.getElementById("events-count"),
    scenarios: document.getElementById("scenarios"),
    scenariosCount: document.getElementById("scenarios-count"),
    confirm: document.getElementById("confirm"),
    confirmSummary: document.getElementById("confirm-summary"),
    confirmOk: document.getElementById("confirm-ok"),
    confirmCancel: document.getElementById("confirm-cancel"),
    toast: document.getElementById("toast"),
  };

  let config = {
    device_id: DEFAULT_DEVICE,
    poll_interval_ms: 1000,
    confirmation_ttl_seconds: 60,
  };
  let refreshing = false;
  let wasOnline = null;
  let confirmResolve = null;
  let toastTimer = null;

  function applyMode() {
    const params = new URLSearchParams(window.location.search);
    const mode = params.get("mode") === "tv" ? "tv" : "phone";
    elements.body.dataset.mode = mode;
    elements.modeLabel.textContent = mode === "tv" ? "Режим телевизора" : "Режим телефона";
  }

  function setConnection(online, message) {
    elements.connection.classList.toggle("online", online);
    elements.connection.classList.toggle("offline", !online);
    elements.onlineDot.classList.toggle("online", online);
    elements.onlineDot.classList.toggle("offline", !online);
    elements.connectionText.textContent = message;
    if (wasOnline === true && online === false) {
      showToast("Связь с control plane потеряна", "error");
    }
    wasOnline = online;
  }

  function showToast(message, kind) {
    elements.toast.textContent = message;
    elements.toast.className = "toast" + (kind ? " " + kind : "");
    elements.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      elements.toast.hidden = true;
    }, 4200);
  }

  async function fetchJson(path, options) {
    const response = await fetch(path, options);
    let data = {};
    try {
      data = await response.json();
    } catch (error) {
      data = {};
    }
    if (!response.ok) {
      throw new Error(data.error || "HTTP " + response.status);
    }
    return data;
  }

  function formatNumber(value, digits) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
      return "0";
    }
    return digits === 0 ? String(Math.round(number)) : number.toFixed(digits);
  }

  function formatTime(timestamp) {
    const date = new Date(Number(timestamp) * 1000);
    if (Number.isNaN(date.getTime())) {
      return "—";
    }
    return date.toLocaleTimeString("ru-RU", { hour12: false });
  }

  function signalLabel(signal) {
    return SIGNAL_LABELS[signal] || signal || "сигнал";
  }

  function valueLabel(signal, value) {
    if (signal === "power_switch") {
      return Number(value) ? "включено" : "выключено";
    }
    if (signal === "overload_alarm" || signal === "anomaly") {
      return Number(value) ? "сработала" : "нет";
    }
    return String(value ?? "—");
  }

  function renderState(state) {
    const device = state && state.devices && state.devices[DEFAULT_DEVICE];
    if (!device) {
      throw new Error("Backend не вернул состояние smart_plug_1");
    }
    const power = Number(device.power_w) || 0;
    const limit = Number(device.power_limit_w) || 0;
    const relayOn = Number(device.power_switch) === 1;
    const alarm = Number(device.overload_alarm) === 1;
    const anomaly = Number(device.anomaly) === 1;

    elements.power.textContent = formatNumber(power, power % 1 === 0 ? 0 : 1);
    elements.energy.innerHTML = "";
    elements.energy.append(formatNumber(device.energy_kwh, 3) + " ");
    const energyUnit = document.createElement("small");
    energyUnit.textContent = "кВт·ч";
    elements.energy.append(energyUnit);
    elements.limit.innerHTML = "";
    elements.limit.append(formatNumber(limit, 0) + " ");
    const limitUnit = document.createElement("small");
    limitUnit.textContent = "Вт";
    elements.limit.append(limitUnit);

    elements.relay.textContent = relayOn ? "ВКЛ" : "ВЫКЛ";
    elements.relay.className = "pill " + (relayOn ? "on" : "off");

    elements.protection.textContent = alarm ? "Сработала" : anomaly ? "Аномалия" : "Нет";
    elements.protection.className = "value " + (alarm || anomaly ? "bad" : "good");

    elements.voltageCurrent.textContent =
      formatNumber(device.voltage, 0) + " В / " + formatNumber(device.current_a, 2) + " А";

    elements.alarm.hidden = !(alarm || anomaly);
    if (alarm) {
      elements.alarmText.textContent =
        "Сработала защита: нагрузка превысила лимит. Уменьшите нагрузку и сбросьте защиту.";
    } else if (anomaly) {
      elements.alarmText.textContent =
        "Обнаружена аномалия питания. Проверьте подключённые устройства и сбросьте защиту.";
    }

    if (document.activeElement !== elements.limitInput) {
      elements.limitInput.value = String(Math.round(limit));
    }

    elements.chainSignal.textContent = "Мощность " + formatNumber(power, 0) + " Вт";
    elements.chainRule.textContent = "Лимит " + formatNumber(limit, 0) + " Вт";
    if (alarm) {
      elements.chainAction.textContent = "Реле выключено защитой";
    } else {
      elements.chainAction.textContent = relayOn ? "Реле включено" : "Реле выключено";
    }

    elements.updated.textContent = "Обновлено " + formatTime(state.updated_at || Date.now() / 1000);
  }

  function renderEvents(events) {
    const list = Array.isArray(events) ? events : [];
    elements.eventsCount.textContent = String(list.length);
    elements.events.innerHTML = "";
    if (!list.length) {
      const empty = document.createElement("li");
      empty.className = "muted";
      empty.textContent = "Нет событий";
      elements.events.append(empty);
      return;
    }
    list.slice(-20).reverse().forEach((event) => {
      const item = document.createElement("li");
      if (event.type === "alarm") {
        item.classList.add("alarm");
      }
      const time = document.createElement("time");
      time.dateTime = new Date(Number(event.time) * 1000).toISOString();
      time.textContent = formatTime(event.time);
      const body = document.createElement("div");
      const type = document.createElement("div");
      type.className = "event-type";
      type.textContent = EVENT_LABELS[event.type] || event.type || "событие";
      const message = document.createElement("div");
      message.textContent = event.message ||
        [signalLabel(event.signal), event.value !== undefined ? valueLabel(event.signal, event.value) : ""]
          .filter(Boolean)
          .join(": ") || event.device || "";
      body.append(type, message);
      item.append(time, body);
      elements.events.append(item);
    });
  }

  function renderScenarios(scenarios) {
    const list = Array.isArray(scenarios) ? scenarios : [];
    elements.scenariosCount.textContent = String(list.length);
    elements.scenarios.innerHTML = "";
    if (!list.length) {
      const empty = document.createElement("li");
      empty.className = "muted";
      empty.textContent = "Сценарии не настроены";
      elements.scenarios.append(empty);
      return;
    }
    list.forEach((scenario) => {
      const item = document.createElement("li");
      const title = document.createElement("div");
      title.className = "scenario-title";
      const name = document.createElement("span");
      name.textContent = scenario.name || scenario.id || "Сценарий";
      const badge = document.createElement("span");
      badge.className = "badge" + (scenario.enabled ? "" : " off");
      badge.textContent = scenario.enabled ? "ВКЛ" : "ВЫКЛ";
      title.append(name, badge);

      const when = scenario.when || {};
      const action = (scenario.do && scenario.do[0]) || {};
      const rule = document.createElement("div");
      rule.className = "scenario-rule";
      rule.textContent =
        signalLabel(when.signal) + " " + (when.operator || "==") + " " + (when.value ?? "—") +
        " → " + signalLabel(action.signal) + " = " + valueLabel(action.signal, action.value);

      item.append(title, rule);
      elements.scenarios.append(item);
    });
  }

  async function refresh() {
    if (refreshing) {
      return;
    }
    refreshing = true;
    try {
      const results = await Promise.allSettled([
        fetchJson("/api/state"),
        fetchJson("/api/events"),
        fetchJson("/api/scenarios"),
      ]);
      const [stateResult, eventsResult, scenariosResult] = results;
      if (stateResult.status !== "fulfilled") {
        throw stateResult.reason;
      }
      renderState(stateResult.value);
      if (eventsResult.status === "fulfilled") {
        renderEvents(eventsResult.value);
      }
      if (scenariosResult.status === "fulfilled") {
        renderScenarios(scenariosResult.value);
      }
      setConnection(true, "Онлайн: control plane доступен");
    } catch (error) {
      setConnection(false, "Нет связи с control plane. Проверьте backend и Wi-Fi.");
    } finally {
      refreshing = false;
    }
  }

  function askConfirmation(summary) {
    return new Promise((resolve) => {
      confirmResolve = resolve;
      elements.confirmSummary.textContent = summary || "Команда изменит состояние розетки.";
      elements.confirm.hidden = false;
      elements.confirmOk.focus();
    });
  }

  function closeConfirmation(result) {
    elements.confirm.hidden = true;
    const resolve = confirmResolve;
    confirmResolve = null;
    if (resolve) {
      resolve(result);
    }
  }

  async function runCommand(signal, value, summary) {
    try {
      const preview = await fetchJson("/api/commands/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device: config.device_id || DEFAULT_DEVICE, signal: signal, value: value }),
      });
      if (preview.status === "confirmation_required") {
        const confirmed = await askConfirmation(preview.summary || summary);
        if (!confirmed) {
          return;
        }
        try {
          await fetchJson(
            "/api/commands/" + encodeURIComponent(preview.confirmation_id) + "/confirm",
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: "{}",
            }
          );
          showToast("Команда выполнена", "ok");
        } catch (error) {
          if (/expired|истек/i.test(error.message)) {
            showToast("Подтверждение истекло. Запросите команду заново.", "error");
            return;
          }
          throw error;
        }
      } else {
        showToast("Команда выполнена", "ok");
      }
      await refresh();
    } catch (error) {
      showToast(error.message || "Не удалось выполнить команду", "error");
    }
  }

  async function postDemo(path, message) {
    try {
      await fetchJson(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      showToast(message, "ok");
      await refresh();
    } catch (error) {
      showToast(error.message || "Не удалось выполнить действие", "error");
    }
  }

  function applyLimit() {
    const value = Number(elements.limitInput.value);
    if (!Number.isFinite(value) || value < 100 || value > 3500) {
      showToast("Лимит должен быть от 100 до 3500 Вт", "error");
      elements.limitInput.focus();
      return;
    }
    runCommand("power_limit_w", value, "Изменить лимит мощности на " + Math.round(value) + " Вт?");
  }

  function bindActions() {
    document.getElementById("power-on").addEventListener("click", () =>
      runCommand("power_switch", 1, "Включить реле розетки?"));
    document.getElementById("power-off").addEventListener("click", () =>
      runCommand("power_switch", 0, "Выключить реле розетки?"));
    document.getElementById("reset-protection").addEventListener("click", () =>
      runCommand("reset_protection", 1, "Сбросить защиту и разрешить включение реле?"));
    document.getElementById("demo-start").addEventListener("click", () =>
      postDemo("/api/demo/start", "Демонстрация перегрузки запущена"));
    document.getElementById("demo-reset").addEventListener("click", () =>
      postDemo("/api/demo/reset", "Демо сброшено"));
    document.getElementById("apply-limit").addEventListener("click", applyLimit);
    elements.limitInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        applyLimit();
      }
    });
    elements.confirmOk.addEventListener("click", () => closeConfirmation(true));
    elements.confirmCancel.addEventListener("click", () => closeConfirmation(false));
  }

  function bindKeyboard() {
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !elements.confirm.hidden) {
        event.preventDefault();
        closeConfirmation(false);
        return;
      }
      if (elements.body.dataset.mode !== "tv") {
        return;
      }
      if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) {
        return;
      }
      const items = focusableItems();
      if (!items.length) {
        return;
      }
      const current = document.activeElement;
      event.preventDefault();
      if (!items.includes(current)) {
        items[0].focus();
        return;
      }
      const next = findDirectionalTarget(current, items, event.key);
      if (next) {
        next.focus();
      }
    });
  }

  function focusableItems() {
    const scope = elements.confirm.hidden ? document : elements.confirm;
    return Array.from(scope.querySelectorAll("button:not([disabled]), input:not([disabled]), [tabindex='0']"))
      .filter((element) => element.offsetParent !== null);
  }

  function findDirectionalTarget(current, items, key) {
    const origin = current.getBoundingClientRect();
    const originX = origin.left + origin.width / 2;
    const originY = origin.top + origin.height / 2;
    const horizontal = key === "ArrowLeft" || key === "ArrowRight";
    const forward = key === "ArrowRight" || key === "ArrowDown";
    let best = null;
    let bestScore = Infinity;
    items.forEach((item) => {
      if (item === current) {
        return;
      }
      const rect = item.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;
      const dx = x - originX;
      const dy = y - originY;
      const primary = horizontal ? dx : dy;
      const secondary = horizontal ? dy : dx;
      if ((forward && primary < 6) || (!forward && primary > -6)) {
        return;
      }
      const score = Math.abs(primary) + Math.abs(secondary) * 2.2;
      if (score < bestScore) {
        bestScore = score;
        best = item;
      }
    });
    return best;
  }

  async function loadConfig() {
    try {
      const value = await fetchJson("/api/config");
      config = Object.assign(config, value);
    } catch (error) {
      // Defaults keep the frontend usable if config is temporarily unavailable.
    }
  }

  async function start() {
    applyMode();
    bindActions();
    bindKeyboard();
    await loadConfig();
    await refresh();
    setInterval(refresh, Math.max(500, Number(config.poll_interval_ms) || 1000));
  }

  start();
})();
