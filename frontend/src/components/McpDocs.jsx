import { useState } from "react";
import { ArrowUpRight, Check, Copy, Download, Plug, Terminal } from "lucide-react";
import "./McpDocs.css";

const API_URL = "http://127.0.0.1:8787";
const MCP_URL = "http://127.0.0.1:8788/mcp";
const toolGroups = [
  ["Дом и устройства", "Состояние устройств, история и потребление энергии.", ["get_home_state", "list_devices", "get_device_state", "get_health", "get_recent_events", "get_power_history", "analyze_energy"]],
  ["Сценарии и шаблоны", "Создание автоматизаций, редактирование и проверка правил.", ["list_scenarios", "get_scenario", "create_scenario", "update_scenario", "toggle_scenario", "delete_scenario", "simulate_scenario", "list_scenario_templates", "create_scenario_from_template"]],
  ["Управление", "Команды устройствам и подтверждение опасных действий.", ["request_device_command", "confirm_device_command"]],
  ["Тесты", "Аварийные проверки и диагностика на изолированных эмуляторах.", ["list_emergency_tests", "run_emergency_tests", "list_device_diagnostics", "run_device_diagnostics"]],
  ["Ujin и API", "Состояние интеграции, управление обменом и описание API.", ["get_ujin_status", "manage_ujin_integration", "describe_api"]],
  ["Лаборатория", "Эксперименты и сброс состояний общего дома.", ["run_demo", "reset_home"]],
];
const resources = ["home://state", "home://events", "home://scenarios", "home://devices", "home://scenario-templates", "home://tests/emergency", "home://tests/devices", "home://integrations/ujin", "home://api"];

function CodeBlock({ title, value, language = "PowerShell" }) {
  const [message, setMessage] = useState("");
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setMessage("Скопировано");
    } catch {
      setMessage("Выделите и скопируйте текст вручную");
    }
  }
  return <div className="mcp-code">
    <div className="mcp-code-heading">
      <span>{title}<small>{language}</small></span>
      <button type="button" onClick={copy} aria-label={`Копировать: ${title}`}>
        {message === "Скопировано" ? <Check size={16} /> : <Copy size={16} />} Копировать
      </button>
    </div>
    <pre><code>{value}</code></pre>
    <span className="mcp-copy-status" role="status">{message}</span>
  </div>;
}

