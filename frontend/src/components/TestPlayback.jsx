import { useEffect, useId, useRef, useState } from "react";
import { Activity, AlertTriangle, Check, Pause, Play, RotateCcw, SkipForward } from "lucide-react";
import "./TestPlayback.css";

const keyOf = (reading) => `${reading.device}.${reading.signal}`;
const number = (value, measure) => new Intl.NumberFormat("ru-RU", {
  maximumFractionDigits: measure === "кВт·ч" ? 6 : 2,
}).format(value);
const alarmSignals = new Set(["overload_alarm", "alarm", "leak", "dry_boil", "fault", "siren"]);

function TraceChart({ frames, cursor, primary, secondary, threshold }) {
  const clip = useId().replaceAll(":", "");
  const svg = useRef(null), [width, setWidth] = useState(800);
  useEffect(() => {
    const resize = new ResizeObserver(([entry]) => setWidth(Math.max(280, Math.round(entry.contentRect.width))));
    resize.observe(svg.current);
    return () => resize.disconnect();
  }, []);
  const height = 260, left = 56, right = 22, top = 28, bottom = 35;
  const get = (frame, signal) => frame.readings.find((r) => keyOf(r) === signal);
  const readings = frames.flatMap((f) => [get(f, primary), ...(secondary ? [get(f, secondary)] : [])]);
  const values = readings.map((r) => Number(r?.value)).filter(Number.isFinite);
  const maximum = readings[0]?.discrete ? 1 : Math.max(...values, threshold?.value ?? 0, 1) * 1.13;
  const minimum = Math.min(0, ...values);
  const x = (i) => left + i / Math.max(1, frames.length - 1) * (width - left - right);
  const y = (value) => top + (maximum - value) / (maximum - minimum) * (height - top - bottom);
  const path = (signal) => {
    let previous = null;
    return frames.slice(0, cursor + 1).map((frame, i) => {
      const value = get(frame, signal)?.value;
      if (!Number.isFinite(value)) return "";
      const point = previous === null ? `M ${x(i)} ${y(value)}` : `H ${x(i)} V ${y(value)}`;
      previous = value;
      return point;
    }).join(" ");
  };
  const current = get(frames[cursor], primary);
  return (
    <svg ref={svg} className="test-trace-chart" viewBox={`0 0 ${width} ${height}`} role="img"
      aria-label={`График: ${current?.title}. Показания тестового стенда по шагам.`}>
      <defs><clipPath id={clip}><rect x={left} y={top - 4} width={width - left - right + 3} height={height - top - bottom + 8} /></clipPath></defs>
      {[0, 0.5, 1].map((ratio) => {
        const value = minimum + (maximum - minimum) * ratio;
        return <g key={ratio} className="trace-grid">
          <line x1={left} x2={width - right} y1={y(value)} y2={y(value)} />
          <text x={left - 10} y={y(value) + 4} textAnchor="end">{current?.discrete ? (ratio === 0 ? "0" : ratio === 1 ? "1" : "") : number(value)}</text>
        </g>;
      })}
      {threshold && <g className={threshold.target ? "trace-threshold target" : "trace-threshold"}>
        <line x1={left} x2={width - right} y1={y(threshold.value)} y2={y(threshold.value)} />
        <text x={width - right} y={y(threshold.value) - 8} textAnchor="end">{threshold.title} · {number(threshold.value)} {current?.measure}</text>
      </g>}
      <g clipPath={`url(#${clip})`}>
        {secondary && <path className="trace-line trace-secondary" d={path(secondary)} />}
        <path className="trace-line" d={path(primary)} />
        <line className="trace-cursor" x1={x(cursor)} x2={x(cursor)} y1={top} y2={height - bottom} />
        {current && <circle className="trace-dot" cx={x(cursor)} cy={y(current.value)} r={5} />}
      </g>
      <g className="trace-axis">
        <text x={left} y={height - 7}>Шаг 1 · {frames[0].seconds} с</text>
        <text x={width - right} y={height - 7} textAnchor="end">Шаг {frames.length} · {frames.at(-1).seconds} с</text>
      </g>
    </svg>
  );
}

