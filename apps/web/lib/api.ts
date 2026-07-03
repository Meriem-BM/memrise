import { MemriseClient } from "memrise-memory-sdk";

let client: MemriseClient | undefined;

// All requests go through the same-origin proxy at /api/memrise, which attaches
// the API key server-side. No credentials are exposed to the browser bundle.
export function getMemriseClient(): MemriseClient {
  client ??= new MemriseClient({ baseUrl: "/api/memrise" });
  return client;
}
