interface ErrorCardProps {
  message: string;
  onRetry: () => void;
}

export default function ErrorCard({ message, onRetry }: ErrorCardProps) {
  return (
    <div
      className="mt-6 bg-surface border border-error-border rounded-xl p-6 text-center"
      style={{ animation: "slide-up 200ms ease-out" }}
    >
      <p className="text-secondary text-sm">{message}</p>
      <button
        onClick={onRetry}
        className="mt-4 py-2.5 px-6 rounded-lg text-sm font-semibold border border-border text-primary hover:bg-surface-hover hover:border-secondary/30 transition-all duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20"
      >
        Try again
      </button>
    </div>
  );
}
