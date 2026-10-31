import { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  Check,
  ChevronDown,
  FlaskConical,
  LoaderCircle,
  Play,
  RotateCcw,
  Square,
  X,
} from "lucide-react";
import { descriptions, fallbackDescription } from "./deviceCatalog";
import "./DeviceTestsPage.css";

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
  function load() {
    const abort = new AbortController();
    setLoading(true);
    setError("");
    request("/api/device-tests", { signal: abort.signal })
      .then((data) => {
        if (mounted.current) setCatalog(data.devices);
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
    setRunInfo({ done: 0, total: ids.length, state: "running" });
    try {
      for (const id of ids) {
        if (abort.signal.aborted) break;
        setRunning(id);
        try {
          const report = await request("/api/device-tests", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ device: id }),
            signal: AbortSignal.any([abort.signal, AbortSignal.timeout(15000)]),
          });
          const result = report.results.find((r) => r.device === id);
          if (!result) throw Error("Сервер вернул неполный результат проверки");
          if (!mounted.current) return;
          setResults((old) => ({
            ...old,
            [id]: { ...result, finished_at: report.finished_at },
          }));
        } catch (e) {
          if (!mounted.current || abort.signal.aborted) break;
          setResults((old) => ({
            ...old,
            [id]: {
              device: id,
              status: "failed",
              checks: [],
              error: e.message,
              finished_at: Date.now() / 1000,
            },
          }));
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
    link.download = "ujinfizteha-device-tests.json";
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
          <h1>Тесты устройств</h1>
          <p>Проверьте работу, показания и защиту каждого эмулятора.</p>
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
            Команды выполняются на отдельных экземплярах настоящих эмуляторов со
            стандартными настройками. Устройства дома и сохранённые сценарии не
            изменяются.
          </span>
        </div>
      </div>
      <div className="tests-summary">
        <div>
          <span>Устройств</span>
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
          }}
        >
          <RotateCcw size={14} />
          Сбросить результаты
        </button>
      </div>
      {loading && (
        <div className="tests-empty" role="status">
          <LoaderCircle className="animate-spin" size={24} />
          Загружаем устройства…
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
            ? "Нет устройств с таким результатом"
            : "В доме пока нет доступных устройств"}
        </div>
      )}
      <div className="tests-device-grid">
        {visible.map((d) => {
          const result = results[d.id],
            status = running === d.id ? "running" : result?.status || "idle";
          const spec = descriptions[d.id] || fallbackDescription;
          return (
            <article
              className={"test-device-card status-" + status}
              key={d.id}
              aria-label={d.name}
              aria-busy={status === "running"}
            >
              <div className="test-device-heading">
                <img
                  src={`${import.meta.env.BASE_URL}images/${spec.image}.webp`}
                  alt=""
                />
                <div>
                  <span>{d.room}</span>
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
                          <span>
                            {check.error ||
                              `Ожидание: ${check.comparison === "==" ? "" : check.comparison + " "}${show(check.expected)} · Получено: ${show(check.actual)}`}
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
                      ? `${result.duration_ms} мс`
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
