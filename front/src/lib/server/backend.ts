import "server-only";
import { HttpError, readResponse } from "@/lib/http/errors";

export async function backend(
  path: string,
  token?: string,
  init?: RequestInit,
): Promise<unknown> {
  return readResponse(await backendRequest(path, token, init));
}

export async function backendRequest(
  path: string,
  token?: string,
  init?: RequestInit,
  timeoutMs = 10_000,
): Promise<Response> {
  const base = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  try {
    return await fetch(`${base}${path}`, {
      ...init,
      headers,
      cache: "no-store",
      redirect: "error",
      signal: init?.signal
        ? AbortSignal.any([init.signal, AbortSignal.timeout(timeoutMs)])
        : AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    if (init?.signal?.aborted) throw error;
    throw new HttpError(
      503,
      error instanceof DOMException && error.name === "TimeoutError"
        ? "tempo_esgotado"
        : "api_indisponivel",
      error instanceof DOMException && error.name === "TimeoutError"
        ? "A solicitação demorou mais do que o esperado. Tente novamente."
        : "O serviço está temporariamente indisponível. Tente novamente em instantes.",
    );
  }
}
