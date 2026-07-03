import type { NextRequest } from "next/server";

const API_URL = (process.env.MEMRISE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const API_KEY = process.env.MEMRISE_API_KEY ?? "local-dev-key";

// The browser talks to this proxy so the API key stays server-side.
async function proxy(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await params;
  const target = `${API_URL}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const response = await fetch(target, {
    method: request.method,
    headers: {
      authorization: `Bearer ${API_KEY}`,
      "content-type": request.headers.get("content-type") ?? "application/json",
    },
    body: hasBody ? await request.text() : undefined,
    cache: "no-store",
  });
  return new Response(response.body, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") ?? "application/json",
      "x-request-id": response.headers.get("x-request-id") ?? "",
    },
  });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
