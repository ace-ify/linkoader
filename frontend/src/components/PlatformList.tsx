interface PlatformListProps {
  visible: boolean;
}

export default function PlatformList({ visible }: PlatformListProps) {
  if (!visible) return null;

  return (
    <p className="text-muted text-sm text-center mt-4">
      YouTube · Instagram · TikTok · Twitter/X · Pinterest · Facebook
    </p>
  );
}
