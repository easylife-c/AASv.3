"use client";
import { useState } from "react";
import { api } from "@/lib/api";

type Tank = { nutrient: string; level_ml: number; updated_at: string };

export default function TankStatus({ tanks, onChange }: { tanks: Tank[]; onChange: () => void }) {
  const [refillAmount, setRefillAmount] = useState<Record<string, string>>({});

  async function handleRefill(nutrient: string) {
    const amount = parseFloat(refillAmount[nutrient] || "0");
    if (!amount || amount <= 0) return;
    await api.refillTank(nutrient, amount);
    setRefillAmount((prev) => ({ ...prev, [nutrient]: "" }));
    onChange();
  }

  async function handleReset(nutrient: string) {
    await api.resetTank(nutrient, 1000);
    onChange();
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {tanks.map((tank) => {
        const pct = Math.max(0, Math.min(100, (tank.level_ml / 1000) * 100));
        return (
          <div key={tank.nutrient} className="rounded-lg bg-neutral-900 p-4">
            <div className="flex items-center justify-between">
              <span className="font-semibold">{tank.nutrient} Tank</span>
              <span className="text-sm text-neutral-400">{tank.level_ml.toFixed(0)} ml</span>
            </div>
            <div className="mt-2 h-2 w-full overflow-hidden rounded bg-neutral-800">
              <div
                className={`h-full ${pct < 20 ? "bg-red-500" : "bg-leaf"}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="mt-3 flex gap-2">
              <input
                type="number"
                placeholder="ml"
                value={refillAmount[tank.nutrient] || ""}
                onChange={(e) => setRefillAmount((prev) => ({ ...prev, [tank.nutrient]: e.target.value }))}
                className="w-20 rounded bg-neutral-800 px-2 py-1 text-sm"
              />
              <button
                onClick={() => handleRefill(tank.nutrient)}
                className="rounded bg-leaf px-2 py-1 text-sm hover:opacity-90"
              >
                Refill
              </button>
              <button
                onClick={() => handleReset(tank.nutrient)}
                className="rounded bg-neutral-700 px-2 py-1 text-sm hover:opacity-90"
              >
                Reset
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
