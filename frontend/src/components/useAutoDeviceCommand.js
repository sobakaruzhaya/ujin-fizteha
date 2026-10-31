import { useEffect, useRef } from "react";

// Coalesce edits to each signal; HomeApp serializes resulting device commands.
export default function useAutoDeviceCommand(id, onCommand, onFailure) {
  const latest = useRef({ id, onCommand, onFailure });
  latest.current = { id, onCommand, onFailure };
  const timers = useRef(new Map()),
    values = useRef(new Map()),
    alive = useRef(true);
  function cancel(signal) {
    clearTimeout(timers.current.get(signal));
    timers.current.delete(signal);
    values.current.delete(signal);
  }
  function flush(signal) {
    if (!values.current.has(signal)) return;
    const value = values.current.get(signal);
    cancel(signal);
    const { id, onCommand } = latest.current;
    void onCommand(id, signal, value, false).then((ok) => {
      if (!ok && alive.current) latest.current.onFailure?.(signal);
    });
  }
  function schedule(signal, value, delay = 350) {
    cancel(signal);
    values.current.set(signal, value);
    timers.current.set(
      signal,
      setTimeout(() => flush(signal), delay),
    );
  }
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      for (const signal of [...values.current.keys()]) flush(signal);
    };
  }, []);
  return { schedule, cancel, flush };
}
