"use client";
import { useRef, useState } from "react";
import { api } from "@/lib/api";

type Analysis = {
  species: string | null;
  deficiencies: string[];
  diseases: string[];
  probabilities: Record<string, string>;
  height_cm: number | null;
  width_cm: number | null;
};

export default function PlantAnalysis({
  plantId,
  latest,
  onAnalyzed,
}: {
  plantId: number;
  latest: Analysis | null;
  onAnalyzed: (a: Analysis) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setLoading(true);
    setError(null);
    try {
      const result = await api.analyzePlantImage(plantId, file);
      onAnalyzed(result);
    } catch (e: any) {
      setError(e.message || "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg bg-neutral-900 p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">AI Plant Analysis</h3>
        <button
          onClick={() => inputRef.current?.click()}
          disabled={loading}
          className="rounded bg-leaf px-3 py-1 text-sm hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Analyzing…" : "Upload Photo"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
      </div>

      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}

      {latest ? (
        <div className="mt-3 space-y-2 text-sm">
          <p>
            <span className="text-neutral-400">Species: </span>
            {latest.species || "Unknown"}
          </p>
          {latest.diseases?.length > 0 && (
            <p>
              <span className="text-neutral-400">Diseases: </span>
              {latest.diseases.join(", ")}
            </p>
          )}
          {latest.deficiencies?.length > 0 ? (
            <p>
              <span className="text-neutral-400">Deficiencies: </span>
              {latest.deficiencies
                .map((d) => `${d} (${latest.probabilities?.[d] || "?"})`)
                .join(", ")}
            </p>
          ) : (
            <p className="text-neutral-400">No deficiencies detected.</p>
          )}
          {latest.height_cm && latest.width_cm && (
            <p>
              <span className="text-neutral-400">Size: </span>
              {latest.height_cm}cm × {latest.width_cm}cm
            </p>
          )}
        </div>
      ) : (
        <p className="mt-3 text-sm text-neutral-500">No analysis yet — upload a photo to get started.</p>
      )}
    </div>
  );
}
