import { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowRight,
  Check,
  LoaderCircle,
  Plus,
  Trash2,
  Workflow,
  X,
} from "lucide-react";
import { Sheet, SheetContent, SheetTitle, SheetDescription } from "./ui/sheet";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import {
  GlideSelect,
  ScrubField,
  SquishSwitch,
  AnimatedList,
} from "./control-adapters";

type Signal = {
  name: string;
  title: string;
  management: string;
  control: string;
  measure?: string;
  min?: number | null;
  max?: number | null;
  layout?: Record<string, string>;
};
type Action = { device: string; signal: string; value: number };
type Condition = Action & { operator: string };
export type Scenario = {
  id?: string;
  name: string;
  enabled: boolean;
  when: Condition;
  do: Action[];
};
type Props = {
  item: Partial<Scenario>;
  home: { metadata: Record<string, { name: string; room: string }> };
  declarations: Record<string, Signal[]>;
  onClose: () => void;
  onSave: (scenario: Scenario) => Promise<void>;
};
const operators = [
  { value: ">", label: "Больше" },
  { value: "<", label: "Меньше" },
  { value: "==", label: "Равно" },
  { value: ">=", label: "Не меньше" },
  { value: "<=", label: "Не больше" },
  { value: "!=", label: "Не равно" },
];
const readable = (signals: Signal[]) =>
  signals.filter((s) => s.name !== "fw" && s.management !== "w");
const writable = (signals: Signal[]) =>
  signals.filter((s) => s.management !== "r");

