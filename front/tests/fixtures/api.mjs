// Synthetic API for browser tests only. Never imported by application code.
import { createServer } from "node:http";
export const fixtureToken = "synthetic-browser-test-token";
const user = {
  id: "00000000-0000-4000-8000-000000000001",
  username: "conta_demonstracao",
  email: "demonstracao@example.org",
};
const uploadedResumeId = "00000000-0000-4000-8000-000000000099";
const optimizedResumeId = "00000000-0000-4000-8000-000000000098";
const attemptId = "00000000-0000-4000-8000-000000000077";
const interviewId = "00000000-0000-4000-8000-000000000066";
let uploadedText =
  "Ana Silva. Experiência acadêmica com desenvolvimento de aplicações, APIs e testes automatizados em projetos universitários.";
let uploadedTextConfirmed = false;
const uploadedResume = () => ({
  id: uploadedResumeId,
  tipo: "original",
  curriculo_origem_id: null,
  nome_arquivo: "Currículo sintético enviado.pdf",
  descricao_vaga:
    "Vaga de demonstração em desenvolvimento de software, APIs e testes.",
  texto_extraido: uploadedText,
  texto_confirmado: uploadedTextConfirmed,
  latex_gerado: null,
  latex_revisao: 0,
  pdf_revisao: null,
  template_versao: null,
  conteudo_estruturado: null,
  created_at: "2026-10-23T12:00:00Z",
  updated_at: "2026-10-23T12:00:00Z",
  pdf_disponivel: false,
  avisos: [],
});
const optimizedResume = () => ({
  id: optimizedResumeId,
  tipo: "otimizado",
  curriculo_origem_id: uploadedResumeId,
  nome_arquivo: "Versão otimizada — demonstração.tex",
  descricao_vaga: uploadedResume().descricao_vaga,
  texto_extraido: uploadedText,
  texto_confirmado: true,
  latex_gerado:
    "\\documentclass{article}\n\\begin{document}\nAna Silva — currículo sintético\\end{document}",
  latex_revisao: 1,
  pdf_revisao: null,
  template_versao: "synthetic-v1",
  conteudo_estruturado: null,
  created_at: "2026-10-23T12:00:00Z",
  updated_at: "2026-10-23T12:00:00Z",
  pdf_disponivel: false,
  tentativa_origem_id: attemptId,
  revisao_humana_confirmada: true,
  avisos: [],
});
const fact = {
  texto: "Desenvolvimento de aplicações acadêmicas",
  trecho_fonte: "desenvolvimento de aplicações",
  fonte: "Currículo original",
};
const attempt = () => ({
  id: attemptId,
  curriculo_id: uploadedResumeId,
  curriculo_gerado_id: optimizedResumeId,
  tipo_operacao: "otimizacao",
  status: "aguardando_revisao",
  etapa: "revisao",
  codigo_erro: null,
  mensagem_erro: null,
  modelo: "modelo-sintetico",
  tokens_entrada: 800,
  tokens_saida: 400,
  created_at: "2026-10-23T12:00:00Z",
  completed_at: null,
  expires_at: null,
  acompanhamento: `/v1/otimizacoes/${attemptId}`,
  proposta: {
    curriculo: {
      contato: [fact],
      resumo: fact,
      formacao: [],
      experiencias: [],
      projetos: [],
      competencias: [fact],
    },
    latex_gerado: optimizedResume().latex_gerado,
    alteracoes: [
      {
        secao: "Resumo profissional",
        antes: "Estudante de computação.",
        depois:
          "Estudante de computação com projetos acadêmicos de desenvolvimento de aplicações.",
        justificativa: "Organiza a experiência fornecida para leitura da vaga.",
        trecho_fonte:
          "Estudante de computação. Projeto acadêmico com desenvolvimento de aplicações.",
        fonte: "Currículo original",
        tipo: "reescrita",
      },
    ],
    palavras_chave_usadas: [
      {
        termo: "desenvolvimento de aplicações",
        evidencia_no_original: "desenvolvimento de aplicações",
        trecho_fonte: "Projeto acadêmico com desenvolvimento de aplicações.",
        fonte: "Currículo original",
      },
    ],
    lacunas: [
      {
        termo_da_vaga: "Liderança de equipe",
        motivo_para_nao_incluir:
          "Não há evidência dessa experiência no conteúdo revisado.",
      },
    ],
    versao_schema: 2,
    fontes_confirmadas: [],
    sessao_complementacao_id: null,
  },
});
const interview = () => ({
  id: interviewId,
  curriculo_id: uploadedResumeId,
  status: "aguardando_respostas",
  revisao: 1,
  rodada_atual: 1,
  created_at: "2026-10-23T12:00:00Z",
  expires_at: "2026-10-24T12:00:00Z",
  rodadas: [
    {
      id: "00000000-0000-4000-8000-000000000055",
      numero: 1,
      perguntas: [
        {
          id: "00000000-0000-4000-8000-000000000056",
          pergunta:
            "Que parte do seu projeto acadêmico você desenvolveu pessoalmente?",
          justificativa: "A vaga pede prática de desenvolvimento em equipe.",
          categoria: "projeto",
          termo_da_vaga: "desenvolvimento de aplicações",
          resposta_origem_id: null,
        },
      ],
      respostas: [],
      complemento_livre: null,
      complemento_livre_id: null,
      acao_apos_respostas: null,
      created_at: "2026-10-23T12:00:00Z",
    },
  ],
  complementos: [],
  conflitos: [],
  resolucoes: [],
  consentimento_em: "2026-10-23T12:00:00Z",
  consentimento_versao: "synthetic-v1",
  confirmado_em: null,
  tentativa_id: null,
  geracao_id: null,
  codigo_erro: null,
  mensagem_erro: null,
  acompanhamento: `/v1/complementacoes/${interviewId}`,
});
const resume = (index) => ({
  id: `00000000-0000-4000-8000-${String(index + 10).padStart(12, "0")}`,
  tipo: index === 1 ? "otimizado" : "original",
  nome_arquivo: [
    "Currículo — dados sintéticos.pdf",
    "Versão para revisão — demonstração.tex",
    "Experiência acadêmica — exemplo.docx",
  ][index % 3],
  texto_confirmado: index === 2,
  created_at: "2026-10-22T12:00:00Z",
  updated_at: "2026-10-22T12:00:00Z",
});
createServer(async (req, res) => {
  const url = new URL(req.url, "http://127.0.0.1");
  const send = (data, status = 200, headers = {}) => {
    res.writeHead(status, { "Content-Type": "application/json", ...headers });
    res.end(JSON.stringify(data));
  };
  if (url.pathname === "/health") return send({ ok: true });
  if (url.pathname === "/v1/auth/token") {
    let text = "";
    for await (const chunk of req) text += chunk;
    const params = new URLSearchParams(text);
    if (params.get("password") !== "senha-sintetica") return send({}, 401);
    return send({
      access_token:
        params.get("username") === "vazio"
          ? "empty-test-token"
          : params.get("username") === "falha"
            ? "error-test-token"
            : fixtureToken,
      token_type: "bearer",
      expires_in: 1800,
    });
  }
  if (url.pathname === "/v1/auth/register") return send(user, 201);
  const auth = req.headers.authorization;
  if (
    ![fixtureToken, "empty-test-token", "error-test-token"].some(
      (token) => auth === `Bearer ${token}`,
    )
  )
    return send({}, 401);
  if (url.pathname === "/v1/auth/me") return send(user);
  if (auth === "Bearer error-test-token") return send({}, 503);
  if (url.pathname === "/v1/uso")
    return send({
      limite: 5,
      usado: auth === "Bearer empty-test-token" ? 0 : 2,
      restante: auth === "Bearer empty-test-token" ? 5 : 3,
      inicio_periodo: "2026-10-01T00:00:00Z",
      proximo_reinicio: "2026-11-01T00:00:00Z",
    });
  if (url.pathname === `/v1/complementacoes/${interviewId}`)
    return send(interview());
  if (url.pathname === `/v1/otimizacoes/${attemptId}` && req.method === "GET")
    return send(attempt());
  if (url.pathname === `/v1/curriculos/${optimizedResumeId}`)
    return send(optimizedResume(), 200, { ETag: '"1"' });
  if (url.pathname === "/v1/curriculos" && req.method === "POST") {
    let bytes = 0;
    for await (const chunk of req) bytes += chunk.length;
    if (
      !bytes ||
      !req.headers["content-type"]?.startsWith("multipart/form-data;")
    )
      return send({ erro: { codigo: "validacao" } }, 400);
    uploadedTextConfirmed = false;
    return send(uploadedResume(), 201);
  }
  if (
    url.pathname === `/v1/curriculos/${uploadedResumeId}/texto-extraido` &&
    req.method === "PATCH"
  ) {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    const input = JSON.parse(raw);
    uploadedText = input.texto;
    uploadedTextConfirmed = true;
    return send(uploadedResume());
  }
  if (url.pathname === "/v1/curriculos" && req.method === "GET")
    return send({
      itens:
        auth === "Bearer empty-test-token"
          ? []
          : Array.from({ length: 3 }, (_, i) => resume(i)),
      total: auth === "Bearer empty-test-token" ? 0 : 3,
      pagina: Number(url.searchParams.get("pagina") ?? 1),
      tamanho: Number(url.searchParams.get("tamanho") ?? 4),
    });
  if (
    url.pathname === `/v1/curriculos/${uploadedResumeId}/complementacoes` &&
    req.method === "GET"
  )
    return send({
      itens: [
        {
          id: interviewId,
          curriculo_id: uploadedResumeId,
          status: "aguardando_respostas",
          revisao: 1,
          rodada_atual: 1,
          created_at: "2026-10-23T12:00:00Z",
          expires_at: "2026-10-24T12:00:00Z",
        },
      ],
      total: 1,
      pagina: 1,
      tamanho: 20,
    });
  if (url.pathname === "/v1/otimizacoes" && req.method === "GET")
    return send({
      itens: [
        {
          id: attemptId,
          curriculo_id: uploadedResumeId,
          curriculo_gerado_id: optimizedResumeId,
          sessao_complementacao_id: null,
          status: "aguardando_revisao",
          etapa: "revisao",
          codigo_erro: null,
          created_at: "2026-10-23T12:00:00Z",
          completed_at: null,
        },
      ],
      total: 1,
      pagina: 1,
      tamanho: 20,
    });
  if (url.pathname.startsWith("/v1/curriculos/")) {
    if (url.pathname === `/v1/curriculos/${uploadedResumeId}`)
      return send(uploadedResume());
    const item = Array.from({ length: 3 }, (_, i) => resume(i)).find(
      (r) => `/v1/curriculos/${r.id}` === url.pathname,
    );
    return send(item ?? {}, item ? 200 : 404);
  }
  send({}, 404);
}).listen(8011, "127.0.0.1");
