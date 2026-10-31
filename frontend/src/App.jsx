import React, { Component, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  ArrowUpRight,
  ArrowRight,
  Plus,
  X,
  Settings2,
  Zap,
  ShieldCheck,
  SlidersHorizontal,
  ChevronRight,
  House,
  Workflow,
  Clock3,
  Check,
  FlaskConical,
  RotateCcw,
  Wifi,
  Power,
  MoveUpRight,
} from "lucide-react";
import CountUp from "./components/reactbits/CountUp";
import Dither from "./components/reactbits/Dither";
import DarkVeil from "./components/reactbits/DarkVeil";
import SpotlightCard from "./components/reactbits/SpotlightCard";

const base = import.meta.env.BASE_URL;
const descriptions = {
  smart_plug_1: {
    image: "plug",
    sub: "Энергия под контролем",
    signal: "power_w",
    unit: "Вт",
    toggle: "power_switch",
    on: 1,
    alarm: "overload_alarm",
    status: (d) =>
      d.overload_alarm ? "Защита" : d.power_switch ? "Включено" : "Выключено",
  },
  light_1: {
    image: "lamp",
    sub: "Свет под настроение",
    signal: "brightness",
    unit: "%",
    toggle: "lamp",
    on: 1,
    status: (d) => (d.lamp ? "Включено" : "Выключено"),
  },
  thermostat_1: {
    image: "thermostat",
    sub: "Ваша идеальная температура",
    signal: "temperature",
    unit: "°C",
    decimals: 1,
    toggle: "mode",
    on: 3,
    active: (d) => !d.fault,
    status: (d) =>
      d.fault
        ? "Нет данных"
        : d.output === 1
          ? "Нагрев"
          : d.output === 2
            ? "Охлаждение"
            : "Ожидание",
  },
  ventilation_1: {
    image: "ventilation",
    sub: "Свежий воздух каждый день",
    signal: "co2",
    unit: "ppm",
    toggle: "mode",
    on: 1,
    active: (d) => d.mode !== 0,
    status: (d) =>
      d.mode === 0 ? "Выключено" : d.mode === 1 ? "Авто" : "Ручной",
  },
  temp_sensor_1: {
    image: "temp_sensor",
    sub: "Климат в комнате",
    signal: "temperature",
    unit: "°C",
    decimals: 1,
    active: (d) => !d.low_battery && !d.fault,
    status: (d) =>
      d.fault
        ? "Неисправность"
        : d.tamper
          ? "Вскрыт"
          : d.low_battery
            ? "Низкий заряд"
            : "На связи",
  },
  leak_1: {
    image: "leak",
    sub: "Защита от протечки",
    signal: "battery",
    unit: "%",
    active: (d) => !d.low_battery && !d.tamper,
    alarm: "leak",
    status: (d) =>
      d.leak
        ? "Протечка"
        : d.tamper
          ? "Вскрыт"
          : d.low_battery
            ? "Низкий заряд"
            : "Сухо",
  },
  hub_1: {
    image: "hub",
    sub: "Три датчика и сирена",
    signal: "sensors_online",
    unit: "датчика",
    active: (d) => !d.mute,
    alarm: "leak",
    status: (d) =>
      d.leak ? "Протечка" : d.mute ? "Без звука" : "Охрана",
  },
  fire_1: {
    image: "fire",
    sub: "Пожарная безопасность",
    signal: "smoke",
    unit: "%",
    active: (d) => !d.alarm,
    alarm: "alarm",
    status: (d) =>
      d.alarm
        ? "Тревога"
        : d.low_battery
          ? "Низкий заряд"
          : "Дежурство",
  },
  counter_1: {
    image: "counter",
    sub: "Расход электроэнергии",
    signal: "power_w",
    unit: "Вт",
    active: (d) => !!d.load_relay,
    status: (d) => (d.load_relay ? "Учёт" : "Реле отключено"),
  },
  tv_1: {
    image: "tv",
    sub: "Кино и приложения",
    signal: "volume",
    unit: "%",
    toggle: "power",
    on: 1,
    status: (d) => (d.power ? "Включён" : "Выключен"),
  },
  fridge_1: {
    image: "fridge",
    sub: "Свежесть под контролем",
    signal: "fridge_temp",
    unit: "°C",
    decimals: 1,
    active: (d) => !d.alarm,
    alarm: "alarm",
    status: (d) =>
      d.alarm === 2
        ? "Дверь открыта"
        : d.alarm === 1
          ? "Температура"
          : "Норма",
  },
  kettle_1: {
    image: "kettle",
    sub: "Кипяток к чаю",
    signal: "temperature",
    unit: "°C",
    toggle: "power",
    on: 1,
    alarm: "dry_boil",
    status: (d) =>
      d.dry_boil ? "Сухой ход" : d.power ? "Нагрев" : "Готов",
  },
  stove_1: {
    image: "stove",
    sub: "Четыре конфорки",
    signal: "power_w",
    unit: "Вт",
    toggle: "burner_1",
    on: 5,
    alarm: "overheat",
    status: (d) =>
      d.overheat
        ? "Перегрев"
        : d.boil_dry
          ? "Сухой нагрев"
          : d.burner_1
            ? "Нагрев"
            : "Выключена",
  },
  oven_1: {
    image: "oven",
    sub: "Готовим с комфортом",
    signal: "temperature",
    unit: "°C",
    toggle: "power",
    on: 1,
    alarm: "alarm",
    status: (d) =>
      d.alarm === 1
        ? "Дверь открыта"
        : d.alarm === 2
          ? "Перегрев"
          : d.power
            ? "Нагрев"
            : "Выключена",
  },
  intercom_1: {
    image: "intercom",
    sub: "Дверь и гости",
    signal: "volume",
    unit: "%",
    active: (d) => d.call_state > 0 || !!d.door_open,
    alarm: "tamper",
    status: (d) =>
      d.tamper
        ? "Вскрыт"
        : d.call_state === 1
          ? "Звонок"
          : d.call_state === 2
            ? "Разговор"
            : d.door_open
              ? "Дверь открыта"
              : "Ожидание",
  },
};
const fallbackDescription = {
  image: "plug",
  sub: "Устройство дома",
  signal: "fw",
  unit: "",
  status: () => "На связи",
};
function plural(count, one, few, many) {
  const n = Math.abs(count) % 100,
    last = n % 10;
  if (n > 10 && n < 20) return many;
  if (last > 1 && last < 5) return few;
  if (last === 1) return one;
  return many;
}
async function api(path, body, method) {
  const response = await fetch(path, {
    method: method || (body ? "POST" : "GET"),
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(8000),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.error || "Не удалось выполнить действие");
  return data;
}
function NumberValue({ value, decimals = 0, ...props }) {
  const prev = useRef(0);
  const reduce = useReducedMotion();
  const from = prev.current;
  useEffect(() => {
    prev.current = value;
  }, [value]);
  return reduce ? (
    <span>{Number(value).toFixed(decimals)}</span>
  ) : (
    <CountUp
      from={from}
      to={Number(value) || 0}
      decimals={decimals}
      duration={0.7}
      separator=" "
      trigger="load"
      {...props}
    />
  );
}
class EffectBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}
function Modal({ children, title, onClose, className = "" }) {
  const ref = useRef(null);
  useEffect(() => {
    const node = ref.current;
    node.showModal();
    const close = (event) => {
      event.preventDefault();
      onClose();
    };
    node.addEventListener("cancel", close);
    return () => node.removeEventListener("cancel", close);
  }, []);
  return (
    <dialog
      ref={ref}
      className={className}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      aria-label={title}
    >
      <div className="modal-heading">
        <h2>{title}</h2>
        <button className="icon-button" aria-label="Закрыть" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
function Switch({ on, onClick, label, disabled }) {
  return (
    <button
      className={"switch " + (on ? "on" : "")}
      role="switch"
      aria-label={label}
      aria-checked={on}
      onClick={onClick}
      disabled={disabled}
    >
      <span />
    </button>
  );
}
function Activity({ events, short = false }) {
  const visible = events
    .filter((e) => e.type !== "log")
    .slice()
    .reverse()
    .slice(0, short ? 3 : 100);
  return visible.length ? (
    <div className="activity-list">
      {visible.map((e) => (
        <div className="activity-row" key={e.id}>
          <span
            className={"activity-icon " + (e.type === "alarm" ? "warning" : "")}
          >
            {e.type === "alarm" ? (
              <ShieldCheck size={17} />
            ) : e.type.startsWith("scenario") ? (
              <Workflow size={17} />
            ) : (
              <Clock3 size={17} />
            )}
          </span>
          <span>
            {e.message ||
              (e.type === "state_change"
                ? `Розетка ${e.value ? "включена" : "выключена"}`
                : e.type)}
            <small>{new Date(e.time * 1000).toLocaleTimeString("ru-RU")}</small>
          </span>
        </div>
      ))}
    </div>
  ) : (
    <div className="empty-state">
      <Clock3 size={24} />
      <p>Здесь будет история вашего дома</p>
      <small>Включите устройство или запустите сценарий.</small>
    </div>
  );
}
function DeviceDetails({ id, home, declarations, command }) {
  const state = home.devices[id],
    sigs = declarations[id] || [];
  const [values, setValues] = useState({ ...state });
  const spec = descriptions[id] || fallbackDescription;
  return (
    <>
      <div className="detail-hero">
        <img
          src={`${base}images/${spec.image}.webp`}
          alt={home.metadata[id].name}
        />
        <span>
          {home.metadata[id].room}
          <strong>
            {state[spec.signal]} <small>{spec.unit}</small>
          </strong>
        </span>
      </div>
      {id === "smart_plug_1" && !!state.overload_alarm && (
        <p className="inline-warning">
          Сработала защита. Уменьшите нагрузку ниже лимита, примените изменение,
          сбросьте защиту и включите розетку.
        </p>
      )}
      <div className="detail-readings">
        {sigs
          .filter((s) => s.management === "r" && s.name !== "fw")
          .map((s) => (
            <div key={s.name}>
              <span>{s.title}</span>
              <strong>
                {state[s.name]} <small>{s.measure}</small>
              </strong>
            </div>
          ))}
      </div>
      <div className="detail-controls">
        {sigs
          .filter((s) => s.management !== "r")
          .map((s) => (
            <form
              key={s.name}
              onSubmit={(e) => {
                e.preventDefault();
                command(
                  id,
                  s.name,
                  Number(s.control === "button" ? 1 : values[s.name]),
                );
              }}
            >
              <label htmlFor={"signal-" + s.name}>{s.title}</label>
              <div>
                {s.control === "button" ? null : s.layout ? (
                  <select
                    id={"signal-" + s.name}
                    value={values[s.name]}
                    onChange={(e) =>
                      setValues({ ...values, [s.name]: e.target.value })
                    }
                  >
                    {Object.entries(s.layout).map(([value, title]) => (
                      <option value={value} key={value}>
                        {title}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    required
                    id={"signal-" + s.name}
                    type="number"
                    step="any"
                    min={s.min}
                    max={s.max}
                    value={values[s.name]}
                    onChange={(e) =>
                      setValues({ ...values, [s.name]: e.target.value })
                    }
                  />
                )}
                <button className="secondary" type="submit">
                  {s.control === "button" ? "Выполнить" : "Применить"}
                </button>
              </div>
            </form>
          ))}
      </div>
    </>
  );
}
function ScenarioEditor({ item, home, declarations, onSave, notify }) {
  const [name, setName] = useState(item?.name || "");
  const [when, setWhen] = useState(
    item?.when || {
      device: "smart_plug_1",
      signal: "power_w",
      operator: ">",
      value: 1000,
    },
  );
  const [actions, setActions] = useState(
    item?.do || [{ device: "light_1", signal: "lamp", value: 0 }],
  );
  const [enabled, setEnabled] = useState(item?.enabled ?? true);
  const [preview, setPreview] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const draft = () => ({
    ...(item?.id ? { id: item.id } : {}),
    name,
    enabled,
    when,
    do: actions,
  });
  const devices = Object.entries(home.metadata);
  function signalChoices(id, writable) {
    return (declarations[id] || []).filter(
      (s) =>
        s.name !== "fw" &&
        (writable ? s.management !== "r" : s.management !== "w"),
    );
  }
  function controls(value, set, action = false) {
    return (
      <>
        <label>
          Устройство
          <select
            value={value.device}
            onChange={(e) => {
              const id = e.target.value;
              set({
                ...value,
                device: id,
                signal: signalChoices(id, action)[0].name,
              });
            }}
          >
            {devices.map(([id, m]) => (
              <option key={id} value={id}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {action ? "Действие" : "Показатель"}
          <select
            value={value.signal}
            onChange={(e) => set({ ...value, signal: e.target.value })}
          >
            {signalChoices(value.device, action).map((s) => (
              <option key={s.name} value={s.name}>
                {s.title}
              </option>
            ))}
          </select>
        </label>
        <div className="form-row">
          {!action && (
            <label>
              Условие
              <select
                value={value.operator}
                onChange={(e) => set({ ...value, operator: e.target.value })}
              >
                {[
                  [">", "Больше"],
                  ["<", "Меньше"],
                  ["==", "Равно"],
                  [">=", "Не меньше"],
                  ["<=", "Не больше"],
                  ["!=", "Не равно"],
                ].map(([v, t]) => (
                  <option key={v} value={v}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            Значение
            <input
              required
              type="number"
              step="any"
              value={value.value}
              onChange={(e) =>
                set({
                  ...value,
                  value: e.target.value === "" ? "" : Number(e.target.value),
                })
              }
            />
          </label>
        </div>
        {action && (
          <small>
            {Object.entries(
              (declarations[value.device] || []).find(
                (s) => s.name === value.signal,
              )?.layout || {},
            )
              .map(([v, t]) => `${v} = ${t}`)
              .join(" · ")}
          </small>
        )}
      </>
    );
  }
  async function test() {
    setBusy(true);
    setError("");
    try {
      const r = await api("/api/simulations", {
        seconds: 30,
        scenario: draft(),
      });
      const n = r.events.filter((e) => e.type === "scenario_triggered").length;
      setPreview(
        `За 30 секунд: ${n ? `${n} срабатываний` : "условие не наступило"}. Мощность в конце: ${r.state.summary.power_w} Вт. Состояние дома не изменилось.`,
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
          await onSave(draft());
        } catch (err) {
          setError(err.message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <label>
        Название
        <input
          required
          value={name}
          maxLength={120}
          onChange={(e) => setName(e.target.value)}
          placeholder="Например, уютный вечер"
        />
      </label>
      <section className="rule-group">
        <h3>
          <span>Если</span> Происходит событие
        </h3>
        {controls(when, setWhen)}
      </section>
      {actions.map((a, i) => (
        <section className="rule-group" key={i}>
          <h3>
            <span>Тогда</span> Выполнить действие{" "}
            {actions.length > 1 && (
              <button
                type="button"
                className="icon-button"
                aria-label="Удалить действие"
                onClick={() => setActions(actions.filter((_, j) => i !== j))}
              >
                <X size={14} />
              </button>
            )}
          </h3>
          {controls(
            a,
            (next) =>
              setActions(actions.map((old, j) => (i === j ? next : old))),
            true,
          )}
        </section>
      ))}
      <button
        type="button"
        className="text-button"
        onClick={() =>
          setActions([
            ...actions,
            { device: "light_1", signal: "lamp", value: 1 },
          ])
        }
      >
        <Plus size={14} />
        Добавить действие
      </button>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        Включить после сохранения
      </label>
      {error && (
        <p className="inline-warning" role="alert">
          {error}
        </p>
      )}
      {preview && (
        <div className="preview-result" role="status">
          {preview}
        </div>
      )}
      <div className="modal-actions">
        <button
          type="button"
          className="secondary"
          onClick={test}
          disabled={busy || !name}
        >
          Проверить · 30 сек
        </button>
        <button type="submit" className="primary" disabled={busy}>
          Сохранить сценарий
        </button>
      </div>
    </form>
  );
}

export default function App() {
  const [home, setHome] = useState(null),
    [declarations, setDeclarations] = useState({}),
    [scenarios, setScenarios] = useState([]),
    [events, setEvents] = useState([]);
  const [online, setOnline] = useState(false),
    [page, setPage] = useState(
      ["home", "scenarios", "history"].includes(location.hash.slice(1))
        ? location.hash.slice(1)
        : "home",
    );
  const [room, setRoom] = useState("Все"),
    [selected, setSelected] = useState(null),
    [editor, setEditor] = useState(null),
    [settings, setSettings] = useState(false),
    [confirmation, setConfirmation] = useState(null),
    [message, setMessage] = useState(null);
  const [eventFilter, setEventFilter] = useState("all");
  const refreshBusy = useRef(false),
    timer = useRef(),
    resolveConfirm = useRef();
  const reduce = useReducedMotion();
  const tv = new URLSearchParams(location.search).get("mode") === "tv";
  useEffect(() => {
    document.body.dataset.mode = tv ? "tv" : "phone";
  }, [tv]);
  function notify(text, error = false) {
    clearTimeout(timer.current);
    setMessage({ text, error });
    timer.current = setTimeout(() => setMessage(null), 5000);
  }
  async function refresh() {
    if (refreshBusy.current) return;
    refreshBusy.current = true;
    try {
      const [h, d, s, e] = await Promise.all(
        ["/api/state", "/api/devices", "/api/scenarios", "/api/events"].map(
          (p) => api(p),
        ),
      );
      setHome(h);
      setDeclarations(d);
      setScenarios(s);
      setEvents(e);
      setOnline(true);
    } catch {
      setOnline(false);
    } finally {
      refreshBusy.current = false;
    }
  }
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 1500);
    return () => {
      clearInterval(t);
      clearTimeout(timer.current);
    };
  }, []);
  useEffect(() => {
    const fn = () =>
      setPage(
        ["home", "scenarios", "history"].includes(location.hash.slice(1))
          ? location.hash.slice(1)
          : "home",
      );
    addEventListener("hashchange", fn);
    return () => removeEventListener("hashchange", fn);
  }, []);
  useEffect(() => {
    if (!tv) return;
    const fn = (e) => {
      if (
        !e.key.startsWith("Arrow") ||
        ["INPUT", "SELECT"].includes(document.activeElement.tagName)
      )
        return;
      const scope = document.querySelector("dialog[open]") || document;
      const nodes = [...scope.querySelectorAll("button,a,input,select")].filter(
        (n) => n.getClientRects().length && !n.disabled,
      );
      const r = document.activeElement.getBoundingClientRect();
      const horizontal = ["ArrowLeft", "ArrowRight"].includes(e.key);
      const sign = ["ArrowLeft", "ArrowUp"].includes(e.key) ? -1 : 1;
      const next = nodes
        .map((n) => {
          const b = n.getBoundingClientRect();
          return { n, x: b.x - r.x, y: b.y - r.y };
        })
        .filter(
          (p) =>
            p.n !== document.activeElement &&
            (horizontal ? p.x : p.y) * sign > 3,
        )
        .sort(
          (a, b) =>
            Math.hypot(a.x, a.y) +
            2 * Math.abs(horizontal ? a.y : a.x) -
            (Math.hypot(b.x, b.y) + 2 * Math.abs(horizontal ? b.y : b.x)),
        )[0];
      if (next) {
        e.preventDefault();
        next.n.focus();
      }
    };
    addEventListener("keydown", fn);
    return () => removeEventListener("keydown", fn);
  }, [tv]);
  function ask(text) {
    setConfirmation(text);
    return new Promise((resolve) => {
      resolveConfirm.current = resolve;
    });
  }
  function answer(ok) {
    setConfirmation(null);
    resolveConfirm.current?.(ok);
  }
  async function command(id, signal, value) {
    if (!online) return notify("Нет связи. Дождитесь подключения.", true);
    try {
      const r = await api("/api/commands/preview", {
        device: id,
        signal,
        value,
      });
      if (r.status === "confirmation_required") {
        if (!(await ask(r.summary))) return;
        await api(`/api/commands/${r.confirmation_id}/confirm`, {});
      }
      notify("Настройки применены");
      await refresh();
    } catch (e) {
      notify(e.message, true);
    }
  }
  async function experiment(preset) {
    try {
      await api("/api/demo/start", { preset });
      notify("Эксперимент запущен");
      setSettings(false);
      setTimeout(refresh, 1100);
    } catch (e) {
      notify(e.message, true);
    }
  }
  async function reset() {
    if (
      !(await ask(
        "Сбросить состояния эмуляторов? Сохранённые сценарии останутся.",
      ))
    )
      return;
    try {
      await api("/api/demo/reset", {});
      await refresh();
      notify("Состояния устройств сброшены");
    } catch (e) {
      notify(e.message, true);
    }
  }
  const alarm = !!home?.devices.smart_plug_1.overload_alarm;
  const deviceCount = Object.keys(home?.devices || {}).length;
  const deviceWord = plural(deviceCount, "устройство", "устройства", "устройств");
  const emulatorWord = plural(deviceCount, "эмулятор", "эмулятора", "эмуляторов");
  const meaningful = events.filter((e) => e.type !== "log");
  const rooms = [
    "Все",
    ...new Set(Object.values(home?.metadata || {}).map((m) => m.room)),
  ];
  const meta = (id) => home?.metadata[id]?.name || id;
  const signalTitle = (a) =>
    declarations[a.device]?.find((s) => s.name === a.signal)?.title || a.signal;

  return (
    <div className="app-shell">
      <header className="header">
        <a href="#home" className="brand">
          <span className="brand-symbol">
            <Zap size={21} fill="currentColor" />
          </span>
          power<span>guardian</span>
        </a>
        <nav aria-label="Главная навигация">
          {[
            ["home", "Мой дом", House],
            ["scenarios", "Сценарии", Workflow],
            ["history", "История", Clock3],
          ].map(([id, label, Icon]) => (
            <a key={id} className={page === id ? "active" : ""} href={"#" + id}>
              <Icon size={15} />
              <span>{label}</span>
              {page === id && <motion.i layoutId="nav-dot" />}
            </a>
          ))}
        </nav>
        <div className="header-right">
          <span className={"connection " + (!online ? "offline" : "")}>
            <i />
            {online ? "На связи" : "Подключение"}
          </span>
          <button
            className="icon-button"
            aria-label="Настройки и эксперименты"
            onClick={() => setSettings(true)}
          >
            <Settings2 size={19} />
          </button>
        </div>
      </header>
      <main>
        <AnimatePresence mode="wait">
          <motion.div
            key={page}
            initial={reduce ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            {!online && (
              <div className="offline-notice" role="status">
                {home
                  ? "Соединение потеряно. Показаны последние данные."
                  : "Подключаемся к вашему дому…"}
                <button onClick={refresh}>Повторить</button>
              </div>
            )}
            {page === "home" && (
              <>
                <section className="hero">
                  <div className="hero-copy">
                    <span className="home-location">
                      <House size={13} /> Моя квартира <span> / </span>{" "}
                      {new Date().toLocaleDateString("ru-RU", {
                        day: "numeric",
                        month: "long",
                      })}
                    </span>
                    <h1>
                      {alarm ? (
                        <>
                          Дом просит
                          <br />
                          вашего внимания.
                        </>
                      ) : (
                        <>
                          Дома всё
                          <br />
                          как надо.
                        </>
                      )}
                    </h1>
                    <p>
                      {alarm
                        ? "Защита отключила розетку. Проверьте нагрузку."
                        : "Свет, тепло и спокойствие. В вашем ритме."}
                    </p>
                    <div className="hero-status">
                      <span>
                        <i />
                        {deviceCount} {deviceWord}
                      </span>
                      <span>
                        <Workflow size={13} />
                        {home?.summary.active_scenarios ?? "—"} сценариев
                      </span>
                      <span>
                        <ShieldCheck size={14} />
                        {alarm ? "Защита сработала" : "Защита активна"}
                      </span>
                    </div>
                  </div>
                  <div className="hero-energy">
                    <span className="energy-icon">
                      <Zap size={19} />
                    </span>
                    <span>Дом потребляет</span>
                    <div>
                      <NumberValue value={home?.summary.power_w || 0} />
                      <small>Вт</small>
                    </div>
                    <p>
                      {Number(home?.summary.energy_kwh || 0).toFixed(4)} кВт·ч
                      за сеанс
                    </p>
                  </div>
                </section>
                {alarm && (
                  <button
                    className="alarm-banner"
                    onClick={() => setSelected("smart_plug_1")}
                  >
                    <span>
                      <ShieldCheck size={18} />
                      Розетка отключена защитой
                    </span>
                    <span>
                      Восстановить работу <ArrowUpRight size={16} />
                    </span>
                  </button>
                )}
                <section className="devices-section">
                  <div className="section-heading">
                    <div>
                      <h2>
                        Ваши устройства
                        <span>{String(deviceCount).padStart(2, "0")}</span>
                      </h2>
                    </div>
                    <div className="room-filter" aria-label="Комнаты">
                      {rooms.map((r) => (
                        <button
                          key={r}
                          onClick={() => setRoom(r)}
                          className={room === r ? "selected" : ""}
                        >
                          {r}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="gallery-wrap">
                    <div className="device-grid">
                      {home
                        ? Object.entries(home.devices)
                            .filter(
                              ([id]) =>
                                room === "Все" ||
                                home.metadata[id].room === room,
                            )
                            .map(([id, d], index) => {
                              const spec = descriptions[id] || fallbackDescription,
                                on = spec.toggle ? !!d[spec.toggle] : false,
                                active = spec.active ? !!spec.active(d) : on,
                                alarm = spec.alarm
                                  ? !!d[spec.alarm]
                                  : !!d.overload_alarm,
                                m = home.metadata[id];
                              return (
                                <SpotlightCard
                                  key={id}
                                  className={
                                    "device-card " +
                                    (alarm ? "has-alarm" : "")
                                  }
                                  spotlightColor="rgba(238, 154, 98, 0.35)"
                                  intensity={0.12}
                                  borderGlow={0.3}
                                  grain={0.04}
                                  style={{
                                    "--spotlight-card-surface":
                                      "rgba(9,9,9,.94)",
                                  }}
                                >
                                  <div className="device-card-top">
                                    <span className="device-number">
                                      0
                                      {Object.keys(home.devices).indexOf(id) +
                                        1}
                                    </span>
                                    {spec.toggle && (
                                      <Switch
                                        on={on}
                                        disabled={!online}
                                        label={
                                          (on ? "Выключить " : "Включить ") +
                                          m.name
                                        }
                                        onClick={() =>
                                          command(
                                            id,
                                            spec.toggle,
                                            on ? 0 : spec.on,
                                          )
                                        }
                                      />
                                    )}
                                  </div>
                                  <button
                                    className={
                                      "product-image " +
                                      (!active ? "device-off" : "")
                                    }
                                    onClick={() => setSelected(id)}
                                    aria-label={"Настроить " + m.name}
                                  >
                                    {!reduce && index < 2 && <div className="photo-effect" aria-hidden="true"><EffectBoundary>{index === 0 ? <Dither waveColor={[0.38,0.25,0.18]} waveAmplitude={0.1} waveSpeed={0.025} pixelSize={3} enableMouseInteraction={false} dpr={0.5} disableAnimation={!!selected || !!settings || !!confirmation} /> : <DarkVeil color="#b18664" speed={0.12} quality={0.2} dpr={0.5} mouseInteraction={false} paused={!!selected || !!settings || !!confirmation} />}</EffectBoundary></div>}
                                    <motion.img
                                      src={`${base}images/${spec.image}.webp`}
                                      alt={m.name}
                                      initial={
                                        reduce
                                          ? false
                                          : { opacity: 0, scale: 0.94 }
                                      }
                                      animate={{ opacity: 1, scale: 1 }}
                                      transition={{
                                        delay: index * 0.08,
                                        duration: 0.7,
                                      }}
                                      whileHover={
                                        reduce
                                          ? {}
                                          : {
                                              scale: 1.035,
                                              rotate:
                                                spec.image === "lamp" ? -2 : 0,
                                            }
                                      }
                                    />
                                    <span className="image-grain" />
                                  </button>
                                  <div className="device-room">
                                    <i className={active ? "lit" : ""} />
                                    {m.room}
                                    <span>
                                      {spec.status
                                        ? spec.status(d)
                                        : on
                                          ? "Включено"
                                          : "Выключено"}
                                    </span>
                                  </div>
                                  <div className="device-card-bottom">
                                    <button
                                      className="device-title"
                                      onClick={() => setSelected(id)}
                                    >
                                      {m.name}
                                      <small>{spec.sub}</small>
                                    </button>
                                    <span className="device-value">
                                      <NumberValue
                                        value={
                                          id === "light_1" && !on
                                            ? 0
                                            : d[spec.signal] ?? 0
                                        }
                                        decimals={
                                          spec.decimals ??
                                          (id === "thermostat_1" ? 1 : 0)
                                        }
                                      />
                                      <small>{spec.unit}</small>
                                    </span>
                                  </div>
                                  <button
                                    className="device-details-link"
                                    onClick={() => setSelected(id)}
                                    aria-label={"Параметры " + m.name}
                                  >
                                    <ArrowUpRight size={16} />
                                  </button>
                                </SpotlightCard>
                              );
                            })
                        : Array.from({ length: 8 }, (_, i) => (
                            <div className="device-skeleton" key={i} />
                          ))}
                    </div>
                  </div>
                </section>
                <section className="lower-grid">
                  <div>
                    <div className="section-heading">
                      <h2>Дом заботится сам</h2>
                      <a href="#scenarios">
                        Все сценарии <ArrowUpRight size={14} />
                      </a>
                    </div>
                    <button
                      className="automation-teaser"
                      onClick={() => { location.hash = 'scenarios'; }}
                    >
                      <span className="workflow-symbol">
                        <Workflow size={25} />
                      </span>
                      <span>
                        <strong>
                          {scenarios[0]?.name || "Ваш первый сценарий"}
                        </strong>
                        <small>
                          {scenarios.length
                            ? "Автоматизация повседневных забот"
                            : "Свяжите устройства одним правилом"}
                        </small>
                      </span>
                      <ChevronRight size={19} />
                    </button>
                  </div>
                  <div>
                    <div className="section-heading">
                      <h2>Последние события</h2>
                      <a href="#history">
                        История <ArrowUpRight size={14} />
                      </a>
                    </div>
                    <Activity events={events} short />
                  </div>
                </section>
              </>
            )}
            {page === "scenarios" && (
              <>
                <section className="page-intro">
                  <div>
                    <span className="home-location">Автоматизация</span>
                    <h1>
                      Меньше действий.
                      <br />
                      Больше комфорта.
                    </h1>
                    <p>Устройства работают вместе по вашим правилам.</p>
                  </div>
                  <button
                    className="primary"
                    disabled={!home}
                    onClick={() => setEditor({})}
                  >
                    <Plus size={16} />
                    Новый сценарий
                  </button>
                </section>
                <div className="scenario-grid">
                  {scenarios.map((s) => (
                    <SpotlightCard key={s.id} className="scenario-card">
                      <div className="scenario-card-head">
                        <Workflow size={24} />
                        <Switch
                          on={s.enabled}
                          disabled={!online}
                          label={"Переключить " + s.name}
                          onClick={async () => {
                            if (
                              await ask(
                                `${s.enabled ? "Отключить" : "Включить"} сценарий «${s.name}»?`,
                              )
                            )
                              try {
                                await api(`/api/scenarios/${s.id}/toggle`, {
                                  enabled: !s.enabled,
                                });
                                refresh();
                              } catch (e) {
                                notify(e.message, true);
                              }
                          }}
                        />
                      </div>
                      <h2>{s.name}</h2>
                      <div className="rule-summary">
                        <span>Если</span>
                        <p>
                          {meta(s.when.device)}
                          <small>
                            {signalTitle(s.when)} {s.when.operator}{" "}
                            {s.when.value}
                          </small>
                        </p>
                      </div>
                      {s.do.map((a, i) => (
                        <div className="rule-summary" key={i}>
                          <span>Тогда</span>
                          <p>
                            {meta(a.device)}
                            <small>
                              {signalTitle(a)} → {a.value}
                            </small>
                          </p>
                        </div>
                      ))}
                      <div className="scenario-card-actions">
                        <button
                          className="secondary"
                          onClick={() => setEditor(s)}
                        >
                          Изменить
                        </button>
                        <button
                          className="text-button"
                          onClick={async () => {
                            if (await ask(`Удалить сценарий «${s.name}»?`))
                              try {
                                await api(
                                  `/api/scenarios/${s.id}`,
                                  null,
                                  "DELETE",
                                );
                                refresh();
                              } catch (e) {
                                notify(e.message, true);
                              }
                          }}
                        >
                          Удалить
                        </button>
                      </div>
                    </SpotlightCard>
                  ))}
                  <button
                    className="add-scenario"
                    disabled={!home}
                    onClick={() => setEditor({})}
                  >
                    <Plus size={28} />
                    <span>Создать сценарий</span>
                    <small>Если событие — тогда действие</small>
                  </button>
                </div>
              </>
            )}
            {page === "history" && (
              <>
                <section className="page-intro">
                  <div>
                    <span className="home-location">Всегда в курсе</span>
                    <h1>Жизнь вашего дома.</h1>
                    <p>Что произошло и почему — без лишнего шума.</p>
                  </div>
                </section>
                <div className="history-filters">
                  {[
                    ["all", "Все события"],
                    ["alarm", "Безопасность"],
                    ["scenario_triggered", "Сценарии"],
                    ["command", "Команды"],
                  ].map(([v, t]) => (
                    <button
                      className={eventFilter === v ? "selected" : ""}
                      key={v}
                      onClick={() => setEventFilter(v)}
                    >
                      {t}
                    </button>
                  ))}
                </div>
                <Activity
                  events={meaningful.filter(
                    (e) => eventFilter === "all" || e.type === eventFilter,
                  )}
                />
              </>
            )}
          </motion.div>
        </AnimatePresence>
      </main>
      <footer>
        <span className="footer-brand">powerguardian</span>
        <span>
          <i />
          Эмуляторы Ujin OS
        </span>
        <button onClick={() => setSettings(true)}>
          Лаборатория <ArrowUpRight size={12} />
        </button>
      </footer>
      {selected && home && (
        <Modal title={meta(selected)} onClose={() => setSelected(null)}>
          <DeviceDetails
            key={selected}
            id={selected}
            home={home}
            declarations={declarations}
            command={command}
          />
        </Modal>
      )}
      {editor && home && (
        <Modal
          title={editor.id ? "Изменить сценарий" : "Новый сценарий"}
          onClose={() => setEditor(null)}
        >
          <ScenarioEditor
            item={editor}
            home={home}
            declarations={declarations}
            notify={notify}
            onSave={async (s) => {
              await api("/api/scenarios", s);
              setEditor(null);
              refresh();
              notify("Сценарий сохранён");
            }}
          />
        </Modal>
      )}
      {settings && (
        <Modal
          title="Ваше пространство"
          onClose={() => setSettings(false)}
          className="settings-modal"
        >
          <div className="settings-status">
            <Wifi size={20} />
            <div>
              <strong>{online ? "Дом на связи" : "Нет соединения"}</strong>
              <small>{location.origin}</small>
            </div>
            <span>
              {deviceCount} {emulatorWord}
            </span>
          </div>
          <h3>Попробовать в лаборатории</h3>
          <p className="settings-description">
            Эксперименты меняют виртуальные устройства. Настоящее оборудование
            не подключено.
          </p>
          <div className="experiment-list">
            {[
              [
                "overload",
                "Перегрузка розетки",
                "Нагрузка 2400 Вт. Проверка защиты.",
                Zap,
              ],
              [
                "co2",
                "Свежий воздух",
                "CO₂ 1500 ppm. Вентиляция включится.",
                Wifi,
              ],
              [
                "evening",
                "Уютный вечер",
                "Мягкий свет и температура 23 °C.",
                House,
              ],
              [
                "comfort",
                "Тепло по датчику",
                "19 °C в спальне. Термостат включит нагрев.",
                SlidersHorizontal,
              ],
              [
                "leak",
                "Протечка",
                "Датчик сработал, нагрузка отключена.",
                ShieldCheck,
              ],
              [
                "fire",
                "Пожар",
                "Задымление 80 %. Проверка тревоги.",
                FlaskConical,
              ],
              [
                "intercom",
                "Звонок в дверь",
                "Вызов домофона и свет в прихожей.",
                House,
              ],
              [
                "kitchen",
                "Кухня",
                "Чайник и конфорка включены.",
                FlaskConical,
              ],
            ].map(([preset, title, sub, Icon]) => (
              <button
                key={preset}
                onClick={() => experiment(preset)}
                disabled={!online}
              >
                <Icon size={20} />
                <span>
                  {title}
                  <small>{sub}</small>
                </span>
                <ArrowUpRight size={16} />
              </button>
            ))}
          </div>
          <button className="secondary full-width" onClick={reset}>
            <RotateCcw size={14} />
            Сбросить состояния устройств
          </button>
          <p className="settings-note">
            После перегрузки: уменьшите нагрузку → сбросьте защиту → включите
            розетку. Все действия доступны в карточке розетки.
          </p>
          <a className="text-button" href={tv ? "?mode=phone" : "?mode=tv"}>
            {tv ? "Выйти из TV-режима" : "Открыть на телевизоре"}
            <ArrowUpRight size={14} />
          </a>
        </Modal>
      )}
      {confirmation && (
        <Modal
          title="Подтвердите действие"
          onClose={() => answer(false)}
          className="confirmation"
        >
          <div className="confirm-icon">
            <ShieldCheck size={28} />
          </div>
          <p>{confirmation}</p>
          <small>Подтверждение команды действует 60 секунд.</small>
          <div className="modal-actions">
            <button className="secondary" onClick={() => answer(false)}>
              Отмена
            </button>
            <button className="primary" onClick={() => answer(true)}>
              Подтвердить
            </button>
          </div>
        </Modal>
      )}
      <AnimatePresence>
        {message && (
          <motion.div
            role="status"
            className={"toast " + (message.error ? "error" : "")}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
          >
            {message.error ? <ShieldCheck size={16} /> : <Check size={16} />}
            {message.text}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