export default function TestPlayback({ result, signal, onFinished, speed, onSpeedChange }) {
  const frames = result.trace?.length ? result.trace : result.timeline;
  const [cursor, setCursor] = useState(0), [playing, setPlaying] = useState(true);
  const completed = useRef(false), finishRef = useRef(onFinished);
  finishRef.current = onFinished;
  const last = frames.length - 1;
  const config = result.visualization || {};
  const frame = frames[cursor];
  const primaryKey = (config.primary || [frame.readings[0].device, frame.readings[0].signal]).join(".");
  const primary = frame.readings.find((r) => keyOf(r) === primaryKey);
  const secondaryKey = config.secondary?.join(".");
  const secondary = frame.readings.find((r) => keyOf(r) === secondaryKey);
  const activeAlarms = frame.readings.filter((r) => alarmSignals.has(r.signal) && r.value);
  const alarm = activeAlarms.length > 0;
  const overLimit = config.threshold && !config.threshold.target && primary.value > config.threshold.value;
  const duration = Math.max(4500, Math.min(8500, frames.length * 260));
  function finish() {
    if (!completed.current) { completed.current = true; finishRef.current?.(); }
  }
  useEffect(() => {
    if (!playing) return;
    if (cursor >= last) { setPlaying(false); finish(); return; }
    const timer = setTimeout(() => setCursor((value) => Math.min(value + 1, last)), duration / Math.max(1, last) / speed);
    return () => clearTimeout(timer);
  }, [cursor, playing, speed, duration, last]);
  useEffect(() => {
    const stop = () => { setPlaying(false); finish(); };
    if (signal?.aborted) stop();
    signal?.addEventListener("abort", stop, { once: true });
    return () => signal?.removeEventListener("abort", stop);
  }, [signal]);
  function seek(index) { setPlaying(false); setCursor(index); if (index === last) finish(); }
  const milestones = result.timeline || [];
  return (
    <section className={`test-playback ${alarm || overLimit ? "has-alarm" : ""}`} aria-label={`Визуализация: ${result.name}`}>
      <div className="playback-heading">
        <div><span className="playback-eyebrow"><Activity size={15} /> Ход теста · изолированный стенд</span><h2>{result.name}</h2></div>
        <span className={`playback-state ${alarm ? "alarm" : ""}`}>
          {alarm ? <AlertTriangle size={16} /> : <Check size={16} />}
          {alarm ? "Датчик сообщает о тревоге" : overLimit ? "Порог превышен" : "Тревоги нет"}
        </span>
      </div>
      <p className="playback-explanation">Воспроизведение записанных показаний эмуляторов. Устройства дома не изменяются.</p>
      <div className="playback-body">
        <div className="playback-measurement">
          <div className="playback-main-reading" data-signal={primaryKey}>
            <span>{primary.title}</span>
            <strong>{primary.discrete ? primary.label || primary.value : number(primary.value, primary.measure)}<small>{!primary.discrete && primary.measure}</small></strong>
            <span>{primary.source} · {frame.seconds} с на стенде</span>
          </div>
          <div className="playback-legend"><span><i />{primary.title}</span>{secondary && <span><i className="legend-secondary" />{secondary.title}</span>}</div>
          <TraceChart frames={frames} cursor={cursor} primary={primaryKey} secondary={secondaryKey} threshold={config.threshold} />
          <div className="playback-phase"><span className="playback-pulse" /><div><strong>{frame.title}</strong><span>{frame.event || "Записанный отсчёт эмуляторов"}</span></div></div>
        </div>
        <div className="playback-readings" aria-label="Показания и реакция устройств">
          {frame.readings.filter((r) => keyOf(r) !== primaryKey).map((reading) => {
            const danger = alarmSignals.has(reading.signal) && !!reading.value;
            return <div className={`playback-reading ${danger ? "alarm" : ""}`} key={keyOf(reading)} data-signal={keyOf(reading)}>
              <span>{reading.title}<small>{reading.source}</small></span>
              <strong>{reading.label || number(reading.value, reading.measure)}{!reading.label && reading.measure && <small>{reading.measure}</small>}</strong>
            </div>;
          })}
        </div>
      </div>
      <div className="playback-controls">
        <button className="secondary" aria-label={playing ? "Пауза воспроизведения" : "Продолжить воспроизведение"} onClick={() => {
          if (cursor >= last) setCursor(0);
          setPlaying(!playing);
        }}>{playing ? <Pause size={17} /> : <Play size={17} />}{playing ? "Пауза" : "Продолжить"}</button>
        <button className="playback-icon-button" aria-label="Воспроизвести сначала" onClick={() => { setCursor(0); setPlaying(true); }}><RotateCcw size={17} /></button>
        <label className="playback-scrubber"><span>Шаг {cursor + 1} / {frames.length}</span><input type="range" min={0} max={last} step={1} value={cursor} aria-label="Шаг записи теста" onChange={(e) => seek(Number(e.target.value))} /></label>
        <label className="playback-speed"><span>Скорость</span><select value={speed} aria-label="Скорость воспроизведения" onChange={(e) => onSpeedChange(Number(e.target.value))}><option value={0.5}>0,5×</option><option value={1}>1×</option><option value={2}>2×</option><option value={4}>4×</option></select></label>
        <button className="playback-icon-button" aria-label="Перейти к концу записи" onClick={() => { seek(last); finish(); }}><SkipForward size={18} /></button>
      </div>
      <div className="playback-milestones" aria-label="Этапы теста">
        {milestones.map((stage, i) => {
          const index = stage.frame ?? frames.findIndex((f) => f.title === stage.title);
          return <button key={i} className={cursor >= index ? "visited" : ""} onClick={() => seek(Math.max(0, index))} aria-label={`Этап: ${stage.title}`}><span>{String(i + 1).padStart(2, "0")}</span>{stage.title}<small>{stage.seconds} с</small></button>;
        })}
      </div>
      {cursor === last && <div className={`playback-verdict ${result.status === "passed" ? "" : "failed"}`} role="status">{result.status === "passed" ? <Check size={16} /> : <AlertTriangle size={16} />}{result.status === "passed" ? "Проверка пройдена" : "Обнаружены ошибки проверки"} · {result.checks.filter((c) => c.passed).length} / {result.checks.length} проверок</div>}
    </section>
  );
}
