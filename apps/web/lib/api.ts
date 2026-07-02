import { MemriseClient } from "memrise-memory-sdk";

const baseUrl = process.env.NEXT_PUBLIC_MEMRISE_API_URL ?? "http://localhost:8000";
const apiKey = process.env.NEXT_PUBLIC_MEMRISE_API_KEY ?? "local-dev-key";

let client: MemriseClient | undefined;

export function getMemriseClient(): MemriseClient {
  client ??= new MemriseClient({ baseUrl, apiKey });
  return client;
}
