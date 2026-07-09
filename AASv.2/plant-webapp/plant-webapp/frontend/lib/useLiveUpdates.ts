"use client";
import { useEffect, useRef, useState } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/live";

export type LiveEvent = {
  type: "sensor_update" | "irrigation_event" | "irrigation_stopped" | "tank_update" | "tanks_reset" | "fertilizer_event";
  [key: string]: any;
};

/** Subscribes to the backend's /ws/live socket and keeps the latest event
 * of each type available, plus a rolling log. Reconnects automatically. */
export function useLiveUpdates() {
  const [latest, setLatest] = useState<Record<string, LiveEvent>>({});
  const [log, setLog] = useState<LiveEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data: LiveEvent = JSON.parse(event.data);
          setLatest((prev) => ({ ...prev, [data.type]: data }));
          setLog((prev) => [data, ...prev].slice(0, 50));
        } catch {
          // ignore malformed frames
        }
      };

      ws.onclose = () => {
        if (!cancelled) setTimeout(connect, 2000); // simple reconnect backoff
      };
    }

    connect();
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, []);

  return { latest, log };
}
