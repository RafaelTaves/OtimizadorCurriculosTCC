import { NextResponse, type NextRequest } from "next/server";
import { HttpError } from "@/lib/http/errors";
import { backendRequest } from "@/lib/server/backend";
import { errorResponse, checkOrigin } from "@/lib/server/route-utils";
import { session } from "@/lib/server/session";

const UUID =
  "[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}";
const patterns: Array<{
  regex: RegExp;
  methods: string[];
  bodyLimit?: number;
}> = [
  { regex: /^v1\/uso$/, methods: ["GET"] },
  {
    regex: /^v1\/curriculos$/,
    methods: ["GET", "POST"],
    bodyLimit: 10 * 1024 * 1024 + 100_000,
  },
  { regex: /^v1\/otimizacoes$/, methods: ["GET"] },
  { regex: new RegExp(`^v1/curriculos/${UUID}$`), methods: ["GET", "DELETE"] },
  {
    regex: new RegExp(`^v1/curriculos/${UUID}/texto-extraido$`),
    methods: ["PATCH"],
    bodyLimit: 600_000,
  },
  {
    regex: new RegExp(`^v1/curriculos/${UUID}/otimizacoes$`),
    methods: ["POST"],
    bodyLimit: 64_000,
  },
  {
    regex: new RegExp(`^v1/curriculos/${UUID}/latex$`),
    methods: ["PUT"],
    bodyLimit: 1_300_000,
  },
  {
    regex: new RegExp(`^v1/curriculos/${UUID}/preview$`),
    methods: ["POST"],
    bodyLimit: 1_300_000,
  },
  {
    regex: new RegExp(`^v1/curriculos/${UUID}/renderizacoes$`),
    methods: ["POST"],
  },
  { regex: new RegExp(`^v1/curriculos/${UUID}/download$`), methods: ["GET"] },
  {
    regex: new RegExp(`^v1/curriculos/${UUID}/complementacoes$`),
    methods: ["GET", "POST"],
    bodyLimit: 64_000,
  },
  { regex: new RegExp(`^v1/otimizacoes/${UUID}$`), methods: ["GET"] },
  {
    regex: new RegExp(`^v1/otimizacoes/${UUID}/confirmacao$`),
    methods: ["POST"],
  },
  { regex: new RegExp(`^v1/previews/${UUID}$`), methods: ["GET"] },
  { regex: new RegExp(`^v1/previews/${UUID}/download$`), methods: ["GET"] },
  { regex: new RegExp(`^v1/renderizacoes/${UUID}$`), methods: ["GET"] },
  { regex: new RegExp(`^v1/complementacoes/${UUID}$`), methods: ["GET"] },
  {
    regex: new RegExp(`^v1/complementacoes/${UUID}/respostas$`),
    methods: ["POST"],
    bodyLimit: 600_000,
  },
  {
    regex: new RegExp(`^v1/complementacoes/${UUID}/complementos$`),
    methods: ["PUT"],
    bodyLimit: 600_000,
  },
  {
    regex: new RegExp(`^v1/complementacoes/${UUID}/confirmacao$`),
    methods: ["POST"],
    bodyLimit: 64_000,
  },
  {
    regex: new RegExp(`^v1/complementacoes/${UUID}/cancelamento$`),
    methods: ["POST"],
  },
  {
    regex: new RegExp(`^v1/complementacoes/${UUID}/retentativas$`),
    methods: ["POST"],
  },
];

