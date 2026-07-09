type SensorData = {
  soil_moisture?: number | null;
  soil_temperature_c?: number | null;
  air_temperature_c?: number | null;
  air_humidity_pct?: number | null;
  light_intensity_lux?: number | null;
};

function Stat({ label, value, unit }: { label: string; value: number | null | undefined; unit: string }) {
  return (
    <div className="flex flex-col rounded-lg bg-neutral-900 p-4">
      <span className="text-xs uppercase tracking-wide text-neutral-400">{label}</span>
      <span className="mt-1 text-2xl font-semibold">
        {value === null || value === undefined ? "—" : `${value}${unit}`}
      </span>
    </div>
  );
}

export default function SensorCard({ data }: { data: SensorData }) {
  const moistureLabel = data.soil_moisture === 0 ? "Dry" : data.soil_moisture === 1 ? "Wet" : "—";

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <div className="flex flex-col rounded-lg bg-neutral-900 p-4">
        <span className="text-xs uppercase tracking-wide text-neutral-400">Soil Moisture</span>
        <span className="mt-1 text-2xl font-semibold">{moistureLabel}</span>
      </div>
      <Stat label="Soil Temp" value={data.soil_temperature_c ?? null} unit="°C" />
      <Stat label="Air Temp" value={data.air_temperature_c ?? null} unit="°C" />
      <Stat label="Air Humidity" value={data.air_humidity_pct ?? null} unit="%" />
      <Stat label="Light" value={data.light_intensity_lux ?? null} unit=" lux" />
    </div>
  );
}
