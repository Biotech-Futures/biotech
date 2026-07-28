import { useCallback, useEffect, useRef, useState } from "react";

// Persist the deadline rather than the remaining count, so a refresh or a second
// tab can't reset a cooldown the server is still enforcing.
function storageKey(key: string) {
  return `send-cooldown:${key}`;
}

function readDeadline(key: string): number {
  try {
    return Number(window.localStorage.getItem(storageKey(key))) || 0;
  } catch {
    return 0;
  }
}

function writeDeadline(key: string, deadline: number) {
  try {
    window.localStorage.setItem(storageKey(key), String(deadline));
  } catch {
    /* storage unavailable — the server still enforces the gap */
  }
}

function remainingFrom(deadline: number) {
  return Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
}

export function useSendCooldown(key: string, defaultSeconds = 60) {
  const [secondsLeft, setSecondsLeft] = useState(() => remainingFrom(readDeadline(key)));
  const keyRef = useRef(key);
  keyRef.current = key;

  useEffect(() => {
    setSecondsLeft(remainingFrom(readDeadline(key)));
  }, [key]);

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const timer = setInterval(() => {
      setSecondsLeft(remainingFrom(readDeadline(keyRef.current)));
    }, 1000);
    return () => clearInterval(timer);
  }, [secondsLeft]);

  const start = useCallback(
    (seconds?: number) => {
      const total = Math.max(1, Math.round(seconds || defaultSeconds));
      writeDeadline(keyRef.current, Date.now() + total * 1000);
      setSecondsLeft(total);
    },
    [defaultSeconds],
  );

  return { secondsLeft, start };
}
