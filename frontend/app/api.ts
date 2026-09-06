export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      ...(sessionStorage.getItem("agentwatch-api-key")
        ? { "X-API-Key": sessionStorage.getItem("agentwatch-api-key")! }
        : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 429) {
      const retry = response.headers.get("Retry-After") ?? "a few";
      throw new Error(
        `The shared demo is busy or its request budget is used. Retry in ${retry} seconds.`,
      );
    }
    const detail = await response.text();
    throw new Error(
      response.status === 401
        ? "API key required. Enter it in Connection settings."
        : `Request failed (${response.status}): ${detail.slice(0, 180)}`,
    );
  }
  return response.json() as Promise<T>;
}
