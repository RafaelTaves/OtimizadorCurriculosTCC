import { z } from "zod";
import type { components } from "@/generated/api";

export type User = components["schemas"]["UserView"];
export type Usage = components["schemas"]["UsageView"];
export type Resume = components["schemas"]["ResumeView"];
export type ResumePage = components["schemas"]["ResumePage"];
export type Interview = components["schemas"]["InterviewView"];
export type InterviewPage = components["schemas"]["InterviewPage"];
export type Complement = components["schemas"]["Complement"];
export type Attempt = components["schemas"]["AttemptView"];
export type Proposal = components["schemas"]["Proposal"];
export type AttemptPage = components["schemas"]["AttemptPage"];
export const userSchema = z.object({
  id: z.uuid(),
  username: z.string(),
  email: z.email(),
});
export const tokenSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.literal("bearer"),
  expires_in: z.number().int().positive().max(7200),
});
export const usageSchema = z.object({
  limite: z.number().int().nonnegative(),
  usado: z.number().int().nonnegative(),
  restante: z.number().int().nonnegative(),
  inicio_periodo: z.iso.datetime({ offset: true }),
  proximo_reinicio: z.iso.datetime({ offset: true }),
});
// Only metadata needed by this phase crosses into browser components.
export const resumeSummarySchema = z.object({
  id: z.uuid(),
  nome_arquivo: z.string(),
  tipo: z.enum(["original", "otimizado"]),
  texto_confirmado: z.boolean(),
  created_at: z.iso.datetime({ offset: true }),
  updated_at: z.iso.datetime({ offset: true }),
  tentativa_origem_id: z.uuid().nullable().optional(),
  revisao_humana_confirmada: z.boolean().optional(),
});
export const resumePageSchema = z.object({
  itens: z.array(resumeSummarySchema),
  total: z.number().int().nonnegative(),
  pagina: z.number().int().positive(),
  tamanho: z.number().int().positive(),
});
export const resumeDetailSchema = z.object({
  id: z.uuid(),
  tipo: z.enum(["original", "otimizado"]),
  curriculo_origem_id: z.uuid().nullable(),
  nome_arquivo: z.string(),
  descricao_vaga: z.string().nullable(),
  texto_extraido: z.string().nullable(),
  texto_confirmado: z.boolean(),
  latex_gerado: z.string().nullable(),
  latex_revisao: z.number().int().nonnegative(),
  pdf_revisao: z.number().int().nullable(),
  template_versao: z.string().nullable(),
  conteudo_estruturado: z.record(z.string(), z.unknown()).nullable(),
  created_at: z.iso.datetime({ offset: true }),
  updated_at: z.iso.datetime({ offset: true }),
  tentativa_origem_id: z.uuid().nullable().optional(),
  revisao_humana_confirmada: z.boolean().optional(),
  pdf_disponivel: z.boolean(),
  download_pdf: z.string().nullable().optional(),
  avisos: z.array(z.string()).default([]),
});
const factSchema = z.object({
  texto: z.string(),
  trecho_fonte: z.string(),
  fonte: z.string(),
});
const entrySchema = z.object({
  titulo: factSchema,
  instituicao: factSchema.nullable(),
  periodo: factSchema.nullable(),
  itens: z.array(factSchema),
});
export const proposalSchema = z.object({
  curriculo: z.object({
    contato: z.array(factSchema),
    resumo: factSchema.nullable(),
    formacao: z.array(entrySchema),
    experiencias: z.array(entrySchema),
    projetos: z.array(entrySchema),
    competencias: z.array(factSchema),
  }),
  latex_gerado: z.string(),
  alteracoes: z.array(
    z.object({
      secao: z.string(),
      antes: z.string().nullable(),
      depois: z.string(),
      justificativa: z.string(),
      trecho_fonte: z.string(),
      fonte: z.string(),
      tipo: z.enum(["reescrita", "inclusao"]),
    }),
  ),
  palavras_chave_usadas: z.array(
    z.object({
      termo: z.string(),
      evidencia_no_original: z.string().nullable().optional(),
      trecho_fonte: z.string().nullable().optional(),
      fonte: z.string(),
    }),
  ),
  lacunas: z.array(
    z.object({
      termo_da_vaga: z.string(),
      motivo_para_nao_incluir: z.string(),
    }),
  ),
  versao_schema: z.union([z.literal(1), z.literal(2)]).default(1),
  fontes_confirmadas: z
    .array(
      z.object({
        id: z.uuid(),
        texto: z.string(),
        resposta_origem_id: z.uuid().nullable().optional(),
        substitui_trecho_original: z.string().nullable().optional(),
      }),
    )
    .default([]),
  sessao_complementacao_id: z.uuid().nullable().optional(),
});
export const attemptSchema = z.object({
  id: z.uuid(),
  curriculo_id: z.uuid().nullable(),
  curriculo_gerado_id: z.uuid().nullable(),
  tipo_operacao: z.string(),
  status: z.string(),
  etapa: z.string(),
  codigo_erro: z.string().nullable(),
  mensagem_erro: z.string().nullable(),
  modelo: z.string().nullable(),
  tokens_entrada: z.number().nullable(),
  tokens_saida: z.number().nullable(),
  created_at: z.iso.datetime({ offset: true }),
  completed_at: z.iso.datetime({ offset: true }).nullable(),
  expires_at: z.iso.datetime({ offset: true }).nullable(),
  acompanhamento: z.string(),
  proposta: proposalSchema.nullable().optional(),
  download_pdf: z.string().nullable().optional(),
});
export const attemptPageSchema = z.object({
  itens: z.array(
    z.object({
      id: z.uuid(),
      curriculo_id: z.uuid(),
      curriculo_gerado_id: z.uuid().nullable(),
      sessao_complementacao_id: z.uuid().nullable(),
      status: z.string(),
      etapa: z.string(),
      codigo_erro: z.string().nullable(),
      created_at: z.iso.datetime({ offset: true }),
      completed_at: z.iso.datetime({ offset: true }).nullable(),
    }),
  ),
  total: z.number().int().nonnegative(),
  pagina: z.number().int().positive(),
  tamanho: z.number().int().positive(),
});
const questionSchema = z.object({
  id: z.uuid(),
  pergunta: z.string(),
  justificativa: z.string(),
  categoria: z.enum([
    "projeto",
    "experiencia",
    "formacao",
    "competencia",
    "outro",
  ]),
  termo_da_vaga: z.string().nullable().optional(),
  resposta_origem_id: z.uuid().nullable().optional(),
});
const answerSchema = z.object({
  id: z.uuid(),
  pergunta_id: z.uuid(),
  texto: z.string().nullable().optional(),
  pulada: z.boolean(),
  negativa: z.boolean(),
});
const roundSchema = z.object({
  id: z.uuid(),
  numero: z.number().int(),
  perguntas: z.array(questionSchema),
  respostas: z.array(answerSchema),
  complemento_livre: z.string().nullable(),
  complemento_livre_id: z.uuid().nullable(),
  acao_apos_respostas: z.string().nullable(),
  created_at: z.iso.datetime({ offset: true }),
});
const complementSchema = z.object({
  id: z.uuid(),
  texto: z.string(),
  resposta_origem_id: z.uuid().nullable().optional(),
  substitui_trecho_original: z.string().nullable().optional(),
});
const conflictSchema = z.object({
  id: z.uuid(),
  resposta_origem_id: z.uuid(),
  trecho_original: z.string(),
  trecho_resposta: z.string(),
  descricao: z.string(),
});
const resolutionSchema = z.object({
  conflito_id: z.uuid(),
  acao: z.enum(["manter_original", "usar_complemento"]),
  complemento_id: z.uuid().nullable().optional(),
});
const interviewSummarySchema = z.object({
  id: z.uuid(),
  curriculo_id: z.uuid().nullable(),
  status: z.enum([
    "analisando",
    "aguardando_respostas",
    "aguardando_confirmacao",
    "confirmada",
    "falhou",
    "cancelada",
    "expirada",
  ]),
  revisao: z.number().int(),
  rodada_atual: z.number().int(),
  created_at: z.iso.datetime({ offset: true }),
  expires_at: z.iso.datetime({ offset: true }).nullable(),
});
export const interviewSchema = interviewSummarySchema.extend({
  rodadas: z.array(roundSchema),
  complementos: z.array(complementSchema),
  conflitos: z.array(conflictSchema),
  resolucoes: z.array(resolutionSchema),
  consentimento_em: z.iso.datetime({ offset: true }),
  consentimento_versao: z.string(),
  confirmado_em: z.iso.datetime({ offset: true }).nullable(),
  tentativa_id: z.uuid().nullable(),
  geracao_id: z.uuid().nullable(),
  codigo_erro: z.string().nullable(),
  mensagem_erro: z.string().nullable(),
  acompanhamento: z.string(),
});
export const interviewPageSchema = z.object({
  itens: z.array(interviewSummarySchema),
  total: z.number().int().nonnegative(),
  pagina: z.number().int().positive(),
  tamanho: z.number().int().positive(),
});
export type ResumeSummary = z.infer<typeof resumeSummarySchema>;
export type History = z.infer<typeof resumePageSchema>;
export type ResumeDetail = z.infer<typeof resumeDetailSchema>;
export type InterviewData = z.infer<typeof interviewSchema>;
export type AttemptData = z.infer<typeof attemptSchema>;
