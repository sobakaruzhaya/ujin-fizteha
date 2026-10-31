export const descriptions = {
  smart_plug_1: {
    image: "plug",
    sub: "Энергия под контролем",
    signal: "power_w",
    unit: "Вт",
    toggle: "power_switch",
    on: 1,
    alarm: "overload_alarm",
    status: (d) =>
      d.overload_alarm ? "Защита" : d.power_switch ? "Включено" : "Выключено",
  },
  light_1: {
    image: "lamp",
    sub: "Свет под настроение",
    signal: "brightness",
    unit: "%",
    toggle: "lamp",
    on: 1,
    status: (d) => (d.lamp ? "Включено" : "Выключено"),
  },
  thermostat_1: {
    image: "thermostat",
    sub: "Ваша идеальная температура",
    signal: "temperature",
    unit: "°C",
    decimals: 1,
    toggle: "mode",
    on: 3,
    active: (d) => !d.fault,
    status: (d) =>
      d.fault
        ? "Нет данных"
        : d.output === 1
          ? "Нагрев"
          : d.output === 2
            ? "Охлаждение"
            : "Ожидание",
  },
  ventilation_1: {
    image: "ventilation",
    sub: "Свежий воздух каждый день",
    signal: "co2",
    unit: "ppm",
    toggle: "mode",
    on: 1,
    active: (d) => d.mode !== 0,
    status: (d) =>
      d.mode === 0 ? "Выключено" : d.mode === 1 ? "Авто" : "Ручной",
  },
  temp_sensor_1: {
    image: "temp_sensor",
    sub: "Климат в комнате",
    signal: "temperature",
    unit: "°C",
    decimals: 1,
    active: (d) => !d.low_battery && !d.fault,
    status: (d) =>
      d.fault
        ? "Неисправность"
        : d.tamper
          ? "Вскрыт"
          : d.low_battery
            ? "Низкий заряд"
            : "На связи",
  },
  leak_1: {
    image: "leak",
    sub: "Защита от протечки",
    signal: "battery",
    unit: "%",
    active: (d) => !d.low_battery && !d.tamper,
    alarm: "leak",
    status: (d) =>
      d.leak
        ? "Протечка"
        : d.tamper
          ? "Вскрыт"
          : d.low_battery
            ? "Низкий заряд"
            : "Сухо",
  },
  hub_1: {
    image: "hub",
    sub: "Три датчика и сирена",
    signal: "sensors_online",
    unit: "датчика",
    active: (d) => !d.mute,
    alarm: "leak",
    status: (d) =>
      d.leak ? "Протечка" : d.mute ? "Без звука" : "Охрана",
  },
  fire_1: {
    image: "fire",
    sub: "Пожарная безопасность",
    signal: "smoke",
    unit: "%",
    active: (d) => !d.alarm,
    alarm: "alarm",
    status: (d) =>
      d.alarm
        ? "Тревога"
        : d.low_battery
          ? "Низкий заряд"
          : "Дежурство",
  },
  counter_1: {
    image: "counter",
    sub: "Расход электроэнергии",
    signal: "power_w",
    unit: "Вт",
    active: (d) => !!d.load_relay,
    status: (d) => (d.load_relay ? "Учёт" : "Реле отключено"),
  },
  tv_1: {
    image: "tv",
    sub: "Кино и приложения",
    signal: "volume",
    unit: "%",
    toggle: "power",
    on: 1,
    status: (d) => (d.power ? "Включён" : "Выключен"),
  },
  fridge_1: {
    image: "fridge",
    sub: "Свежесть под контролем",
    signal: "fridge_temp",
    unit: "°C",
    decimals: 1,
    active: (d) => !d.alarm,
    alarm: "alarm",
    status: (d) =>
      d.alarm === 2
        ? "Дверь открыта"
        : d.alarm === 1
          ? "Температура"
          : "Норма",
  },
  kettle_1: {
    image: "kettle",
    sub: "Кипяток к чаю",
    signal: "temperature",
    unit: "°C",
    toggle: "power",
    on: 1,
    alarm: "dry_boil",
    status: (d) =>
      d.dry_boil ? "Сухой ход" : d.power ? "Нагрев" : "Готов",
  },
  stove_1: {
    image: "stove",
    sub: "Четыре конфорки",
    signal: "power_w",
    unit: "Вт",
    toggle: "burner_1",
    on: 5,
    alarm: "overheat",
    status: (d) =>
      d.overheat
        ? "Перегрев"
        : d.boil_dry
          ? "Сухой нагрев"
          : d.burner_1
            ? "Нагрев"
            : "Выключена",
  },
  oven_1: {
    image: "oven",
    sub: "Готовим с комфортом",
    signal: "temperature",
    unit: "°C",
    toggle: "power",
    on: 1,
    alarm: "alarm",
    status: (d) =>
      d.alarm === 1
        ? "Дверь открыта"
        : d.alarm === 2
          ? "Перегрев"
          : d.power
            ? "Нагрев"
            : "Выключена",
  },
  intercom_1: {
    image: "intercom",
    sub: "Дверь и гости",
    signal: "volume",
    unit: "%",
    active: (d) => d.call_state > 0 || !!d.door_open,
    alarm: "tamper",
    status: (d) =>
      d.tamper
        ? "Вскрыт"
        : d.call_state === 1
          ? "Звонок"
          : d.call_state === 2
            ? "Разговор"
            : d.door_open
              ? "Дверь открыта"
              : "Ожидание",
  },
};
export const fallbackDescription = {
  image: "plug",
  sub: "Устройство дома",
  signal: "fw",
  unit: "",
  status: () => "На связи",
};
export function plural(count, one, few, many) {
  const n = Math.abs(count) % 100,
    last = n % 10;
  if (n > 10 && n < 20) return many;
  if (last > 1 && last < 5) return few;
  if (last === 1) return one;
  return many;
}

export function deviceActive(id,state) {
 const spec=descriptions[id]||fallbackDescription;
 return spec.toggle ? !!state[spec.toggle] : spec.active ? !!spec.active(state) : true;
}
