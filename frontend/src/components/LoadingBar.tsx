interface LoadingBarProps {
  visible: boolean;
}

export default function LoadingBar({ visible }: LoadingBarProps) {
  if (!visible) return null;

  return (
    <div className="w-full h-[2px] bg-border overflow-hidden rounded-full mt-1">
      <div
        className="h-full w-1/3 bg-primary rounded-full"
        style={{ animation: "loading-bar 1.5s linear infinite" }}
      />
    </div>
  );
}
