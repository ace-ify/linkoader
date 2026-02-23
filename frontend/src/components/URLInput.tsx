import { useRef, useEffect, useCallback } from "react";

interface URLInputProps {
  onSubmit: (url: string) => void;
  onClear: () => void;
  disabled: boolean;
  value: string;
  onChange: (value: string) => void;
}

export default function URLInput({
  onSubmit,
  onClear,
  disabled,
  value,
  onChange,
}: URLInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (trimmed && !disabled) {
      onSubmit(trimmed);
    }
  }, [value, disabled, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleSubmit();
      }
      if (e.key === "Escape") {
        onClear();
        inputRef.current?.focus();
      }
    },
    [handleSubmit, onClear]
  );

  const handlePaste = useCallback(
    (e: React.ClipboardEvent) => {
      const pasted = e.clipboardData.getData("text").trim();
      if (pasted) {
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => {
          onSubmit(pasted);
        }, 300);
      }
    },
    [onSubmit]
  );

  return (
    <div className="relative w-full">
      <input
        ref={inputRef}
        type="url"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        disabled={disabled}
        placeholder="https://"
        className="w-full bg-surface border border-border rounded-xl px-4 py-3.5 pr-20 text-primary text-sm placeholder:text-muted outline-none transition-colors focus:border-secondary/40 disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label="Paste a URL to download content"
      />

      {/* Clear button */}
      {value && !disabled && (
        <button
          onClick={() => {
            onClear();
            inputRef.current?.focus();
          }}
          className="absolute right-12 top-1/2 -translate-y-1/2 text-muted hover:text-secondary transition-colors p-1 cursor-pointer"
          aria-label="Clear input"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      )}

      {/* Submit button */}
      <button
        onClick={handleSubmit}
        disabled={disabled || !value.trim()}
        className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-muted hover:text-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
        aria-label="Extract content"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="5" y1="12" x2="19" y2="12" />
          <polyline points="12 5 19 12 12 19" />
        </svg>
      </button>
    </div>
  );
}
