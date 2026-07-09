"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useLiveUpdates } from "@/lib/useLiveUpdates";
import SensorCard from "@/components/SensorCard";
import TankStatus from "@/components/TankStatus";
import PlantAnalysis from "@/components/PlantAnalysis";

export default function DashboardPage() {
  const [plants, setPlants] = useState<any[]>([]);
  const [selectedPlantId, setSelectedPlantId] = useState<number | null>(null);
  const [tanks, setTanks] = useState<any[]>([]);
  const [sensorData, setSensorData] = useState<any>({});
  const [latestAnalysis, setLatestAnalysis] = useState<any>(null);
  const [fertHistory, setFertHistory] = useState<any[]>([]);
  const [irrigationHistory, setIrrigationHistory] = useState<any[]>([]);
  const { latest } = useLiveUpdates();

  const loadTanks = useCallback(() => api.getTanks().then(setTanks).catch(() => {}), []);

  useEffect(() => {
    api.getPlants().then((p) => {
      setPlants(p);
      if (p.length && !selectedPlantId) setSelectedPlantId(p[0].id);
    }).catch(() => {});
    loadTanks();
    api.getLiveSensors().then(setSensorData).catch(() => {});
  }, [loadTanks, selectedPlantId]);

  useEffect(() => {
    if (!selectedPlantId) return;
    api.getAnalysisHistory(selectedPlantId).then((h) => setLatestAnalysis(h[0] || null)).catch(() => {});
    api.getFertilizerHistory(selectedPlantId).then(setFertHistory).catch(() => {});
    api.getIrrigationHistory(selectedPlantId).then(setIrrigationHistory).catch(() => {});
  }, [selectedPlantId]);

  // Live sensor push from WebSocket overrides the last polled snapshot
  useEffect(() => {
    if (latest.sensor_update) setSensorData(latest.sensor_update.data);
    if (latest.tank_update || latest.tanks_reset) loadTanks();
  }, [latest, loadTanks]);

  async function handleIrrigate() {
    if (!selectedPlantId) return;
    await api.startIrrigation(selectedPlantId, 50);
    api.getIrrigationHistory(selectedPlantId).then(setIrrigationHistory).catch(() => {});
  }

  const selectedPlant = plants.find((p) => p.id === selectedPlantId);

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-leaf">🌱 Plant Care Dashboard</h1>
        {plants.length > 0 && (
          <select
            value={selectedPlantId ?? ""}
            onChange={(e) => setSelectedPlantId(Number(e.target.value))}
            className="rounded bg-neutral-800 px-3 py-2"
          >
            {plants.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        )}
      </header>

      <section>
        <h2 className="mb-2 text-sm uppercase tracking-wide text-neutral-400">Sensors</h2>
        <SensorCard data={sensorData} />
      </section>

      <section>
        <h2 className="mb-2 text-sm uppercase tracking-wide text-neutral-400">Fertilizer Tanks</h2>
        <TankStatus tanks={tanks} onChange={loadTanks} />
      </section>

      {selectedPlantId && (
        <section>
          <h2 className="mb-2 text-sm uppercase tracking-wide text-neutral-400">
            {selectedPlant?.name || "Plant"} — AI Analysis
          </h2>
          <PlantAnalysis
            plantId={selectedPlantId}
            latest={latestAnalysis}
            onAnalyzed={(a) => setLatestAnalysis(a)}
          />
        </section>
      )}

      <section className="flex gap-3">
        <button onClick={handleIrrigate} className="rounded bg-blue-600 px-4 py-2 font-medium hover:opacity-90">
          💧 Irrigate Now (50ml)
        </button>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg bg-neutral-900 p-4">
          <h3 className="mb-2 font-semibold">Fertilizer History</h3>
          <ul className="space-y-1 text-sm text-neutral-300">
            {fertHistory.slice(0, 8).map((f) => (
              <li key={f.id}>
                {new Date(f.applied_at).toLocaleString()} — {f.nutrient}: {f.amount_ml}ml ({f.status})
              </li>
            ))}
            {fertHistory.length === 0 && <li className="text-neutral-500">No history yet.</li>}
          </ul>
        </div>
        <div className="rounded-lg bg-neutral-900 p-4">
          <h3 className="mb-2 font-semibold">Irrigation History</h3>
          <ul className="space-y-1 text-sm text-neutral-300">
            {irrigationHistory.slice(0, 8).map((i) => (
              <li key={i.id}>
                {new Date(i.recorded_at).toLocaleString()} — {i.amount_ml}ml ({i.trigger})
              </li>
            ))}
            {irrigationHistory.length === 0 && <li className="text-neutral-500">No history yet.</li>}
          </ul>
        </div>
      </section>
    </main>
  );
}
