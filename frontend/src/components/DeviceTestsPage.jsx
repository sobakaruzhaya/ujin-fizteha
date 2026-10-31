import { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  Check,
  ChevronDown,
  FlaskConical,
  Flame,
  LoaderCircle,
  Play,
  RotateCcw,
  Square,
  X,
} from "lucide-react";
import { descriptions, fallbackDescription } from "./deviceCatalog";
import "./DeviceTestsPage.css";
import { useNotifications } from "./Notifications";
import TestPlayback from "./TestPlayback";

const names = {
  idle: "Не проверено",
  running: "Проверяем…",
  passed: "Пройден",
  failed: "Ошибка",
  unsupported: "Нет проверки",
};
const show = (value) =>
  typeof value === "boolean" ? (value ? "Да" : "Нет") : String(value ?? "—");
async function request(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw Error(data.error || "Не удалось выполнить проверку");
  return data;
}

export default function DeviceTestsPage() {
  const [mode, setMode] = useState("emergency");
  return (
    <>
      <div className="tests-mode-tabs" role="group" aria-label="Тип тестирования">
        <button aria-pressed={mode === "emergency"} onClick={() => setMode("emergency")}>Аварийные ситуации</button>
        <button aria-pressed={mode === "devices"} onClick={() => setMode("devices")}>Диагностика устройств</button>
      </div>
      <ChecksPage key={mode} emergency={mode === "emergency"} />
    </>
  );
}

function SensorReaction({ result }) {
  return (
    <details className="test-check-details test-sensor-reaction">
      <summary>Реакция датчиков <ChevronDown size={15} /></summary>
      <div className="test-reaction-timeline">
        {result.timeline.map((stage, i) => (
          <section className="test-reaction-stage" key={i}>
            <h3>{stage.title}<span>{stage.seconds} с</span></h3>
            <dl>{stage.readings.map((r) => (
              <div key={`${r.device}.${r.signal}`}>
                <dt>{r.title}<small>{r.source}</small></dt>
                <dd>{r.label || show(r.value)}{!r.label && r.measure ? ` ${r.measure}` : ""}</dd>
              </div>
            ))}</dl>
          </section>
        ))}
      </div>
      {result.rules.length > 0 && <p className="test-stand-rules">Правила стенда: {result.rules.join("; ")}</p>}
      {result.events.some((e) => e.type === "scenario_triggered") && (
        <ul>{result.events.filter((e) => e.type === "scenario_triggered").map((event) => (
          <li key={event.id}><Check size={15} /><span>{event.message}</span></li>
        ))}</ul>
      )}
    </details>
  );
}

