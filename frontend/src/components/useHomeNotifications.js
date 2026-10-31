import { useCallback, useRef } from "react";

// Each entry watches a real signal transition, not a timer or sample message.
const alarms = [
  ["smart_plug", "overload_alarm", "Перегрузка розетки", "Превышен лимит мощности. Питание отключено защитой.", "error"],
  ["smart_plug", "anomaly", "Аномалия питания", "Защита обнаружила аномалию и отключила розетку.", "error"],
  ["fire", "alarm", "Пожарная тревога", "Пожарный датчик перешёл в состояние тревоги.", "error"],
  ["leak", "leak", "Обнаружена протечка", "Датчик обнаружил воду.", "error"],
  ["hub", "leak", "Хаб обнаружил протечку", "Получен сигнал от датчиков протечки.", "error"],
  ["kettle", "dry_boil", "Чайник без воды", "Защита сухого хода заблокировала нагрев.", "error"],
  ["stove", "overheat", "Перегрев плиты", "Конфорки отключены встроенной защитой.", "error"],
  ["stove", "boil_dry", "Сухой нагрев плиты", "Посуда не обнаружена. Нагрев прекращён.", "warning"],
  ["fridge", "alarm", "Тревога холодильника", "Проверьте температуру и состояние двери.", "warning"],
  ["oven", "alarm", "Предупреждение духовки", "Проверьте дверь и состояние нагрева.", "warning"],
];
const watched = (metadata, state) => {
  const rows = [];
  for (const [id, meta] of Object.entries(metadata)) {
    const signals = state[id] || {};
    for (const [family, signal, title, message, kind] of alarms) {
      if (meta.family === family && signal in signals)
        rows.push({ key: `${id}:${signal}`, value: signals[signal], title, message, kind, name: meta.name });
    }
    for (const [signal, title, message, kind] of [
      ["fault", "Сбой датчика", "Устройство сообщает о неисправности.", "error"],
      ["low_battery", "Низкий заряд датчика", "Замените или зарядите батарею.", "warning"],
      ["tamper", "Вскрытие корпуса", "Сработал датчик вскрытия.", "warning"],
    ]) {
      if (signal in signals) rows.push({ key: `${id}:${signal}`, value: signals[signal], title, message, kind, name: meta.name });
    }
    if ("online" in signals) rows.push({ key: `${id}:offline`, value: signals.online === 0, title: "Нет связи с устройством", message: "Устройство перестало выходить на связь.", kind: "error", name: meta.name });
    if (meta.family === "hub") rows.push({ key: `${id}:offline-sensors`, value: signals.sensors_online < signals.sensors_total, title: "Нет связи с датчиком протечки", message: `На связи ${signals.sensors_online} из ${signals.sensors_total} датчиков.`, kind: "warning", name: meta.name });
    if (meta.family === "ventilation") rows.push({ key: `${id}:high-co2`, value: signals.co2 > 1000, title: "Высокий уровень CO₂", message: `Измерено ${signals.co2} ppm. Скорость вентиляции: ${signals.fan_speed}.`, kind: "warning", name: meta.name });
  }
  return rows;
};

export default function useHomeNotifications(publish) {
  const previous = useRef(null);
  const seenEvents = useRef(null);
  const connection = useRef(null);
  const connected = useCallback((home, declarations, events) => {
    if (connection.current === false) publish({ kind: "success", title: "Связь восстановлена", description: "Состояния устройств снова обновляются." });
    connection.current = true;
    const rows = watched(home.metadata, home.devices);
    for (const row of rows) {
      // New servers journal every transition, including a short alarm and its
      // recovery between polls. Keep signal watching for initial active faults
      // and backwards compatibility with older servers only.
      if (home.notification_protocol && previous.current) continue;
      const before = previous.current?.get(row.key);
      if (row.value && (!before || before.value !== row.value)) {
        let reaction = row.message;
        const id = row.key.split(":")[0], device = home.devices[id];
        if (row.key.endsWith(":fault") && home.metadata[id].family === "thermostat" && device.output === 0)
          reaction += " Нагрев остановлен.";
        if (home.metadata[id].family === "hub" && row.key.endsWith(":leak"))
          reaction += device.siren ? " Сирена включена." : " Звук сирены отключён.";
        publish({ kind: row.kind, title: row.title, description: `${row.name}: ${reaction}` });
      } else if (before?.value && !row.value) {
        publish({ kind: "success", title: "Устройство вернулось в норму", description: `${row.name}: «${before.title}» — состояние восстановлено.` });
      }
    }
    previous.current = new Map(rows.map((r) => [r.key, r]));
    if (seenEvents.current) {
      const fresh = events.filter((e) => !seenEvents.current.has(e.id));
      for (const event of fresh) {
        if (event.notification) {
          publish({ kind: event.kind || "info", title: event.title || home.metadata[event.device]?.name || "Устройство", description: event.message });
          continue;
        }
        if (event.type === "alarm" && !rows.some((r) => r.key.startsWith(`${event.device}:`) && r.value))
          publish({ kind: "error", title: "Сработала защита", description: event.message });
        if (event.type === "error") publish({ kind: "error", scope: event.source === "ujin" ? "Ujin" : "Дом", title: event.source === "ujin" ? "Ошибка обмена Ujin" : "Ошибка выполнения", description: event.message });
        if (event.type === "integration_connected") publish({ kind: "success", scope: "Ujin", title: "Ujin на связи", description: event.message });
        if (event.type === "scenario_triggered") publish({ kind: "info", title: "Сценарий сработал", description: event.message });
        if (["device_started", "device_finished", "device_stopped"].includes(event.type))
          publish({ kind: event.type === "device_finished" ? "success" : "info", title: event.type === "device_finished" ? "Вода нагрета" : event.type === "device_started" ? "Чайник включён" : "Нагрев остановлен", description: event.message });
      }
      const actions = fresh.filter((e) => e.type === "command" && e.source === "scenario" && !e.notification_handled);
      if (actions.length) {
        const descriptions = actions.map((e) => {
          const signal = declarations[e.device]?.find((s) => s.name === e.signal);
          const value = signal?.layout?.[e.value] ?? `${e.value}${signal?.measure ? " " + signal.measure : ""}`;
          return `${home.metadata[e.device]?.name || e.device}: ${signal?.title || e.signal} → ${value}`;
        });
        publish({ kind: "success", title: "Реакция устройств", description: descriptions.slice(0, 3).join("; ") + (actions.length > 3 ? `; ещё ${actions.length - 3} действий` : "") });
      }
    }
    seenEvents.current = new Set(events.map((e) => e.id));
  }, [publish]);
  const disconnected = useCallback(() => {
    if (connection.current !== false) publish({ kind: "error", title: "Нет связи с домом", description: "Не удалось получить состояния устройств. Пытаемся подключиться снова." });
    connection.current = false;
  }, [publish]);
  return { connected, disconnected };
}
