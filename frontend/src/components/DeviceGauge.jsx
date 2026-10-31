import { useEffect, useState } from "react";
import { Fan, Sun } from "lucide-react";
import SloshGauge from "./reactbits/SloshGauge";
import "./DeviceGauge.css";
import useAutoDeviceCommand from "./useAutoDeviceCommand";

export default function DeviceGauge({
  id,
  state,
  onCommand,
  busy = false,
  online = true,
}) {
  const fan = id === "ventilation_1";
  const signal = fan ? "fan_speed" : "brightness";
  const min = fan ? 0 : 1,
    max = fan ? 6 : 100;
  const current = Number(state[signal]);
  const powered = fan ? !!state.mode : !!state.lamp;
  const [value, setValue] = useState(current);
  const auto = useAutoDeviceCommand(id, onCommand, () => setValue(current));
  useEffect(() => setValue(current), [current, powered]);
  useEffect(() => {
    if (!powered) auto.cancel(signal);
  }, [powered]);
  const disabled = !powered || !online || busy;
  const Icon = fan ? Fan : Sun;
  return (
    <div className="device-gauge-control" aria-busy={busy}>
      <div className="device-gauge-info">
        <span className="device-gauge-title">
          <Icon size={17} />
          {fan ? "Скорость вентиляции" : "Яркость света"}
        </span>
        <strong>{fan ? `${value} / 6` : `${value}%`}</strong>
        <span className="device-gauge-hint">
          {!powered
            ? "Включите устройство для настройки"
            : fan
              ? "Изменение скорости включает ручной режим"
              : "Потяните уровень вверх или вниз"}
        </span>
        {powered && (
          <span className="device-gauge-save" role="status">
            {busy ? "Сохраняем…" : "Сохраняется автоматически"}
          </span>
        )}
      </div>
      <SloshGauge
        value={(value / max) * 100}
        onChange={(percent) => {
          const next = Math.max(
            min,
            Math.min(max, Math.round((percent / 100) * max)),
          );
          setValue(next);
          if (next === current) auto.cancel(signal);
          else auto.schedule(signal, next);
        }}
        interactive
        showValue={!fan}
        disabled={disabled}
        width={76}
        height={132}
        radius={18}
        ticks={fan ? 6 : 4}
        liquidColor={fan ? "#adad8d" : "#edac82"}
        glassColor="#252620"
        ariaLabel={fan ? "Скорость вентиляции" : "Яркость света"}
        ariaValueText={fan ? `${value} из 6 ступеней` : `${value} процентов`}
        keyboardStep={fan ? 100 / 6 : 1}
        minValue={min}
      />
    </div>
  );
}