export default function McpDocs() {
  const [transport, setTransport] = useState("http");
  const [projectPath, setProjectPath] = useState("C:/projects/ujin-fizteha");
  const normalizedPath = projectPath.trim().replace(/\\/g, "/").replace(/\/+$/, "");
  const config = JSON.stringify({ mcpServers: { ujinfizteha: transport === "http"
    ? { type: "http", url: MCP_URL }
    : { command: `${normalizedPath}/.venv-mcp/Scripts/python.exe`, args: [`${normalizedPath}/app/run.py`, "--mcp", "--api-url", API_URL] }
  } }, null, 2);
  function download() {
    const url = URL.createObjectURL(new Blob([config + "\n"], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `ujinfizteha-mcp-${transport}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <article className="mcp-docs">
    <header className="mcp-docs-intro">
      <div>
        <span className="mcp-eyebrow"><Plug size={16} /> Для AI-ассистентов</span>
        <h1>Подключение MCP</h1>
        <p>Подключите ассистента к UjinFizteha, чтобы управлять устройствами, создавать сценарии и проверять реакции датчиков.</p>
      </div>
      <a className="secondary mcp-api-link" href="/api/docs" target="_blank" rel="noreferrer">Документация API <ArrowUpRight size={17} /></a>
    </header>

    <div className="mcp-facts" aria-label="Параметры MCP">
      <div><span>Адрес сервера</span><code>{MCP_URL}</code></div>
      <div><span>Транспорты</span><strong>Streamable HTTP · stdio</strong></div>
      <div><span>Возможности</span><strong>27 инструментов · 9 ресурсов</strong></div>
    </div>

    <div className="mcp-layout">
      <div className="mcp-guide">
        <section className="mcp-section" aria-labelledby="mcp-start">
          <h2 id="mcp-start"><span className="mcp-step">01</span> Запустите сервер</h2>
          <p>Нужны Python 3.11+ и папка проекта. Команды ниже — для Windows PowerShell, выполняйте их из корня проекта.</p>
          <details className="mcp-setup"><summary>Первый запуск: установить зависимости</summary>
            <CodeBlock title="Установка" value={'python -m venv .venv-mcp\n./.venv-mcp/Scripts/python.exe -m pip install -r requirements-mcp.txt'} />
          </details>
          <p>Если сайт уже работает на порту 8787, переходите к следующему шагу. Для запуска API и сайта:</p>
          <CodeBlock title="API и сайт · терминал 1" value="./.venv-mcp/Scripts/python.exe -m app.run --local" />
          <p>Для подключения по HTTP откройте второй терминал и оставьте оба процесса работающими:</p>
          <CodeBlock title="MCP по HTTP · терминал 2" value={`./.venv-mcp/Scripts/python.exe -m app.run --mcp-http --api-url ${API_URL}`} />
          <p className="mcp-note">Если MCP уже запущен на 8788, повторный запуск не нужен. В режиме stdio MCP-процесс запускает сам клиент.</p>
        </section>

        <section className="mcp-section" aria-labelledby="mcp-config">
          <h2 id="mcp-config"><span className="mcp-step">02</span> Настройте MCP-клиент</h2>
          <div className="mcp-transports" role="group" aria-label="Транспорт MCP">
            <button aria-pressed={transport === "http"} onClick={() => setTransport("http")}>HTTP <span>по адресу сервера</span></button>
            <button aria-pressed={transport === "stdio"} onClick={() => setTransport("stdio")}>stdio <span>локальный процесс</span></button>
          </div>
          {transport === "http" ? <p>В клиенте с поддержкой Streamable HTTP добавьте сервер <strong>UjinFizteha</strong> с адресом <code>{MCP_URL}</code>. Для клиентов с JSON-настройкой используйте пример ниже; формат полей может отличаться в вашем клиенте.</p>
            : <><p>Укажите полный путь к проекту. Клиент запустит Python из виртуального окружения и подключится к API на порту 8787.</p>
              <label className="mcp-path">Папка проекта в Windows
                <input value={projectPath} onChange={(event) => setProjectPath(event.target.value)} placeholder="C:/projects/ujin-fizteha" spellCheck={false} />
              </label></>}
          <CodeBlock key={config} title="Конфигурация MCP" language="JSON" value={config} />
          <button className="secondary mcp-download" onClick={download} disabled={transport === "stdio" && !normalizedPath}><Download size={16} /> Скачать JSON</button>
          <p className="mcp-note">Добавьте запись в список <code>mcpServers</code> вашего клиента, сохранив остальные серверы. Переподключите сервер или перезапустите клиент после изменения настроек.</p>
        </section>

        <section className="mcp-section" aria-labelledby="mcp-verify">
          <h2 id="mcp-verify"><span className="mcp-step">03</span> Проверьте подключение</h2>
          <ol className="mcp-checks">
            <li>Попросите ассистента вызвать <code>get_health</code>. Поле <code>transport: "http"</code> означает, что MCP использует общий API дома — в том числе при подключении клиента через stdio.</li>
            <li>Вызовите <code>list_devices</code> и сравните список с главной страницей.</li>
            <li>Для проверки датчиков используйте <code>run_emergency_tests</code>: тесты выполняются на изолированном стенде.</li>
          </ol>
          <div className="mcp-prompt"><Terminal size={19} /><p>«Покажи устройства и текущее потребление. Проверь перегрузку розетки на тестовом стенде и объясни, как сработала защита».</p></div>
          <CodeBlock title="Пример аргументов аварийного теста" language="JSON" value={JSON.stringify({case_id: "socket-overload", include_trace: true}, null, 2)} />
        </section>
      </div>

      <aside className="mcp-sidebar" aria-label="Справка MCP">
        <section className="mcp-section">
          <h2>Как работает подключение</h2>
          <div className="mcp-flow"><span>AI-ассистент</span><span aria-hidden="true">↓ MCP</span><span>Сервер UjinFizteha</span><span aria-hidden="true">↓ API · 8787</span><span>Общий дом</span></div>
          <p>Веб-версия, Telegram и MCP видят одно состояние. Команды устройствам и сохранённые сценарии отражаются во всех интерфейсах.</p>
          <p>Опасная команда через MCP возвращает <code>confirmation_id</code>. Для её выполнения вызывается <code>confirm_device_command</code> в течение 60 секунд.</p>
          <p>Аварийные тесты и симуляции изолированы. <code>run_demo</code> и <code>reset_home</code> изменяют общий дом.</p>
        </section>
        <section className="mcp-section">
          <h2>Если не подключается</h2>
          <details><summary>Connection refused / сервер недоступен</summary><p>Проверьте API на 8787 и MCP-процесс на 8788. <code>127.0.0.1</code> — компьютер, на котором запущен клиент. Этот адрес подходит для локального подключения; облачный клиент не сможет обратиться к вашему компьютеру по нему.</p></details>
          <details><summary>Не найден Python или модуль mcp</summary><p>Установите зависимости из первого шага. Для stdio проверьте полный путь к <code>python.exe</code> и <code>app/run.py</code>.</p></details>
          <details><summary>Ассистент видит другой дом</summary><p>Запускайте MCP с <code>--api-url http://127.0.0.1:8787</code>. Флаг <code>--local</code> у MCP создаёт отдельный дом; в <code>get_health</code> он отмечен как <code>transport: "local"</code>.</p></details>
          <details><summary>В браузере адрес /mcp не открывается</summary><p>Это протокольный адрес, а не страница сайта. Проверяйте его из MCP-клиента через обнаружение инструментов и вызов <code>get_health</code>.</p></details>
          <p className="mcp-note">Локальный MCP слушает <code>127.0.0.1</code>. Telegram-токен и данные Ujin клиенту передавать не нужно: они настроены на сервере.</p>
        </section>
      </aside>
    </div>

    <section className="mcp-catalog" aria-labelledby="mcp-tools">
      <h2 id="mcp-tools">Что умеет ассистент</h2>
      <div className="mcp-tool-grid">{toolGroups.map(([title, description, tools]) => <details className="mcp-tool-group" key={title}>
        <summary>{title}<span>{tools.length}</span></summary><p>{description}</p><ul>{tools.map((tool) => <li key={tool}><code>{tool}</code></li>)}</ul>
      </details>)}</div>
      <details className="mcp-resources"><summary>9 ресурсов для чтения</summary><ul>{resources.map((resource) => <li key={resource}><code>{resource}</code></li>)}</ul></details>
    </section>
  </article>;
}
