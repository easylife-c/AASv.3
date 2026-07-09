const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body && !(options.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  login: (username: string, password: string) => {
    const form = new URLSearchParams();
    form.set("username", username);
    form.set("password", password);
    return fetch(`${API_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    }).then((r) => r.json());
  },

  getPlants: () => request<any[]>("/api/plants"),
  createPlant: (data: any) => request<any>("/api/plants", { method: "POST", body: JSON.stringify(data) }),

  getTanks: () => request<any[]>("/api/tanks"),
  refillTank: (nutrient: string, amount_ml: number) =>
    request<any>("/api/tanks/refill", { method: "POST", body: JSON.stringify({ nutrient, amount_ml }) }),
  resetTank: (nutrient: string, level_ml = 1000) =>
    request<any>("/api/tanks/reset", { method: "POST", body: JSON.stringify({ nutrient, level_ml }) }),

  getLiveSensors: () => request<any>("/api/sensors/live"),
  getSensorHistory: (plantId: number) => request<any[]>(`/api/sensors/history/${plantId}`),

  analyzePlantImage: (plantId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<any>(`/api/analysis/${plantId}/analyze`, { method: "POST", body: formData });
  },
  getAnalysisHistory: (plantId: number) => request<any[]>(`/api/analysis/${plantId}/history`),

  applyFertilizer: (payload: any) =>
    request<any>("/api/fertilizer/apply", { method: "POST", body: JSON.stringify(payload) }),
  getFertilizerHistory: (plantId: number) => request<any[]>(`/api/fertilizer/history/${plantId}`),

  startIrrigation: (plant_id: number, amount_ml: number) =>
    request<any>("/api/irrigation/start", { method: "POST", body: JSON.stringify({ plant_id, amount_ml }) }),
  stopIrrigation: () => request<any>("/api/irrigation/stop", { method: "POST" }),
  getIrrigationHistory: (plantId: number) => request<any[]>(`/api/irrigation/history/${plantId}`),
};
