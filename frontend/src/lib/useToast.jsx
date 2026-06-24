import { useState, useCallback } from "react";

export function useToast() {
  const [toast, setToast] = useState(null);

  const show = useCallback((message, type = "ok") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 2600);
  }, []);

  const node = toast ? (
    <div className={`toast ${toast.type}`}>{toast.message}</div>
  ) : null;

  return { show, node };
}
