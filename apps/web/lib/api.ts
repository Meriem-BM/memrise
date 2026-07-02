import { MemoryClient } from "@memrise/sdk";

const baseUrl = process.env.NEXT_PUBLIC_MEMRISE_API_URL ?? "http://localhost:8000";
const apiKey = process.env.NEXT_PUBLIC_MEMRISE_API_KEY ?? "local-dev-key";

export function getMemoryClient() {
  return new MemoryClient({ baseUrl, apiKey });
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      ...init.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`API request failed with ${response.status}`);
  }
  return (await response.json()) as T;
}
