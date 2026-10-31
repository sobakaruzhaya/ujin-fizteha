import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Link2, LoaderCircle, RefreshCw, Square } from "lucide-react";
import { useNotifications } from "./Notifications";
import "./UjinIntegration.css";

const labels = { idle: "Не подключено", connecting: "Подключение…", connected: "Подключено", error: "Ошибка обмена", stopping: "Остановка…", stopped: "Остановлено" };
const deviceStates = { connected: "Доступно", read_only: "Команды недоступны", unmapped: "Нет локального устройства", no_signals: "Нет сопоставленных сигналов", error: "Ошибка чтения", unverified: "Доставка не подтверждена" };

export default function UjinIntegration() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);
  const publish = useNotifications();
  async function load(signal) {
    try {
      const response = await fetch("/api/integrations/ujin", { signal });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || "Не удалось получить состояние Ujin");
      if (mounted.current) { setStatus(data); setError(""); }
    } catch (e) { if (mounted.current && !signal?.aborted) setError(e.message); }
  }
  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    void load(controller.signal);
    const timer = setInterval(() => void load(controller.signal), 3000);
    return () => { mounted.current = false; controller.abort(); clearInterval(timer); };
  }, []);
  async function action(action, mode) {
    setBusy(true);
    try {
      const response = await fetch("/api/integrations/ujin", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, mode }) });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || "Не удалось изменить подключение");
      if (mounted.current) { setStatus(data); setError(""); }
      publish({ kind: "info", scope: "Ujin", title: action === "stop" ? "Обмен останавливается" : "Подключение запущено", description: mode === "sync" ? "Публикуем показания существующих устройств и проверяем доступность команд." : "Читаем устройства и сигналы в учётной записи employee." });
    } catch (e) {
      if (mounted.current) setError(e.message);
      publish({ kind: "error", scope: "Ujin", title: "Ошибка подключения", description: e.message });
    } finally { if (mounted.current) setBusy(false); }
  }
  return (
    <div className="ujin-page">
      <section className="ujin-intro">
        <div><span className="home-location"><Link2 size={15} /> Интеграции</span><h1>Подключение Ujin</h1></div>
        <a className="secondary" href={status?.panel_url || "https://signal-panel.duckdns.org/"} target="_blank" rel="noreferrer">Панель сигналов <ArrowUpRight size={16} /></a>
      </section>
      {error && <p className="ujin-error" role="alert">{error}</p>}
      {!status && !error && <p role="status"><LoaderCircle size={20} /> Загружаем подключение…</p>}
      {status && <>
        <section className="ujin-connection" aria-label="Состояние подключения">
          <div className="ujin-status"><span data-state={status.state}>{labels[status.state] || status.state}</span><small>{status.mode === "sync" ? "Обмен с эмуляторами" : status.mode === "read" ? "Наблюдение" : "Обмен выключен"}</small></div>
          <p>{status.message}</p>
          {!status.configured && <p>Для подключения нужен серверный параметр <code>UJIN_CREDENTIALS_FILE</code> с путём к документу доступов или архиву.</p>}
          <div className="ujin-actions">
            <button className="secondary" disabled={busy || status.running || !status.configured} onClick={() => action("check")}><RefreshCw size={16} /> Проверить подключение</button>
            <button className="secondary" disabled={busy || status.running || !status.configured} onClick={() => action("start", "read")}>Наблюдать</button>
            <button className="primary" disabled={busy || status.running || !status.configured} onClick={() => action("start", "sync")}>Запустить обмен</button>
            <button className="secondary" disabled={busy || !status.running} onClick={() => action("stop")}><Square size={14} /> Остановить</button>
          </div>
          <div className="ujin-counters"><span>Показаний подтверждено: <strong>{status.published}</strong></span><span>Команд выполнено: <strong>{status.commands_applied}</strong></span></div>
          {status.last_check && <small className="ujin-updated">Последняя проверка: {new Date(status.last_check * 1000).toLocaleTimeString("ru-RU")}</small>}
        </section>
        <p className="ujin-explanation">Наблюдение читает данные Ujin. Обмен отправляет показания локальных эмуляторов в существующие устройства и принимает доступные команды. Новые устройства и словари не создаются; параметры модели и вендора для их создания ожидаются.</p>
        <div className="ujin-device-grid">
          {status.devices.map((device) => <article className="ujin-device" aria-label={device.name} key={device.family}>
            <div className="ujin-device-heading"><h2>{device.name}</h2><span>{device.serial_hint}</span></div>
            <p className={device.state === "error" || device.state === "unverified" ? "ujin-error" : "ujin-device-state"}>{deviceStates[device.state] || device.state}</p>
            {device.message && <p className="ujin-error">{device.message}</p>}
            <dl><div><dt>Сигналов в панели</dt><dd>{device.panel_signals}</dd></div><div><dt>Видно через API</dt><dd>{device.api_signals}</dd></div><div><dt>Доступно для команд</dt><dd>{device.writable_signals}</dd></div><div><dt>Подтверждено в последнем цикле</dt><dd>{device.verified}</dd></div></dl>
            {device.writable_signals === 0 && device.local_id && <p className="ujin-device-note">Платформа пока не открыла управляющие сигналы. Приём команд станет доступен после настройки словарей Ujin.</p>}
            <details><summary>Сигналы и параметры</summary><p className="ujin-technical">Модель: {device.model || "не задана"}<br />Класс публикации: {device.publish_class || "не задан"}</p>
              <ul>{device.signals.map((s) => <li key={s.name}><span>{s.name}<small>{s.management}</small></span><strong>{s.value}</strong></li>)}</ul>
            </details>
          </article>)}
        </div>
      </>}
    </div>
  );
}
