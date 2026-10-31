import { useState } from "react";
import { ArrowUpRight, ShieldCheck, Thermometer, Sparkles } from "lucide-react";
import templates from "./scenarioTemplates.json";
import { descriptions, fallbackDescription } from "./deviceCatalog";
import "./ScenarioTemplates.css";

const categories = ["Все", "Безопасность", "Климат", "Комфорт"];
const icons = { Безопасность: ShieldCheck, Климат: Thermometer, Комфорт: Sparkles };

function unavailable(scenario, home, declarations) {
  const condition = declarations[scenario.when.device]?.find(
    (s) => s.name === scenario.when.signal && s.management !== "w",
  );
  const signals = [scenario.when, ...scenario.do];
  const missing = [...new Set(signals.map((s) => s.device))].filter(
    (id) => !home?.metadata[id] || !declarations[id],
  );
  if (missing.length) return "Нужные устройства недоступны";
  if (!condition) return "Показатель условия недоступен";
  if (scenario.do.some((action) => {
    const s = declarations[action.device]?.find((s) => s.name === action.signal);
    return !s || s.management === "r" ||
      (s.min != null && action.value < s.min) ||
      (s.max != null && action.value > s.max) ||
      (s.layout && !(String(action.value) in s.layout));
  })) return "Действия шаблона недоступны";
  return "";
}

export default function ScenarioTemplates({ home, declarations, scenarios, onSelect }) {
  const [category, setCategory] = useState("Все");
  function choose(template) {
    const draft = structuredClone(template.scenario);
    const names = new Set(scenarios.map((s) => s.name));
    let suffix = 2;
    while (names.has(draft.name)) draft.name = `${template.scenario.name} (${suffix++})`;
    onSelect(draft);
  }
  return (
    <section className="scenario-templates" id="scenario-templates" aria-labelledby="templates-title">
      <div className="templates-heading">
        <div>
          <h2 id="templates-title" tabIndex={-1}>Шаблоны сценариев</h2>
          <p>Выберите правило и настройте его перед сохранением.</p>
        </div>
        <span>{templates.length} готовых правил</span>
      </div>
      <div className="templates-filters" role="group" aria-label="Категории шаблонов">
        {categories.map((name) => (
          <button key={name} aria-pressed={category === name} onClick={() => setCategory(name)}>
            {name}
          </button>
        ))}
      </div>
      <div className="templates-grid">
        {templates.filter((t) => category === "Все" || t.category === category).map((template) => {
          const reason = unavailable(template.scenario, home, declarations);
          const Icon = icons[template.category];
          const spec = descriptions[template.scenario.when.device] || fallbackDescription;
          const devices = [...new Set([template.scenario.when.device, ...template.scenario.do.map((a) => a.device)])];
          return (
            <article className="scenario-template" aria-label={template.scenario.name} key={template.key}>
              <div className="template-top">
                <span><Icon size={14} />{template.category}</span>
                <img src={`${import.meta.env.BASE_URL}images/${spec.image}.webp`} alt="" loading="lazy" />
              </div>
              <h3>{template.scenario.name}</h3>
              <p>{template.description}</p>
              <div className="template-devices">
                {devices.map((id) => <span key={id}>{home?.metadata[id]?.name || id}</span>)}
              </div>
              {reason && <p className="template-unavailable">{reason}</p>}
              <button className="secondary" disabled={!!reason} onClick={() => choose(template)}>
                Использовать шаблон <ArrowUpRight size={15} />
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