function privateJson(value: unknown, status: number) {
  return NextResponse.json(value, {
    status,
    headers: {
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

async function limitedBody(
  request: Request,
  limit: number,
): Promise<Uint8Array> {
  const length = request.headers.get("content-length");
  if (length && (!/^\d+$/.test(length) || Number(length) > limit)) {
    throw new HttpError(
      413,
      "requisicao_grande",
      "O envio ultrapassa o limite permitido.",
    );
  }
  const reader = request.body?.getReader();
  if (!reader) return new Uint8Array();
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > limit) {
      await reader.cancel();
      throw new HttpError(
        413,
        "requisicao_grande",
        "O envio ultrapassa o limite permitido.",
      );
    }
    chunks.push(value);
  }
  const output = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return output;
}

function filteredQuery(request: NextRequest, path: string) {
  const source = request.nextUrl.searchParams;
  const allowed =
    path === "v1/curriculos"
      ? ["pagina", "tamanho"]
      : new RegExp(`^v1/curriculos/${UUID}/complementacoes$`).test(path)
        ? ["pagina", "tamanho"]
        : path === "v1/otimizacoes"
          ? ["curriculo_id", "pagina", "tamanho"]
          : path.endsWith("/download")
            ? ["formato"]
            : [];
  const query = new URLSearchParams();
  for (const key of allowed) {
    const value = source.get(key);
    if (value === null) continue;
    if ((key === "pagina" || key === "tamanho") && !/^\d{1,3}$/.test(value)) {
      throw new HttpError(
        400,
        "consulta_invalida",
        "Confira os filtros informados.",
      );
    }
    if (key === "formato" && value !== "pdf" && value !== "tex") {
      throw new HttpError(
        400,
        "consulta_invalida",
        "Escolha um formato de download válido.",
      );
    }
    if (key === "curriculo_id" && !new RegExp(`^${UUID}$`, "i").test(value)) {
      throw new HttpError(
        400,
        "consulta_invalida",
        "O identificador do currículo é inválido.",
      );
    }
    query.set(key, value);
  }
  if ([...source.keys()].some((key) => !allowed.includes(key))) {
    throw new HttpError(
      400,
      "consulta_invalida",
      "A consulta contém filtros não permitidos.",
    );
  }
  return query.size ? `?${query.toString()}` : "";
}

function rewriteLinks(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(rewriteLinks);
  if (!value || typeof value !== "object") return value;
  const result: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) {
    if (
      (key === "acompanhamento" || key === "download_pdf") &&
      typeof item === "string" &&
      item.startsWith("/v1/")
    ) {
      result[key] = `/api/backend${item}`;
    } else {
      result[key] = rewriteLinks(item);
    }
  }
  return result;
}

function projectResumeHistory(value: unknown): unknown {
  if (
    !value ||
    typeof value !== "object" ||
    !("itens" in value) ||
    !Array.isArray(value.itens)
  )
    return value;
  const page = value as Record<string, unknown> & { itens: unknown[] };
  return {
    ...page,
    itens: page.itens.map((item) => {
      if (!item || typeof item !== "object") return null;
      const resume = item as Record<string, unknown>;
      return {
        id: resume.id,
        nome_arquivo: resume.nome_arquivo,
        tipo: resume.tipo,
        texto_confirmado: resume.texto_confirmado,
        created_at: resume.created_at,
        updated_at: resume.updated_at,
        tentativa_origem_id: resume.tentativa_origem_id,
        revisao_humana_confirmada: resume.revisao_humana_confirmada,
      };
    }),
  };
}

function forwardHeaders(response: Response) {
  const headers = new Headers({
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
  });
  for (const name of [
    "content-type",
    "content-disposition",
    "etag",
    "retry-after",
  ]) {
    const value = response.headers.get(name);
    if (value) headers.set(name, value);
  }
  const location = response.headers.get("location");
  if (location?.startsWith("/v1/"))
    headers.set("Location", `/api/backend${location}`);
  return headers;
}

async function handle(request: NextRequest, segments: string[]) {
  const path = segments.join("/");
  const route = patterns.find((item) => item.regex.test(path));
  if (!route)
    return privateJson(
      {
        erro: {
          codigo: "recurso_inexistente",
          mensagem: "Recurso não encontrado.",
        },
      },
      404,
    );
  if (!route.methods.includes(request.method)) {
    return privateJson(
      {
        erro: {
          codigo: "metodo_nao_permitido",
          mensagem: "Método não permitido.",
        },
      },
      405,
    );
  }
  if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method))
    checkOrigin(request);
  const current = await session();
  if (!current)
    throw new HttpError(
      401,
      "token_invalido",
      "Sua sessão expirou. Entre novamente para continuar.",
    );

  const headers = new Headers();
  for (const name of ["if-match", "idempotency-key"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  let body: BodyInit | undefined;
  const bodyRequired = !(
    request.method === "POST" &&
    (path.endsWith("/cancelamento") ||
      path.endsWith("/retentativas") ||
      path.endsWith("/renderizacoes") ||
      new RegExp(`^v1/otimizacoes/${UUID}/confirmacao$`).test(path))
  );
  if (
    (request.method === "POST" ||
      request.method === "PUT" ||
      request.method === "PATCH") &&
    bodyRequired
  ) {
    const limit = route.bodyLimit ?? 600_000;
    const bytes = await limitedBody(request, limit);
    if (path === "v1/curriculos" && request.method === "POST") {
      if (
        !request.headers
          .get("content-type")
          ?.toLowerCase()
          .startsWith("multipart/form-data;")
      ) {
        throw new HttpError(
          415,
          "formato_invalido",
          "Envie arquivo PDF ou DOCX e a descrição da vaga.",
        );
      }
      const buffer = bytes.buffer.slice(
        bytes.byteOffset,
        bytes.byteOffset + bytes.byteLength,
      ) as ArrayBuffer;
      const form = await new Response(buffer, {
        headers: { "Content-Type": request.headers.get("content-type") ?? "" },
      }).formData();
      const keys = [...form.keys()];
      const files = form.getAll("arquivo");
      const descriptions = form.getAll("descricao_vaga");
      if (
        keys.some((key) => key !== "arquivo" && key !== "descricao_vaga") ||
        files.length !== 1 ||
        descriptions.length !== 1 ||
        typeof descriptions[0] !== "string" ||
        !(files[0] instanceof File)
      ) {
        throw new HttpError(
          400,
          "entrada_invalida",
          "Envie um único arquivo e uma descrição de vaga.",
        );
      }
      if (files[0].size > 10 * 1024 * 1024 || files[0].size === 0) {
        throw new HttpError(
          files[0].size === 0 ? 422 : 413,
          files[0].size === 0 ? "arquivo_vazio" : "arquivo_grande",
          files[0].size === 0
            ? "Selecione um arquivo que tenha conteúdo."
            : "O arquivo ultrapassa o limite de 10 MiB.",
        );
      }
      const outgoing = new FormData();
      outgoing.append(
        "arquivo",
        new File([files[0]], files[0].name, { type: files[0].type }),
      );
      outgoing.append("descricao_vaga", descriptions[0]);
      body = outgoing;
    } else {
      const contentType = request.headers.get("content-type") ?? "";
      if (!contentType.toLowerCase().startsWith("application/json")) {
        throw new HttpError(415, "formato_invalido", "Envie os dados em JSON.");
      }
      headers.set("Content-Type", "application/json");
      body = bytes.buffer.slice(
        bytes.byteOffset,
        bytes.byteOffset + bytes.byteLength,
      ) as ArrayBuffer;
    }
  }
  const query = filteredQuery(request, path);
  const upstream = await backendRequest(
    `/v1/${segments.slice(1).join("/")}${query}`,
    current.token,
    {
      method: request.method,
      headers,
      body,
      signal: request.signal,
    },
    path === "v1/curriculos" && request.method === "POST" ? 60_000 : 10_000,
  );

  if (upstream.status === 204)
    return new NextResponse(null, {
      status: 204,
      headers: forwardHeaders(upstream),
    });
  const contentType = upstream.headers
    .get("content-type")
    ?.split(";")[0]
    .trim();
  if (
    contentType === "application/pdf" ||
    contentType === "application/x-tex"
  ) {
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: forwardHeaders(upstream),
    });
  }
  if (!contentType?.includes("json")) {
    return privateJson(
      {
        erro: {
          codigo: "resposta_invalida",
          mensagem: "O serviço retornou uma resposta inesperada.",
        },
      },
      502,
    );
  }
  const payload: unknown = await upstream.json().catch(() => null);
  if (!upstream.ok) {
    const record =
      payload && typeof payload === "object"
        ? (payload as Record<string, unknown>)
        : {};
    const error =
      record.erro && typeof record.erro === "object"
        ? (record.erro as Record<string, unknown>)
        : {};
    const safeError = {
      erro: {
        codigo:
          typeof error.codigo === "string" ? error.codigo : "requisicao_falhou",
        mensagem:
          typeof error.mensagem === "string" && error.mensagem.length <= 500
            ? error.mensagem
            : "Não foi possível concluir esta solicitação.",
        ...(Array.isArray(error.campos) ? { campos: error.campos } : {}),
      },
    };
    return NextResponse.json(safeError, {
      status: upstream.status,
      headers: forwardHeaders(upstream),
    });
  }
  const projected =
    path === "v1/curriculos" && request.method === "GET"
      ? projectResumeHistory(payload)
      : payload;
  return NextResponse.json(rewriteLinks(projected), {
    status: upstream.status,
    headers: forwardHeaders(upstream),
  });
}

async function route(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  try {
    const { path } = await context.params;
    return await handle(request, path);
  } catch (error) {
    return errorResponse(error);
  }
}

export const GET = route;
export const POST = route;
export const PUT = route;
export const PATCH = route;
export const DELETE = route;
