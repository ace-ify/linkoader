import { useState, useCallback } from "react";
import Header from "./components/Header";
import Footer from "./components/Footer";
import URLInput from "./components/URLInput";
import LoadingBar from "./components/LoadingBar";
import MediaPreview from "./components/MediaPreview";
import ErrorCard from "./components/ErrorCard";
import PlatformList from "./components/PlatformList";
import Toast from "./components/Toast";
import { useExtract } from "./hooks/useExtract";
import { isValidUrl } from "./lib/validate";

export default function App() {
  const [url, setUrl] = useState("");
  const { data, loading, error, retryAfter, extract, reset } = useExtract();
  const [toast, setToast] = useState<string | null>(null);
  const [lastUrl, setLastUrl] = useState("");

  const handleSubmit = useCallback(
    (inputUrl: string) => {
      if (!isValidUrl(inputUrl)) {
        setToast("Please enter a valid URL !!");
        return;
      }
      setUrl(inputUrl);
      setLastUrl(inputUrl);
      extract(inputUrl);
    },
    [extract]
  );

  const handleClear = useCallback(() => {
    setUrl("");
    setLastUrl("");
    reset();
  }, [reset]);

  const handleRetry = useCallback(() => {
    if (lastUrl) {
      extract(lastUrl);
    }
  }, [lastUrl, extract]);

  const handleDismissToast = useCallback(() => {
    setToast(null);
  }, []);

  // Show rate limit as toast
  const isRateLimited = error === "Too many requests.";
  const showError = error && !isRateLimited;

  return (
    <div className="min-h-screen bg-black text-primary flex flex-col">
      <Header />

      <main className="flex-1 flex flex-col items-center justify-center px-4 pb-16">
        <div className="w-full max-w-[640px]">
          {/* Tagline — hidden when preview or error is showing */}
          {!data && !showError && !loading && (
            <h1 className="text-center text-primary text-xl font-semibold tracking-tighter mb-8">
              Paste any link. Get the file.
            </h1>
          )}

          <URLInput
            value={url}
            onChange={setUrl}
            onSubmit={handleSubmit}
            onClear={handleClear}
            disabled={loading}
          />

          <LoadingBar visible={loading} />

          {data && <MediaPreview media={data} />}

          {showError && (
            <ErrorCard message={error} onRetry={handleRetry} />
          )}

          <PlatformList visible={!data && !showError && !loading} />
        </div>
      </main>

      <Toast
        message={
          isRateLimited && retryAfter
            ? `Too many requests. Try again in ${retryAfter}s.`
            : toast || ""
        }
        visible={isRateLimited || !!toast}
        onDismiss={handleDismissToast}
      />

      <Footer />
    </div>
  );
}