function ChecksPage({ emergency }) {
  const publish = useNotifications();
  const endpoint = emergency ? "/api/emergency-tests" : "/api/device-tests";
  const [catalog, setCatalog] = useState([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [results, setResults] = useState({}),
    [running, setRunning] = useState(null),
    [filter, setFilter] = useState("all");
  const controller = useRef(null),
    runLock = useRef(false),
    mounted = useRef(true);
  const [runInfo, setRunInfo] = useState(null);
  const [playback, setPlayback] = useState(null), [speed, setSpeed] = useState(1);
  const playbackView = useRef(null);
  useEffect(() => {
    if (playback) playbackView.current?.scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
      block: "start",
    });
  }, [playback?.key]);
  function viewResult(result, abort) {
    return new Promise((resolve) => {
      const finish = () => { abort?.signal.removeEventListener("abort", finish); resolve(); };
      if (abort?.signal.aborted) return finish();
      abort?.signal.addEventListener("abort", finish, { once: true });
      setPlayback({ result, key: crypto.randomUUID(), signal: abort?.signal, onFinished: finish });
    });
  }
  function load() {
    const abort = new AbortController();
    setLoading(true);
    setError("");
    setPlayback(null);
    request(endpoint, { signal: abort.signal })
      .then((data) => {
        if (mounted.current) setCatalog(emergency ? data.tests : data.devices);
      })
      .catch((e) => {
        if (mounted.current && !abort.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (mounted.current) setLoading(false);
      });
    return abort;
  }
  useEffect(() => {
    mounted.current = true;
    const abort = load();
    return () => {
      mounted.current = false;
      abort.abort();
      controller.current?.abort();
    };
  }, []);
  const tested = Object.values(results).filter(
    (r) => r.status === "passed" || r.status === "failed",
  );
  const passed = tested.filter((r) => r.status === "passed").length,
    failed = tested.filter((r) => r.status === "failed").length;
  async function run(ids) {
    if (runLock.current) return;
    runLock.current = true;
    const abort = new AbortController();
    controller.current = abort;
    const selected = new Set(ids);
    setResults((old) =>
      Object.fromEntries(
        Object.entries(old).filter(([id]) => !selected.has(id)),
      ),
    );
    let done = 0,
      stopped = false;
    setError("");
    setPlayback(null);
    setRunInfo({ done: 0, total: ids.length, state: "running" });
    try {
      for (const id of ids) {
        if (abort.signal.aborted) break;
        setRunning(id);
        try {
          const report = await request(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(emergency ? { case: id } : { device: id }),
            signal: AbortSignal.any([abort.signal, AbortSignal.timeout(15000)]),
          });
          const result = report.results.find((r) => (r.id || r.device) === id);
          if (!result) throw Error("Сервер вернул неполный результат проверки");
          if (!mounted.current) return;
          setResults((old) => ({
            ...old,
            [id]: { ...result, finished_at: report.finished_at },
          }));
          if (result.trace?.length) {
            await viewResult(result, abort);
            if (!mounted.current || abort.signal.aborted) break;
          }
          const name = catalog.find((c) => c.id === id)?.name || result.name;
          const failures = result.checks.filter((c) => !c.passed);
          const reactions = result.checks.filter((c) => c.passed).slice(0, 2);
          publish({
            key: `test:${report.id}:${id}`,
            scope: emergency ? "Тестовый стенд" : "Диагностика",
            kind: result.status === "passed" ? "success" : "error",
            title: `${name}: ${result.status === "passed" ? "проверка пройдена" : "ошибка проверки"}`,
            description: result.status === "passed"
              ? reactions.map((c) => c.title).join(". ") + ` (${result.checks.length} проверок)`
              : failures.map((c) => c.error || c.title).slice(0, 2).join(". "),
          });
        } catch (e) {
          if (!mounted.current || abort.signal.aborted) break;
          setResults((old) => ({
            ...old,
            [id]: {
              id,
              status: "failed",
              checks: [],
              error: e.message,
              finished_at: Date.now() / 1000,
            },
          }));
          publish({ kind: "error", scope: emergency ? "Тестовый стенд" : "Диагностика", title: "Не удалось выполнить проверку", description: e.message });
        }
        done++;
        setRunInfo({ done, total: ids.length, state: "running" });
      }
      stopped = abort.signal.aborted;
    } finally {
      runLock.current = false;
      if (mounted.current) {
        setRunning(null);
        setRunInfo({
          done,
          total: ids.length,
          state: stopped || abort.signal.aborted ? "stopped" : "finished",
        });
      }
    }
  }
  function download() {
    const blob = new Blob(
      [
        JSON.stringify(
          {
            mode: "isolated",
            type: emergency ? "emergency" : "device-diagnostics",
            exported_at: new Date().toISOString(),
            results: Object.values(results),
          },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob),
      link = document.createElement("a");
    link.href = url;
    link.download = emergency ? "ujinfizteha-emergency-tests.json" : "ujinfizteha-device-tests.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const visible = catalog.filter(
    (d) =>
      filter === "all" ||
      (filter === "idle" ? !results[d.id] : results[d.id]?.status === filter),
  );
  return (
    <div className="device-tests-page">
      <section className="tests-intro">
        <div>
          <span className="home-location">
            <FlaskConical size={15} /> Лаборатория
          </span>
          <h1>{emergency ? "Аварийные тесты" : "Тесты устройств"}</h1>
          <p>{emergency ? "Смоделируйте аварию и посмотрите, как реагируют датчики и защиты." : "Проверьте работу, показания и защиту каждого эмулятора."}</p>
        </div>
        <div className="tests-main-actions">
          {running ? (
            <button
              className="secondary"
              onClick={() => controller.current?.abort()}
            >
              <Square size={16} />
              Остановить
            </button>
          ) : (
            <button
              className="primary"
              disabled={loading || !catalog.some((d) => d.supported)}
              onClick={() =>
                run(catalog.filter((d) => d.supported).map((d) => d.id))
              }
            >
              <Play size={17} />
              Запустить все тесты
            </button>
          )}
          <button
            className="secondary"
            disabled={!tested.length || !!running}
            onClick={download}
          >
            <ArrowDownToLine size={16} />
            Отчёт
          </button>
        </div>
      </section>
      <div className="tests-mode-note">
        <FlaskConical size={19} />
        <div>
          <strong>Изолированные проверки</strong>
          <span>
            {emergency
              ? "Аварии моделируются на отдельном стенде. Проверяем встроенные защиты и явно указанные тестовые правила. Показания до события, реакция и восстановление доступны в результатах. Устройства дома и сохранённые сценарии не изменяются."
              : "Команды выполняются на отдельных экземплярах настоящих эмуляторов со стандартными настройками. Устройства дома и сохранённые сценарии не изменяются."}
          </span>
        </div>
      </div>
      <div className="tests-summary">
        <div>
          <span>{emergency ? "Аварийных тестов" : "Устройств"}</span>
          <strong>{loading ? "—" : catalog.length}</strong>
        </div>
        <div>
          <span>Пройдено</span>
          <strong>{passed}</strong>
        </div>
        <div className={failed ? "has-failures" : ""}>
          <span>Ошибок</span>
          <strong>{failed}</strong>
        </div>
        <div>
          <span>Не проверено</span>
          <strong>{Math.max(0, catalog.length - tested.length)}</strong>
        </div>
      </div>
      {runInfo && (
        <div className="tests-progress" role="status">
          <div>
            <span>
              {runInfo.state === "running"
                ? "Выполняем проверки"
                : runInfo.state === "stopped"
                  ? "Проверка остановлена"
                  : "Проверка завершена"}
            </span>
            <strong>
              {runInfo.done} / {runInfo.total}
            </strong>
          </div>
          <progress
            max={runInfo.total}
            value={runInfo.done}
            aria-label="Прогресс тестирования"
          />
        </div>
      )}
      {playback && <div ref={playbackView}>
        <TestPlayback key={playback.key} {...playback} speed={speed} onSpeedChange={setSpeed} />
      </div>}
      <div className="tests-toolbar">
        <div
          className="tests-filters"
          role="group"
          aria-label="Результаты тестов"
        >
          {[
            ["all", "Все"],
            ["idle", "Не проверены"],
            ["passed", "Пройдены"],
            ["failed", "Ошибки"],
          ].map(([id, label]) => (
            <button
              key={id}
              aria-pressed={filter === id}
              onClick={() => setFilter(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          className="text-button"
          disabled={!tested.length || !!running}
          onClick={() => {
            setResults({});
            setRunInfo(null);
            setPlayback(null);
          }}
        >
          <RotateCcw size={14} />
          Сбросить результаты
        </button>
      </div>
      {loading && (
        <div className="tests-empty" role="status">
          <LoaderCircle className="animate-spin" size={24} />
          {emergency ? "Загружаем аварийные тесты…" : "Загружаем устройства…"}
        </div>
      )}
      {error && (
        <div className="tests-empty" role="alert">
          <p>{error}</p>
          <button className="secondary" onClick={load}>
            Повторить загрузку
          </button>
        </div>
      )}
      {!loading && !error && !visible.length && (
        <div className="tests-empty">
          {catalog.length
            ? (emergency ? "Нет тестов с таким результатом" : "Нет устройств с таким результатом")
            : "В доме пока нет доступных устройств"}
        </div>
      )}
      <div className="tests-device-grid">
        {visible.map((d) => {
          const result = results[d.id],
            status = running === d.id ? "running" : result?.status || "idle";
          const spec = descriptions[d.id] || fallbackDescription;
          const picture = emergency ? d.image : spec.image;
          return (
            <article
              className={"test-device-card status-" + status}
              key={d.id}
              aria-label={d.name}
              aria-busy={status === "running"}
            >
              <div className="test-device-heading">
                {picture ? <img
                  src={`${import.meta.env.BASE_URL}images/${picture}.webp`}
                  alt=""
                /> : <div className="test-case-symbol" aria-hidden="true"><Flame size={30} /></div>}
                <div>
                  <span>{emergency ? d.category : d.room}</span>
                  <h2>{d.name}</h2>
                </div>
                <span className={"test-result-badge " + status}>
                  {status === "passed" ? (
                    <Check size={13} />
                  ) : status === "failed" ? (
                    <X size={13} />
                  ) : status === "running" ? (
                    <LoaderCircle className="animate-spin" size={13} />
                  ) : null}
                  {names[status]}
                </span>
              </div>
              <p className="test-description">{d.description}</p>
              {emergency && (
                <div className="test-case-expectation">
                  <strong>Ожидаемая реакция</strong><p>{d.expected}</p>
                  <span>{d.mechanism}</span>
                  {d.note && <p className="test-case-note">{d.note}</p>}
                </div>
              )}
              <div className="test-device-actions">
                <button
                  className="secondary"
                  disabled={!!running || !d.supported}
                  onClick={() => run([d.id])}
                >
                  {status === "running" ? (
                    <LoaderCircle className="animate-spin" size={15} />
                  ) : (
                    <Play size={15} />
                  )}{" "}
                  {status === "running"
                    ? "Проверяем…"
                    : result
                      ? "Повторить тест"
                      : "Запустить тест"}
                </button>
                {result && (
                  <span>
                    {result.checks.filter((c) => c.passed).length} /{" "}
                    {result.checks.length} проверок
                  </span>
                )}
              </div>
              {result?.error && (
                <p className="test-error" role="alert">
                  {result.error}
                </p>
              )}
              {result?.trace?.length > 0 && <button className="test-view-trace" disabled={!!running} onClick={() => viewResult(result)}>
                <Play size={15} /> Посмотреть ход теста
              </button>}
              {result?.timeline?.length > 0 && <SensorReaction result={result} />}
              {result?.checks.length > 0 && (
                <details
                  className="test-check-details"
                  open={result.status === "failed"}
                >
                  <summary>
                    Результаты проверки
                    <ChevronDown size={15} />
                  </summary>
                  <ul>
                    {result.checks.map((check, i) => (
                      <li
                        key={i}
                        className={
                          check.passed ? "check-passed" : "check-failed"
                        }
                      >
                        {check.passed ? <Check size={15} /> : <X size={15} />}
                        <div>
                          <strong>{check.title}</strong>
                          {check.source && <span>{check.source} · {check.signal_title}</span>}
                          <span>
                            {check.error ||
                              `Ожидание: ${check.comparison === "==" ? "" : check.comparison + " "}${show(check.expected)}${check.measure ? " " + check.measure : ""} · Получено: ${show(check.actual)}${check.measure ? " " + check.measure : ""}`}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              {result && (
                <div className="test-finished-at">
                  {new Date(result.finished_at * 1000).toLocaleTimeString(
                    "ru-RU",
                  )}
                  <span>
                    {result.duration_ms !== undefined
                      ? `${result.duration_ms} мс${result.simulated_seconds != null ? ` · модель ${result.simulated_seconds} с` : ""}`
                      : ""}
                  </span>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
