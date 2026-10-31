import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, CheckCircle2, Info, ShieldAlert } from "lucide-react";
import SwipeToast from "./reactbits/SwipeToast";
import "./Notifications.css";

const NotificationContext = createContext(null);
const styles = {
  error: { color: "#eda78b", background: "#291c18", Icon: ShieldAlert, duration: 12000 },
  warning: { color: "#edc28b", background: "#282319", Icon: AlertTriangle, duration: 10000 },
  success: { color: "#b8c6a2", background: "#1e251b", Icon: CheckCircle2, duration: 6000 },
  info: { color: "#edac82", background: "#21221d", Icon: Info, duration: 6500 },
};
const priority = { error: 0, warning: 1, success: 2, info: 3 };

export function useNotifications() {
  const context = useContext(NotificationContext);
  if (!context) throw Error("NotificationsProvider is missing");
  return context;
}

export default function NotificationsProvider({ children }) {
  const [items, setItems] = useState([]);
  const [target, setTarget] = useState(document.body);
  const [compact, setCompact] = useState(() => matchMedia("(max-width: 600px)").matches);
  const recent = useRef(new Map());
  const publish = useCallback((notice) => {
    const now = Date.now();
    const key = notice.key || `${notice.scope || "Дом"}:${notice.title}:${notice.description}`;
    for (const [id, time] of recent.current) if (now - time > 5000) recent.current.delete(id);
    if (recent.current.has(key)) return;
    recent.current.set(key, now);
    const item = { kind: "info", scope: "Дом", ...notice, id: crypto.randomUUID() };
    setItems((old) => [...old, item].sort((a, b) => priority[a.kind] - priority[b.kind]).slice(0, 12));
  }, []);
  const remove = useCallback((id) => setItems((old) => old.filter((n) => n.id !== id)), []);
  useEffect(() => {
    const query = matchMedia("(max-width: 600px)");
    const resize = () => setCompact(query.matches);
    query.addEventListener("change", resize);
    // Native <dialog> lives in the browser's top layer. Mount notifications
    // inside the open dialog so errors remain visible while editing devices.
    const updateTarget = () => {
      const dialogs = document.querySelectorAll("dialog[open]");
      setTarget(dialogs[dialogs.length - 1] || document.body);
    };
    const observer = new MutationObserver(updateTarget);
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["open"] });
    updateTarget();
    return () => { query.removeEventListener("change", resize); observer.disconnect(); };
  }, []);
  const visible = items.slice(0, compact ? 2 : 3);
  return (
    <NotificationContext.Provider value={publish}>
      {children}
      {items.length > 0 && createPortal(
        <aside className="home-notifications" aria-label="Уведомления">
          {items.length > visible.length && <span className="notification-pending">Ещё {items.length - visible.length} в очереди</span>}
          {visible.map((item) => {
            const { Icon, color, background, duration } = styles[item.kind] || styles.info;
            return (
              <SwipeToast key={item.id}
                className={`home-notification notification-${item.kind}`}
                title={<span className="notification-title"><small>{item.scope}</small>{item.title}</span>}
                description={item.description}
                icon={<Icon style={{ color }} />}
                background={background} color="#eee9dd" fuseColor={color}
                duration={duration} width={360} radius={12} slideMs={280}
                inline closeButton closeLabel="Закрыть уведомление"
                role={item.kind === "error" ? "alert" : "status"}
                onClose={() => remove(item.id)}
              />
            );
          })}
        </aside>, target,
      )}
    </NotificationContext.Provider>
  );
}
