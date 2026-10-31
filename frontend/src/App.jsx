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
import DarkVeil from "./components/reactbits/DarkVeil";
import SpotlightCard from "./components/reactbits/SpotlightCard";
import AnimatedContent from "./components/reactbits/AnimatedContent";
import ScenarioSheet from "./components/ScenarioSheet";
import HomeStatistics from "./components/HomeStatistics";
import {
  descriptions,
  fallbackDescription,
  deviceActive,
  plural,
} from "./components/deviceCatalog";
import SquishSwitch from "./components/reactbits/SquishSwitch";
import RubberSegment from "./components/reactbits/RubberSegment";
import PillNav from "./components/reactbits/PillNav";
import CardSwap, { Card } from "./components/reactbits/CardSwap";
import DeviceGauge from "./components/DeviceGauge";
import useAutoDeviceCommand from "./components/useAutoDeviceCommand";

const base = import.meta.env.BASE_URL;

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
function operationStatus(id, state) {
  if (id === "thermostat_1") {
    if (!state.mode) return "Обогрев и охлаждение выключены";
    return state.output === 1
      ? "Нагрев"
      : state.output === 2
        ? "Охлаждение"
        : "Ожидание";
  }
  if (id === "ventilation_1")
    return !state.mode
      ? "Вентилятор выключен"
      : state.fan_speed
        ? `Вентиляция · скорость ${state.fan_speed}`
        : "Вентилятор в ожидании";
  const spec = descriptions[id] || fallbackDescription;
  return spec.status ? spec.status(state) : "На связи";
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
    <SquishSwitch
      checked={on}
      onChange={onClick}
      ariaLabel={label}
      disabled={disabled}
      width={48}
      height={28}
      trackColor="#35382f"
      trackOnColor="rgb(var(--device-tint, 168, 187, 163))"
      thumbOnColor="#241b14"
    />
  );
}
function Activity({ events, short = false, metadata = {} }) {
  const reduce = useReducedMotion();
  function description(e) {
    if (e.device && metadata[e.device]) {
      if (e.signal === "lamp" || e.signal === "power_switch")
        return e.value ? "Включено" : "Выключено";
      if (e.signal === "mode") return `Режим изменён · ${e.value}`;
      if (e.signal === "brightness") return `Яркость · ${e.value}%`;
      const prefix = metadata[e.device].name + ": ";
      if (e.message?.startsWith(prefix)) return e.message.slice(prefix.length);
    }
    return (
      e.message ||
      (e.type === "state_change"
        ? `Розетка ${e.value ? "включена" : "выключена"}`
        : e.type)
    );
  }
  const visible = events
    .filter((e) => e.type !== "log")
    .slice()
    .reverse()
    .slice(0, short ? 3 : 100);
  return visible.length ? (
    <div className="activity-list">
      {visible.map((e) => (
        <motion.div
          className="activity-row"
          key={e.id}
          layout={!reduce}
          initial={reduce ? false : { opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
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
            {e.device && metadata[e.device] && (
              <strong className="activity-device">
                {metadata[e.device].name}
              </strong>
            )}
            {description(e)}
            <small>{new Date(e.time * 1000).toLocaleTimeString("ru-RU")}</small>
          </span>
        </motion.div>
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
function DeviceDetails({ id, home, declarations, command, busy, online }) {
  const state = home.devices[id],
    sigs = declarations[id] || [];
  const [values, setValues] = useState({ ...state });
  const auto = useAutoDeviceCommand(id, command, (signal) =>
    setValues((old) => ({ ...old, [signal]: state[signal] })),
  );
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
      {(id === "thermostat_1" || id === "ventilation_1") && !state.mode && (
        <p className="sensor-paused-note">
          Датчики выключены. Показаны последние измерения — обновление
          возобновится после включения устройства.
        </p>
      )}
      {id === "smart_plug_1" && !!state.overload_alarm && (
        <p className="inline-warning">
          Сработала защита. Уменьшите нагрузку ниже лимита, сбросьте защиту и
          включите розетку.
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
        {(id === "light_1" || id === "ventilation_1") && (
          <DeviceGauge
            id={id}
            state={state}
            onCommand={command}
            busy={busy}
            online={online}
          />
        )}
        {sigs
          .filter(
            (s) =>
              s.management !== "r" &&
              !(
                (id === "light_1" && s.name === "brightness") ||
                (id === "ventilation_1" && s.name === "fan_speed")
              ),
          )
          .map((s) => (
            <form
              key={s.name}
              className={s.name === "brightness" ? "brightness-control" : ""}
              onSubmit={(e) => {
                e.preventDefault();
                if (s.control === "button") command(id, s.name, 1, false);
                else auto.flush(s.name);
              }}
            >
              <label htmlFor={"signal-" + s.name}>{s.title}</label>
              <div>
                {s.control === "button" ? null : s.layout ? (
                  <select
                    id={"signal-" + s.name}
                    disabled={busy || !online}
                    value={values[s.name]}
                    onChange={(e) => {
                      setValues((old) => ({
                        ...old,
                        [s.name]: e.target.value,
                      }));
                      auto.schedule(s.name, Number(e.target.value), 0);
                    }}
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
                    disabled={busy || !online}
                    id={"signal-" + s.name}
                    type="number"
                    step="any"
                    min={s.min}
                    max={s.max}
                    value={values[s.name]}
                    onChange={(e) => {
                      setValues((old) => ({
                        ...old,
                        [s.name]: e.target.value,
                      }));
                      if (e.target.validity.valid)
                        auto.schedule(s.name, Number(e.target.value));
                      else auto.cancel(s.name);
                    }}
                    onBlur={(e) => {
                      if (e.target.reportValidity()) auto.flush(s.name);
                    }}
                  />
                )}
                {s.control === "button" && (
                  <button
                    className="secondary"
                    type="submit"
                    disabled={busy || !online}
                  >
                    {busy ? "Выполнение…" : s.title}
                  </button>
                )}
              </div>
            </form>
          ))}
      </div>
    </>
  );
}

function Login({ onEnter }) {
  const [visible, setVisible] = useState(false);
  const reduce = useReducedMotion();
  return (
    <main className="login-page">
      <section className="login-story">
        <a className="login-brand" href="#">
          Ujin<span>Fizteha</span>
        </a>
        <div>
          <span className="login-eyebrow">ВАШ ДОМ. В ВАШИХ РУКАХ.</span>
          <h1>
            Спокойствие
            <br />
            начинается
            <br />
            <em>дома.</em>
          </h1>
          <p>
            Свет, климат и энергия — в одном пространстве, которое понимает вас.
          </p>
        </div>
        <span className="login-footnote">
          <ShieldCheck size={16} /> Умный дом под вашим контролем
        </span>
      </section>
      <section className="login-panel">
        <form
          className="login-form"
          onSubmit={(e) => {
            e.preventDefault();
            onEnter();
          }}
        >
          <span className="login-eyebrow">UjinFizteha</span>
          <h2>С возвращением</h2>
          <p>Войдите, чтобы быть ближе к своему дому.</p>
          <label htmlFor="login-email">Электронная почта</label>
          <input
            id="login-email"
            type="email"
            autoComplete="username"
            placeholder="you@example.com"
            required
          />
          <label htmlFor="login-password">Пароль</label>
          <div className="login-password">
            <input
              id="login-password"
              type={visible ? "text" : "password"}
              autoComplete="current-password"
              placeholder="Введите пароль"
              required
            />
            <button
              type="button"
              onClick={() => setVisible(!visible)}
              aria-label={visible ? "Скрыть пароль" : "Показать пароль"}
            >
              {visible ? "Скрыть" : "Показать"}
            </button>
          </div>
          <button className="primary login-submit" type="submit">
            Войти <ArrowRight size={18} />
          </button>
          <div className="login-divider">
            <span>Демонстрационная версия</span>
          </div>
          <button
            className="secondary login-demo"
            type="button"
            onClick={onEnter}
          >
            Посмотреть демо <ArrowUpRight size={16} />
          </button>
          <small className="login-note">
            Это демонстрационный экран входа. Учётные записи пока не подключены;
            используйте тестовые данные.
          </small>
        </form>
      </section>
    </main>
  );
}

export default function App() {
  const [entered, setEntered] = useState(
    () => sessionStorage.getItem("guardian-demo-entered") === "1",
  );
  const reduce = useReducedMotion();
  const [lowPower] = useState(
    () =>
      (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4) ||
      navigator.connection?.saveData ||
      (navigator.deviceMemory && navigator.deviceMemory <= 4),
  );
  const [hidden, setHidden] = useState(document.hidden);
  useEffect(() => {
    const update = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  return (
    <>
      <div className="site-background" aria-hidden="true">
        {!reduce && !lowPower && (
          <EffectBoundary>
            <DarkVeil
              color="#b18664"
              speed={0.08}
              brightness={0.45}
              glow={0.1}
              grain={0}
              quality={0.3}
              dpr={1}
              mouseInteraction={false}
              paused={hidden}
              intro={false}
            />
          </EffectBoundary>
        )}
      </div>
      <div className="site-content">
        {entered ? (
          <HomeApp />
        ) : (
          <Login
            onEnter={() => {
              sessionStorage.setItem("guardian-demo-entered", "1");
              setEntered(true);
            }}
          />
        )}
      </div>
    </>
  );
}

function HomeApp() {
  const [pending, setPending] = useState({});
  const pendingRef = useRef(new Set());
  const commandQueues = useRef(new Map());
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
    scenarioDeck = useRef(null),
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
  function command(id, signal, value, requireConfirmation = false) {
    if (!online) {
      notify("Нет связи. Дождитесь подключения.", true);
      return Promise.resolve(false);
    }
    pendingRef.current.add(id);
    setPending((p) => ({ ...p, [id]: true }));
    const execute = async () => {
      try {
        const r = await api("/api/commands/preview", {
          device: id,
          signal,
          value,
          require_confirmation: requireConfirmation,
        });
        if (r.status === "confirmation_required") {
          if (!(await ask(r.summary))) return false;
          await api(`/api/commands/${r.confirmation_id}/confirm`, {});
        }
        await refresh();
        return true;
      } catch (e) {
        notify(e.message, true);
        return false;
      }
    };
    const run = (commandQueues.current.get(id) || Promise.resolve()).then(
      execute,
    );
    commandQueues.current.set(id, run);
    return run.finally(() => {
      if (commandQueues.current.get(id) === run) {
        commandQueues.current.delete(id);
        pendingRef.current.delete(id);
        setPending((p) => ({ ...p, [id]: false }));
      }
    });
  }
  async function toggleScenario(s) {
    if (pendingRef.current.has(s.id)) return;
    pendingRef.current.add(s.id);
    setPending((p) => ({ ...p, [s.id]: true }));
    try {
      await api(`/api/scenarios/${s.id}/toggle`, { enabled: !s.enabled });
      await refresh();
    } catch (e) {
      notify(e.message, true);
    } finally {
      pendingRef.current.delete(s.id);
      setPending((p) => ({ ...p, [s.id]: false }));
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
          Ujin<span>Fizteha</span>
        </a>
        <div className="main-pill-nav">
          <PillNav
            ariaLabel="Главная навигация"
            items={[
              { label: "Мой дом", href: "#home" },
              { label: "Сценарии", href: "#scenarios" },
              { label: "История", href: "#history" },
            ]}
            activeHref={`#${page}`}
            size="lg"
            surface="solid"
            indicator="pill"
            hoverEffect="glide"
            highlightColor="#edac82"
            highlightTextColor="#17120e"
            barColor="#151614"
            itemStyle="plain"
            collapse="never"
            intro={!reduce}
          />
        </div>
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
              <AnimatedContent
                distance={reduce ? 0 : 18}
                duration={0.5}
                initialOpacity={reduce ? 1 : 0}
              >
                <div className="home-page">
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
                      {alarm && (
                        <p>Защита отключила розетку. Проверьте нагрузку.</p>
                      )}
                      <div className="hero-status">
                        <span>
                          <House size={17} />
                          <strong>
                            {home ? Object.keys(home.devices).length : "—"}
                          </strong>{" "}
                          {plural(
                            home ? Object.keys(home.devices).length : 0,
                            "устройство",
                            "устройства",
                            "устройств",
                          )}
                        </span>
                        <span>
                          <Workflow size={17} />
                          <strong>
                            {home?.summary.active_scenarios ?? "—"}
                          </strong>{" "}
                          активных сценариев
                        </span>
                        <span>
                          <ShieldCheck size={17} />
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
                          Устройства
                          <span>
                            {home
                              ? String(
                                  Object.keys(home.devices).length,
                                ).padStart(2, "0")
                              : "—"}
                          </span>
                        </h2>
                      </div>
                      <div className="room-segments">
                        <RubberSegment
                          items={rooms}
                          value={room}
                          onChange={setRoom}
                          aria-label="Комнаты"
                          size="md"
                          trackColor="#111312"
                          thumbColor="#534334"
                          activeTextColor="#edf2eb"
                          textColor="#a2aaa6"
                        />
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
                                const spec =
                                    descriptions[id] || fallbackDescription,
                                  on = deviceActive(id, d),
                                  m = home.metadata[id];
                                return (
                                  <AnimatedContent
                                    key={id}
                                    distance={reduce ? 0 : 16}
                                    duration={0.4}
                                    delay={index * 0.04}
                                    initialOpacity={reduce ? 1 : 0}
                                  >
                                    <SpotlightCard
                                      className={
                                        "device-card " +
                                        (on ? "is-on " : "is-off ") +
                                        (d[spec.alarm] ? "has-alarm" : "")
                                      }
                                      spotlightColor="rgba(166, 189, 165, 0.16)"
                                      intensity={0.12}
                                      borderGlow={0.3}
                                      grain={0}
                                      style={{
                                        "--spotlight-card-surface": "#111312",
                                        "--device-tint":
                                          {
                                            smart_plug_1: "143, 174, 140",
                                            light_1: "200, 164, 109",
                                            thermostat_1: "151, 171, 185",
                                            ventilation_1: "116, 170, 162",
                                          }[id] || "143,174,140",
                                      }}
                                    >
                                      <div className="device-card-top">
                                        <span className="device-top-room">
                                          <span
                                            className={
                                              "device-status-dot " +
                                              (on ? "active" : "")
                                            }
                                          />
                                          {m.room}
                                        </span>
                                        {spec.toggle ? (
                                          <Switch
                                            on={on}
                                            disabled={!online || !!pending[id]}
                                            label={
                                              (on
                                                ? "Выключить "
                                                : "Включить ") + m.name
                                            }
                                            onClick={() =>
                                              command(
                                                id,
                                                spec.toggle,
                                                on ? 0 : spec.on,
                                                false,
                                              )
                                            }
                                          />
                                        ) : (
                                          <span className="device-kind-label">
                                            {home.metadata[id].family ===
                                            "intercom"
                                              ? "Домофон"
                                              : "На связи"}
                                          </span>
                                        )}
                                      </div>
                                      <button
                                        className={
                                          "product-image " +
                                          (!on ? "device-off" : "")
                                        }
                                        onClick={() => setSelected(id)}
                                        aria-label={"Настроить " + m.name}
                                      >
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
                                                    spec.image === "lamp"
                                                      ? -2
                                                      : 0,
                                                }
                                          }
                                        />
                                      </button>
                                      <div className="device-room">
                                        <i className={on ? "lit" : ""} />
                                        {pending[id]
                                          ? "Обновление…"
                                          : operationStatus(id, d)}
                                        <span>
                                          {d.overload_alarm
                                            ? "Защита"
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
                                          {(id === "thermostat_1" ||
                                            id === "ventilation_1") && (
                                            <span className="device-reading-label">
                                              {id === "thermostat_1"
                                                ? "Температура в комнате"
                                                : "CO₂ в комнате"}
                                              {!on && (
                                                <span>
                                                  Последнее измерение · датчик
                                                  выключен
                                                </span>
                                              )}
                                            </span>
                                          )}
                                          <NumberValue
                                            value={d[spec.signal]}
                                            decimals={spec.decimals || 0}
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
                                  </AnimatedContent>
                                );
                              })
                          : Array.from({ length: 4 }, (_, i) => (
                              <div className="device-skeleton" key={i} />
                            ))}
                      </div>
                    </div>
                  </section>
                  <HomeStatistics home={home} online={online} />
                  <section className="lower-grid">
                    <div>
                      <div className="section-heading">
                        <h2>
                          Автоматизации{" "}
                          <span>
                            {home?.summary.active_scenarios ?? 0} активных
                          </span>
                        </h2>
                        <a href="#scenarios">
                          Все сценарии <ArrowUpRight size={14} />
                        </a>
                      </div>
                      <div className="automation-list">
                        {scenarios.length ? (
                          scenarios.map((s) => (
                            <div className="automation-row" key={s.id}>
                              <span className="automation-icon">
                                <Workflow size={20} />
                              </span>
                              <button
                                className="automation-name"
                                onClick={() => setEditor(s)}
                              >
                                <strong>{s.name}</strong>
                                <small>
                                  {s.enabled ? "Активен" : "Выключен"}
                                </small>
                              </button>
                              <Switch
                                on={s.enabled}
                                disabled={!online || !!pending[s.id]}
                                label={`Переключить ${s.name}`}
                                onClick={() => toggleScenario(s)}
                              />
                              <button
                                className="icon-button"
                                aria-label={`Настроить ${s.name}`}
                                onClick={() => setEditor(s)}
                              >
                                <ChevronRight size={18} />
                              </button>
                            </div>
                          ))
                        ) : (
                          <button
                            className="automation-empty"
                            disabled={!home}
                            onClick={() => setEditor({})}
                          >
                            <Plus size={22} />
                            <strong>Создайте первую автоматизацию</strong>
                            <span>Пусть устройства работают вместе</span>
                          </button>
                        )}
                      </div>
                    </div>
                    <div>
                      <div className="section-heading">
                        <h2>Последние события</h2>
                        <a href="#history">
                          История <ArrowUpRight size={14} />
                        </a>
                      </div>
                      <Activity
                        events={events}
                        metadata={home?.metadata}
                        short
                      />
                    </div>
                  </section>
                </div>
              </AnimatedContent>
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
                <div className="scenario-deck">
                  <CardSwap
                    ref={scenarioDeck}
                    width={460}
                    height={560}
                    cardDistance={40}
                    verticalDistance={40}
                    autoplay={false}
                    parallax={0.15}
                    skewAmount={2}
                    intro={!reduce}
                  >
                    {scenarios.map((s) => (
                      <Card key={s.id} className="scenario-card">
                        <img
                          className="scenario-preview"
                          src={`${base}images/${s.id === "overload_protection" ? "scenario-overload.png" : `${descriptions[s.when.device]?.image || "plug"}.webp`}`}
                          alt={`Превью сценария «${s.name}»`}
                        />
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
                      </Card>
                    ))}
                    <button
                      className="add-scenario"
                      disabled={!home}
                      onClick={() => setEditor({})}
                    >
                      <Plus size={28} />
                      <span>Создать сценарий</span>
                    </button>
                  </CardSwap>
                  <div className="scenario-deck-controls">
                    <span>
                      {scenarios.length} сценариев · листайте карточки
                    </span>
                    <button
                      className="secondary"
                      onClick={() => scenarioDeck.current?.prev()}
                    >
                      Назад
                    </button>
                    <button
                      className="secondary"
                      onClick={() => scenarioDeck.current?.next()}
                    >
                      Далее
                    </button>
                  </div>
                </div>
              </>
            )}
            {page === "history" && (
              <>
                <section className="page-intro">
                  <div>
                    <span className="home-location">Всегда в курсе</span>
                    <h1>Жизнь вашего дома.</h1>
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
        <span className="footer-brand">UjinFizteha</span>
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
            busy={!!pending[selected]}
            online={online}
          />
        </Modal>
      )}
      {editor && home && (
        <ScenarioSheet
          item={editor}
          home={home}
          declarations={declarations}
          onClose={() => setEditor(null)}
          onSave={async (s) => {
            await api("/api/scenarios", s);
            setEditor(null);
            refresh();
            notify("Сценарий сохранён");
          }}
        />
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
              {home ? Object.keys(home.devices).length : "—"} эмуляторов
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
              ["kitchen", "Кухня", "Чайник и конфорка включены.", FlaskConical],
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
