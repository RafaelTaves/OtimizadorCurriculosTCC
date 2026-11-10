export class HttpError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public retryAfter: string | null = null,
    public fields: Record<string, string> = {},
  ) {
    super(message);
  }
}
export type LoadResult<T> =
  { data: T; error?: never } | { data?: never; error: string };
export async function readResponse(response: Response): Promise<unknown> {
  const raw = await response.text().catch(() => "");
  let body: unknown = null;
  if (raw) {
    try {
      body = JSON.parse(raw) as unknown;
    } catch {
      body = null;
    }
  }
  if (!response.ok) {
    const error =
      body && typeof body === "object" && "erro" in body
        ? (body as { erro?: { codigo?: unknown; campos?: unknown } }).erro
        : undefined;
    const code =
      typeof error?.codigo === "string" ? error.codigo : "requisicao_falhou";
    const messages: Record<string, string> = {
      conta_existente:
        "Já existe uma conta com esse e-mail ou nome de usuário.",
      credenciais_invalidas: "E-mail, usuário ou senha não conferem.",
      token_invalido: "Sua sessão expirou. Entre novamente para continuar.",
      arquivo_vazio: "Selecione um arquivo que tenha conteúdo.",
      arquivo_grande: "O arquivo ultrapassa o limite de 10 MiB.",
      requisicao_grande: "O envio ultrapassa o limite permitido.",
      formato_nao_aceito: "Envie um arquivo PDF ou DOCX válido.",
      assinatura_invalida: "O arquivo não parece ser um PDF ou DOCX válido.",
      pdf_protegido: "Envie um PDF sem proteção por senha.",
      docx_protegido: "Envie um DOCX sem criptografia.",
      paginas_excedidas: "O PDF ultrapassa o limite de 10 páginas.",
      texto_insuficiente:
        "Não foi possível extrair texto. Use um PDF com texto selecionável ou um DOCX.",
      extracao_timeout:
        "A extração demorou mais do que o esperado. Você pode tentar novamente.",
      extracao_falhou:
        "Não foi possível ler o arquivo. Escolha outro arquivo ou tente novamente.",
      validacao: "Confira os campos informados e tente novamente.",
      texto_nao_confirmado:
        "Revise e confirme o texto extraído antes de continuar.",
      consentimento_obrigatorio:
        "Confirme o consentimento para enviar os dados à OpenAI.",
      cota_excedida: "Sua cota de otimizações deste período foi atingida.",
      limite_sessoes: "O limite diário de novas entrevistas foi atingido.",
      limite_analises: "O limite diário de análises foi atingido.",
      sessao_ativa: "Já existe uma entrevista ativa para este currículo.",
      contexto_alterado:
        "O texto do currículo ou a vaga mudou. Inicie um novo fluxo para usar o contexto atualizado.",
      estado_incompativel:
        "A entrevista mudou de estado. Atualizamos os dados para você continuar.",
      rodada_respondida:
        "Esta rodada já foi enviada. Consulte a entrevista atualizada.",
      sessao_ja_utilizada: "Esta entrevista já foi usada em uma geração.",
      chave_reutilizada:
        "Esta solicitação já foi iniciada com outros dados. Consulte o estado atual antes de tentar de novo.",
      resultado_expurgado:
        "Os dados temporários desta operação foram removidos. Consulte o estado da entrevista.",
      sessao_encerrada: "Esta entrevista foi cancelada ou expirou.",
      sessao_confirmada:
        "Esta entrevista já foi confirmada e não pode mais ser alterada.",
      sessao_inexistente: "Não foi possível encontrar esta entrevista.",
      revisao_obrigatoria: "Atualize os dados e tente novamente.",
      edicao_concorrente:
        "O documento mudou em outra edição. Compare as versões antes de salvar.",
      revisao_indisponivel: "A proposta ainda não está pronta para revisão.",
      revisao_pendente:
        "Confirme a revisão da proposta antes de editar ou exportar.",
      preview_expirada:
        "Esta prévia expirou. Gere uma nova prévia para continuar.",
      pdf_indisponivel: "O PDF ainda não está disponível para esta revisão.",
      compilacoes_excedidas: "Aguarde antes de solicitar outra compilação.",
      ia_nao_configurada: "A geração está temporariamente indisponível.",
      tentativa_inexistente: "Não foi possível encontrar esta tentativa.",
    };
    const fields: Record<string, string> = {};
    if (Array.isArray(error?.campos)) {
      for (const item of error.campos) {
        if (!item || typeof item !== "object" || !("campo" in item)) continue;
        const path = Array.isArray(item.campo)
          ? item.campo
              .filter(
                (part: unknown): part is string => typeof part === "string",
              )
              .join(".")
          : "";
        if (
          path === "descricao_vaga" ||
          path === "texto" ||
          path === "arquivo"
        ) {
          fields[path] = "Confira este campo e tente novamente.";
        }
      }
    }
    throw new HttpError(
      response.status,
      code,
      messages[code] ??
        "Não foi possível concluir esta solicitação. Tente novamente em instantes.",
      response.headers.get("retry-after"),
      fields,
    );
  }
  return body;
}

export async function browserRequest<T>(
  path: string,
  init: RequestInit,
  parse: (value: unknown) => T,
): Promise<{ data: T; status: number; headers: Headers }> {
  try {
    const response = await fetch(`/api/backend${path}`, {
      ...init,
      cache: "no-store",
    });
    const body = await readResponse(response);
    return {
      data: parse(body),
      status: response.status,
      headers: response.headers,
    };
  } catch (error) {
    if (error instanceof HttpError) throw error;
    if (error instanceof Error && error.name === "ZodError") {
      throw new HttpError(
        502,
        "contrato_invalido",
        "A resposta do serviço veio em um formato inesperado.",
      );
    }
    throw new HttpError(
      503,
      "indisponivel",
      "Não foi possível atualizar os dados. Verifique sua conexão e tente novamente.",
    );
  }
}

export async function browserFile(
  path: string,
  init?: RequestInit,
): Promise<Blob> {
  try {
    const response = await fetch(`/api/backend${path}`, {
      ...init,
      cache: "no-store",
    });
    if (!response.ok) {
      await readResponse(response);
      throw new HttpError(
        502,
        "contrato_invalido",
        "O serviço não retornou o arquivo solicitado.",
      );
    }
    const contentType = response.headers
      .get("content-type")
      ?.split(";")[0]
      .trim();
    if (
      contentType !== "application/pdf" &&
      contentType !== "application/x-tex"
    ) {
      throw new HttpError(
        502,
        "tipo_arquivo_invalido",
        "O serviço retornou um tipo de arquivo inesperado.",
      );
    }
    return await response.blob();
  } catch (error) {
    if (error instanceof HttpError) throw error;
    throw new HttpError(
      503,
      "indisponivel",
      "Não foi possível baixar o arquivo. Verifique sua conexão e tente novamente.",
    );
  }
}
export async function browserGet<T>(
  path: string,
  parse: (value: unknown) => T,
): Promise<T> {
  try {
    return parse(await readResponse(await fetch(path, { cache: "no-store" })));
  } catch (error) {
    if (error instanceof HttpError) throw error;
    throw new HttpError(
      503,
      "indisponivel",
      "Não foi possível atualizar os dados. Verifique sua conexão e tente novamente.",
    );
  }
}
