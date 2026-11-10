export const SESSION_COOKIE = "curriculo_session";
export function safeReturnPath(value: unknown): string {
  if (typeof value !== "string") return "/painel";
  const uuid =
    "[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}";
  const known = [
    /^\/(painel|conta|curriculos|curriculos\/novo)$/,
    new RegExp(`^/curriculos/${uuid}/(revisao|complementacoes|editor)$`, "i"),
    new RegExp(`^/complementacoes/${uuid}$`, "i"),
    new RegExp(`^/otimizacoes/${uuid}$`, "i"),
  ];
  return known.some((pattern) => pattern.test(value)) ? value : "/painel";
}
export function resumeDestination(resume: {
  id: string;
  tipo: string;
  tentativa_origem_id?: string | null;
  revisao_humana_confirmada?: boolean;
}) {
  if (resume.tipo === "original") return `/curriculos/${resume.id}/revisao`;
  if (resume.tentativa_origem_id && !resume.revisao_humana_confirmada) {
    return `/otimizacoes/${resume.tentativa_origem_id}`;
  }
  return `/curriculos/${resume.id}/editor`;
}
