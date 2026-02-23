import { useEffect, useState } from "react";

interface ToastProps {
  message: string;
  visible: boolean;
  onDismiss: () => void;
}

export default function Toast({ message, visible, onDismiss }: ToastProps) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (visible) {
      setShow(true);
      const timer = setTimeout(() => {
        setShow(false);
        onDismiss();
      }, 5000);
      return () => clearTimeout(timer);
    } else {
      setShow(false);
    }
  }, [visible, onDismiss]);

  if (!show) return null;

  return (
    <div
      className="fixed bottom-12 left-1/2 -translate-x-1/2 z-50 bg-surface border border-border rounded-lg px-4 py-2.5 shadow-lg"
      style={{ animation: "toast-in 200ms ease-out" }}
    >
      <p className="text-secondary text-sm whitespace-nowrap">{message}</p>
    </div>
  );
}