export default function ScenarioSheet({
  item,
  home,
  declarations,
  onClose,
  onSave,
}: Props) {
  const opener = useRef(document.activeElement as HTMLElement | null);
  const names = Object.entries(home.metadata);
  const choices = (id: string, action = false) =>
    (action ? writable : readable)(declarations[id] || []);
  const first = (action = false): Action => {
    const id = names.find(([id]) => choices(id, action).length)?.[0] || "";
    const signal = choices(id, action)[0];
    return {
      device: id,
      signal: signal?.name || "",
      value:
        signal?.control === "button"
          ? 1
          : Number(Object.keys(signal?.layout || {})[0] ?? signal?.min ?? 0),
    };
  };
  const [name, setName] = useState(item.name || "");
  const [when, setWhen] = useState<Condition>(
    item.when ||
      (declarations.smart_plug_1?.some((s) => s.name === "power_w")
        ? {
            device: "smart_plug_1",
            signal: "power_w",
            operator: ">",
            value: 1000,
          }
        : { ...first(), operator: ">" }),
  );
  const [actions, setActions] = useState<(Action & { key: string })[]>(
    (
      item.do || [
        declarations.light_1?.some((s) => s.name === "lamp")
          ? { device: "light_1", signal: "lamp", value: 0 }
          : first(true),
      ]
    ).map((a) => ({ ...a, key: crypto.randomUUID() })),
  );
  const [enabled, setEnabled] = useState(item.enabled ?? true);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [removing, setRemoving] = useState<string[]>([]);
  const removeTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(() => () => removeTimers.current.forEach(clearTimeout), []);
  function removeAction(key: string) {
    if (removing.includes(key) || actions.length - removing.length <= 1) return;
    setRemoving((old) => [...old, key]);
    removeTimers.current.push(
      setTimeout(() => {
        setActions((old) => old.filter((a) => a.key !== key));
        setRemoving((old) => old.filter((id) => id !== key));
      }, 180),
    );
  }
  const submitted = useRef(false);
  const [open, setOpen] = useState(true);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  useEffect(() => () => clearTimeout(closeTimer.current), []);
  function close() {
    if (busy) return;
    setOpen(false);
    closeTimer.current = setTimeout(onClose, 200);
  }
  const draft = (): Scenario => ({
    ...(item.id ? { id: item.id } : {}),
    name: name.trim(),
    enabled,
    when,
    do: actions.map(({ key, ...action }) => action),
  });
  function validate() {
    const next: Record<string, string> = {};
    if (!name.trim()) next.name = "Введите название сценария";
    if (!choices(when.device).some((s) => s.name === when.signal))
      next.when = "Выберите доступное устройство и показатель";
    if (!Number.isFinite(when.value)) next.when = "Введите числовое значение";
    actions.forEach((a, i) => {
      const s = choices(a.device, true).find((s) => s.name === a.signal);
      if (!s) next[a.key] = "Выберите доступное действие";
      else if (
        !Number.isFinite(a.value) ||
        (s.min != null && a.value < s.min) ||
        (s.max != null && a.value > s.max) ||
        (s.layout && !Object.keys(s.layout).includes(String(a.value)))
      )
        next[a.key] = `Проверьте значение действия ${i + 1}`;
    });
    setErrors(next);
    return Object.keys(next).length === 0;
  }
  const select = (
    label: string,
    value: string,
    options: { value: string; label: string }[],
    change: (value: string) => void,
  ) => (
    <div className="builder-field">
      <span>{label}</span>
      <GlideSelect
        ariaLabel={label}
        value={value}
        options={options}
        onChange={change}
        disabled={busy || !options.length}
        showTags={false}
        surfaceColor="#1a1c19"
        highlightColor="#3c3026"
        accentColor="#edac82"
        menuWidth={280}
      />
    </div>
  );
  function controls(a: Action, set: (a: Action) => void, action = false) {
    const signal = choices(a.device, action).find((s) => s.name === a.signal);
    const layout = signal?.layout;
    const binary =
      action &&
      layout &&
      Object.keys(layout).length === 2 &&
      "0" in layout &&
      "1" in layout;
    return (
      <>
        <div className="builder-fields">
          {select(
            "Устройство",
            a.device,
            names
              .filter(([id]) => choices(id, action).length)
              .map(([value, m]) => ({ value, label: m.name })),
            (id) => {
              const s = choices(id, action)[0];
              set({
                ...a,
                device: id,
                signal: s?.name || "",
                value:
                  s?.control === "button"
                    ? 1
                    : Number(Object.keys(s?.layout || {})[0] ?? s?.min ?? 0),
              });
            },
          )}
          {select(
            action ? "Действие" : "Показатель",
            a.signal,
            choices(a.device, action).map((s) => ({
              value: s.name,
              label: s.title,
            })),
            (signalName) => {
              const s = choices(a.device, action).find(
                (s) => s.name === signalName,
              );
              set({
                ...a,
                signal: signalName,
                value:
                  s?.control === "button"
                    ? 1
                    : Number(Object.keys(s?.layout || {})[0] ?? s?.min ?? 0),
              });
            },
          )}
        </div>
        {!action &&
          select("Условие", (a as Condition).operator, operators, (operator) =>
            set({ ...a, operator } as Condition),
          )}
        {signal?.control === "button" && action ? (
          <p className="builder-hint">
            <Check size={15} /> Команда будет выполнена при срабатывании.
          </p>
        ) : binary ? (
          <div className="builder-field">
            <span>Состояние устройства</span>
            <div
              className="binary-control"
              role="group"
              aria-label="Состояние устройства"
            >
              {[
                [0, "Выключить"],
                [1, "Включить"],
              ].map(([value, label]) => (
                <Button
                  type="button"
                  key={value}
                  variant="ghost"
                  aria-pressed={a.value === value}
                  onClick={() => set({ ...a, value: Number(value) })}
                  disabled={busy}
                >
                  {label}
                </Button>
              ))}
            </div>
          </div>
        ) : layout && action ? (
          select(
            "Значение действия",
            String(a.value),
            Object.entries(layout).map(([value, label]) => ({ value, label })),
            (value) => set({ ...a, value: Number(value) }),
          )
        ) : (
          <div className="builder-number">
            <ScrubField
              label={action ? "Значение действия" : "Значение условия"}
              suffix={signal?.measure || ""}
              value={a.value}
              onChange={(value) => set({ ...a, value })}
              min={action ? (signal?.min ?? -1e9) : -1e9}
              max={action ? (signal?.max ?? 1e9) : 1e9}
              step={signal?.measure === "°C" ? 0.1 : 1}
              accent="#edac82"
              chipColor="#1a1c19"
              disabled={busy}
              showDelta={false}
              showFill={false}
            />
          </div>
        )}
      </>
    );
  }
  async function save() {
    if (submitted.current || removing.length || !validate()) return;
    submitted.current = true;
    setBusy(true);
    setNotice("");
    try {
      await onSave(draft());
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Не удалось сохранить сценарий. Попробуйте ещё раз.",
      );
    } finally {
      submitted.current = false;
      setBusy(false);
    }
  }
  async function preview() {
    if (submitted.current || removing.length || !validate()) return;
    submitted.current = true;
    setBusy(true);
    try {
      const res = await fetch("/api/simulations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seconds: 30, scenario: draft() }),
        signal: AbortSignal.timeout(8000),
      });
      const result = await res.json();
      if (!res.ok) throw Error(result.error);
      setNotice(
        `Проверка завершена. ${result.events.filter((e: { type: string }) => e.type === "scenario_triggered").length} срабатываний за 30 секунд. Состояние дома не изменилось.`,
      );
    } catch (e) {
      setNotice(
        e instanceof Error ? e.message : "Не удалось проверить сценарий",
      );
    } finally {
      submitted.current = false;
      setBusy(false);
    }
  }
  return (
    <Sheet
      open={open}
      onOpenChange={(next: boolean) => {
        if (!next) close();
      }}
    >
      <SheetContent
        className="scenario-sheet"
        showCloseButton={false}
        onEscapeKeyDown={(e: KeyboardEvent) => {
          if (
            (e.target as HTMLElement)
              ?.closest(".glide-select")
              ?.querySelector('[aria-expanded="true"]')
          )
            e.preventDefault();
        }}
        onCloseAutoFocus={(e: Event) => {
          e.preventDefault();
          opener.current?.focus();
        }}
      >
        <header className="builder-header">
          <div className="builder-symbol">
            <Workflow size={22} />
          </div>
          <div>
            <SheetTitle>
              {item.id ? "Изменить сценарий" : "Новый сценарий"}
            </SheetTitle>
            <SheetDescription>
              Настройте автоматизацию устройств
            </SheetDescription>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Закрыть"
            disabled={busy}
            onClick={close}
          >
            <X size={20} />
          </Button>
        </header>
        <form
          className="builder-form"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <div className="builder-scroll">
            <div className="builder-name">
              <label htmlFor="scenario-name">Название сценария</label>
              <Input
                autoFocus
                id="scenario-name"
                placeholder="Например, уютный вечер"
                maxLength={120}
                value={name}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setName(e.target.value)
                }
                aria-invalid={!!errors.name}
                aria-describedby={errors.name ? "name-error" : undefined}
                disabled={busy}
              />
              {errors.name && (
                <p id="name-error" className="field-error">
                  {errors.name}
                </p>
              )}
            </div>
            <section className="builder-card">
              <div className="builder-card-heading">
                <span className="step-number">01</span>
                <h3>Если</h3>
                <span>Условие запуска</span>
              </div>
              {controls(when, (a) => setWhen(a as Condition))}
              {errors.when && <p className="field-error">{errors.when}</p>}
            </section>
            <div className="builder-connector">
              <ArrowDown size={17} />
            </div>
            <AnimatedList
              items={actions.map((a) => ({ id: a.key }))}
              interactive={false}
              frame={false}
              showGradients={false}
              enableArrowNavigation={false}
              selectOnHover={false}
              width="100%"
              maxHeight="none"
              animation="slide"
              className="builder-action-list"
              renderItem={(_, i) => {
                const a = actions[i];
                return (
                  <section
                    className="builder-card"
                    data-removing={removing.includes(a.key)}
                  >
                    <div className="builder-card-heading">
                      <span className="step-number">
                        {String(i + 2).padStart(2, "0")}
                      </span>
                      <h3>Тогда</h3>
                      <span>Действие {i + 1}</span>
                      {actions.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label={`Удалить действие ${i + 1}`}
                          disabled={busy}
                          onClick={() => removeAction(a.key)}
                        >
                          <Trash2 size={16} />
                        </Button>
                      )}
                    </div>
                    {controls(
                      a,
                      (next) =>
                        setActions((old) =>
                          old.map((x) =>
                            x.key === a.key ? { ...next, key: a.key } : x,
                          ),
                        ),
                      true,
                    )}
                    {errors[a.key] && (
                      <p className="field-error">{errors[a.key]}</p>
                    )}
                  </section>
                );
              }}
            />
            <Button
              type="button"
              variant="outline"
              className="builder-add"
              disabled={busy || !names.length}
              onClick={() =>
                setActions((old) => [
                  ...old,
                  { ...first(true), key: crypto.randomUUID() },
                ])
              }
            >
              <Plus size={17} />
              Добавить действие
            </Button>
            <div className="builder-activation">
              <div>
                <strong>Активировать после сохранения</strong>
                <span>Сценарий начнёт работать сразу</span>
              </div>
              <SquishSwitch
                checked={enabled}
                onChange={setEnabled}
                ariaLabel="Активировать после сохранения"
                width={48}
                height={28}
                trackOnColor="#edac82"
                thumbOnColor="#241b14"
                disabled={busy}
              />
            </div>
            <Button
              type="button"
              variant="ghost"
              className="builder-test"
              disabled={busy || !names.length}
              onClick={() => void preview()}
            >
              Проверить на 30 секунд <ArrowRight size={15} />
            </Button>
            {notice && (
              <p className="builder-notice" role="status">
                {notice}
              </p>
            )}
            {!names.length && (
              <p className="field-error">
                Нет доступных устройств. Дождитесь подключения.
              </p>
            )}
          </div>
          <footer className="builder-footer">
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={close}
            >
              Отмена
            </Button>
            <Button type="submit" disabled={busy || !names.length}>
              {busy ? (
                <LoaderCircle className="animate-spin" size={17} />
              ) : (
                <Check size={17} />
              )}{" "}
              {busy
                ? "Сохранение…"
                : item.id
                  ? "Сохранить изменения"
                  : "Создать сценарий"}
            </Button>
          </footer>
        </form>
      </SheetContent>
    </Sheet>
  );
}
