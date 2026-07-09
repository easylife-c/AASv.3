"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const data = await api.login(username, password);
      if (!data.access_token) throw new Error("Invalid credentials");
      localStorage.setItem("token", data.access_token);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Login failed");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-lg bg-neutral-900 p-6">
        <h1 className="mb-4 text-xl font-semibold text-leaf">Plant Care Login</h1>
        <input
          className="mb-3 w-full rounded bg-neutral-800 px-3 py-2"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          type="password"
          className="mb-4 w-full rounded bg-neutral-800 px-3 py-2"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="mb-3 text-sm text-red-400">{error}</p>}
        <button type="submit" className="w-full rounded bg-leaf px-3 py-2 font-medium hover:opacity-90">
          Log In
        </button>
      </form>
    </main>
  );
}
