import { useEffect, useId, useMemo, useState } from "react";
import { useReducedMotion } from "motion/react";
import {
  Activity,
  ArrowUpRight,
  Leaf,
  PlugZap,
  Workflow,
  Zap,
} from "lucide-react";
import MagicBento from "./reactbits/MagicBento";
import "./HomeStatistics.css";
import {deviceActive} from './deviceCatalog';

const number = (value, digits = 0) =>
  Number(value).toLocaleString("ru-RU", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
function PowerChart({ history, status }) {
  const id = useId().replace(/:/g, "");
  if (!history.length)
    return (
      <div className="stats-chart-empty">
        {status === "error"
          ? "История пока недоступна"
          : status === "loading"
            ? "Загружаем показания…"
            : "График появится после первых измерений"}
      </div>
    );
  const ceiling = Math.max(1, ...history.map((p) => p.power_w)) * 1.15;
  const first = history[0].time,
    last = history.at(-1).time,
    span = Math.max(1, last - first);
  const points = history.map(
    (p) =>
      `${8 + ((p.time - first) / span) * 584},${152 - (p.power_w / ceiling) * 140}`,
  );
  const line = `M ${points.join(" L ")}`;
  return (
    <div className="stats-chart">
      <svg
        viewBox="0 0 600 160"
        preserveAspectRatio="none"
        role="img"
        aria-label={`Мощность дома: от ${number(history[0].power_w)} до ${number(history.at(-1).power_w)} ватт за ${Math.round(last - first)} секунд`}
      >
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#edac82" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#edac82" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[12, 82, 152].map((y) => (
          <line
            key={y}
            x1="8"
            y1={y}
            x2="592"
            y2={y}
            stroke="currentColor"
            strokeDasharray="3 6"
          />
        ))}
        <path
          d={`${line} L ${8 + ((last - first) / span) * 584},152 L 8,152 Z`}
          fill={`url(#${id})`}
        />
        <path
          d={line}
          fill="none"
          stroke="#edac82"
          strokeWidth="2.5"
          vectorEffect="non-scaling-stroke"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <circle
          cx={8 + ((last - first) / span) * 584}
          cy={152 - (history.at(-1).power_w / ceiling) * 140}
          r="3"
          fill="#edac82"
        />
      </svg>
      <div className="stats-chart-times">
        <span>
          {new Date(first * 1000).toLocaleTimeString("ru-RU", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })}
        </span>
        <span>
          {status === "error" ? "Последние полученные данные" : "Сейчас"}
        </span>
      </div>
    </div>
  );
}

export default function HomeStatistics({ home, online }) {
  const [history, setHistory] = useState([]),
    [status, setStatus] = useState("loading");
  const reduce = useReducedMotion();
  useEffect(() => {
    let live = true,
      busy = false;
    const controller = new AbortController();
    const refresh = async () => {
      if (busy || document.hidden) return;
      busy = true;
      try {
        const response = await fetch("/api/history", {
          signal: AbortSignal.any([
            controller.signal,
            AbortSignal.timeout(8000),
          ]),
        });
        if (!response.ok) throw Error("history");
        const data = await response.json();
        if (live) {
          setHistory(
            data
              .filter(
                (p) => Number.isFinite(p.time) && Number.isFinite(p.power_w),
              )
              .slice(-300),
          );
          setStatus("ready");
        }
      } catch {
        if (live) setStatus("error");
      } finally {
        busy = false;
      }
    };
    void refresh();
    const timer = setInterval(refresh, 3000);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      live = false;
      controller.abort();
      clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, []);
  const items = useMemo(() => {
    if (!home) return [];
    const devices = Object.entries(home.devices);
    const on = devices.filter(
      ([id,d]) => deviceActive(id,d),
    ).length;
    const peak = history.length
      ? Math.max(...history.map((p) => p.power_w))
      : null;
    const average = history.length
      ? history.reduce((sum, p) => sum + p.power_w, 0) / history.length
      : null;
    const header = (Icon, title) => (
      <div className="stats-card-heading">
        <Icon size={18} />
        <h3>{title}</h3>
      </div>
    );
    const climate = devices.filter(([, d]) => "temperature" in d || "co2" in d);
    return [
      {
        id: "power",
        colSpan: 2,
        rowSpan: 2,
        content: (
          <div className="stats-power-card">
            {header(Activity, "Потребление дома")}
            <div className="stats-large-number">
              {number(home.summary.power_w, 1)}
              <small>Вт сейчас</small>
            </div>
            <div className="stats-power-summary">
              <span>
                Среднее{" "}
                <strong>
                  {average === null ? "—" : `${number(average, 1)} Вт`}
                </strong>
              </span>
              <span>
                Пик{" "}
                <strong>{peak === null ? "—" : `${number(peak, 1)} Вт`}</strong>
              </span>
              <span>До 5 минут истории</span>
            </div>
            <PowerChart history={history} status={status} />
          </div>
        ),
      },
      {
        id: "energy",
        content: (
          <>
            {header(Zap, "Энергия за сеанс")}
            <div className="stats-number">
              {number(home.summary.energy_kwh, 4)}
              <small>кВт·ч</small>
            </div>
            <p>С момента запуска сервера</p>
          </>
        ),
      },
      {
        id: "devices",
        content: (
          <>
            {header(PlugZap, "Устройства включены")}
            <div className="stats-number">
              {on}
              <small>из {devices.length}</small>
            </div>
            <p>По текущему состоянию устройств</p>
          </>
        ),
      },
      {
        id: "scenarios",
        href: "#scenarios",
        content: (
          <>
            {header(Workflow, "Активные сценарии")}
            <div className="stats-number">
              {home.summary.active_scenarios}
              <ArrowUpRight size={20} />
            </div>
            <p>Перейти к автоматизациям</p>
          </>
        ),
      },
      {
        id: "climate",
        content: (
          <>
            {header(Leaf, "Климат дома")}
            <div className="stats-climate">
              {climate.map(([id, d]) => (
                <div key={id}>
                  <strong>
                    {"co2" in d
                      ? `${number(d.co2)} ppm`
                      : `${number(d.temperature, 1)} °C`}
                  </strong>
                  <span>
                    {home.metadata[id]?.room}
                    {"co2" in d ? " · CO₂" : " · температура"}
                    {'mode' in d && !d.mode && ' · последнее измерение'}
                  </span>
                </div>
              ))}
            </div>
            {!climate.length && <p>Нет доступных показаний</p>}
          </>
        ),
      },
    ];
  }, [home, history, status]);
  return (
    <section
      className="home-statistics"
      aria-labelledby="home-statistics-title"
    >
      <div className="section-heading">
        <h2 id="home-statistics-title">Статистика дома</h2>
        <span className="stats-update">
          {!online
            ? "Нет связи · последние данные"
            : status === "error"
              ? "История временно недоступна"
              : "Обновляется автоматически"}
        </span>
      </div>
      {home ? (
        <MagicBento
          items={items}
          columns={4}
          rowHeight={174}
          gap={16}
          radius={22}
          glowColor="237, 172, 130"
          textAutoHide={false}
          enableStars={false}
          enableTilt={false}
          enableMagnetism={false}
          clickEffect={false}
          intro={!reduce}
          disableAnimations={reduce}
          className="stats-bento"
        />
      ) : (
        <div className="stats-loading" role="status">
          Ожидаем данные дома…
        </div>
      )}
    </section>
  );
}
