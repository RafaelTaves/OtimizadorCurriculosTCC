import "server-only";
import { NextResponse } from "next/server";
import { HttpError } from "@/lib/http/errors";

export function privateJson(data: unknown, status = 200) {
  return NextResponse.json(data, {
    status,
    headers: { "Cache-Control": "private, no-store" },
  });
}
export function errorResponse(error: unknown) {
  const known = error instanceof HttpError;
  return privateJson(
    {
      erro: {
        codigo: known ? error.code : "indisponivel",
        mensagem: known
          ? error.message
          : "O serviço está temporariamente indisponível. Tente novamente.",
      },
    },
    known ? error.status : 503,
  );
}
export function checkOrigin(request: Request) {
  const expected = new URL(process.env.APP_ORIGIN ?? "http://localhost:3000")
    .origin;
  if (request.headers.get("origin") !== expected)
    throw new HttpError(
      403,
      "origem_invalida",
      "Origem da solicitação não permitida.",
    );
}
export async function smallJson(request: Request): Promise<unknown> {
  if (!request.headers.get("content-type")?.startsWith("application/json"))
    throw new HttpError(415, "formato_invalido", "Envie os dados em JSON.");
  const reader = request.body?.getReader();
  if (!reader)
    throw new HttpError(
      400,
      "entrada_invalida",
      "Informe os dados solicitados.",
    );
  let bytes = 0;
  const chunks: Uint8Array[] = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    bytes += value.byteLength;
    if (bytes > 4096) {
      await reader.cancel();
      throw new HttpError(
        413,
        "entrada_grande",
        "Os dados excedem o limite permitido.",
      );
    }
    chunks.push(value);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new HttpError(400, "entrada_invalida", "Confira os dados enviados.");
  }
}
