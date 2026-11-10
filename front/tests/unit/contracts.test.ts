import { describe, expect, it } from "vitest";
import { safeReturnPath, resumeDestination } from "@/lib/navigation";
import { signupSchema } from "@/lib/validation/auth";
import { resumePageSchema, usageSchema } from "@/lib/contracts";
describe("fronteiras do navegador", () => {
  it.each([
    "https://evil.example",
    "//evil.example",
    "/\\evil.example",
    "/painel?retorno=//evil.example",
    "/api/auth/logout",
    undefined,
  ])("recusa retorno inseguro %s", (path) => {
    expect(safeReturnPath(path)).toBe("/painel");
  });
  it("preserva destinos conhecidos", () => {
    expect(safeReturnPath("/curriculos/novo")).toBe("/curriculos/novo");
  });
  it("direciona original para revisão e versão para editor", () => {
    expect(resumeDestination({ id: "a", tipo: "original" })).toBe(
      "/curriculos/a/revisao",
    );
    expect(resumeDestination({ id: "a", tipo: "otimizado" })).toBe(
      "/curriculos/a/editor",
    );
  });
  it("não confirma senhas diferentes nem remove espaços da senha", () => {
    const data = {
      username: "teste",
      email: "teste@example.org",
      password: " senha teste ",
      confirmation: " senha teste ",
    };
    expect(signupSchema.parse(data).password).toBe(data.password);
    expect(
      signupSchema.safeParse({ ...data, confirmation: "outra" }).success,
    ).toBe(false);
  });
  it("recusa consumo ausente em vez de inferir zero", () => {
    expect(usageSchema.safeParse({ limite: 5, restante: 5 }).success).toBe(
      false,
    );
  });
  it("remove conteúdo privado desnecessário da listagem", () => {
    const parsed = resumePageSchema.parse({
      itens: [
        {
          id: "00000000-0000-4000-8000-000000000001",
          nome_arquivo: "sintetico.pdf",
          tipo: "original",
          texto_confirmado: false,
          created_at: "2026-10-22T12:00:00Z",
          updated_at: "2026-10-22T12:00:00Z",
          texto_extraido: "Não enviar ao componente",
          descricao_vaga: "Vaga",
        },
      ],
      total: 1,
      pagina: 1,
      tamanho: 4,
    });
    expect(parsed.itens[0]).not.toHaveProperty("texto_extraido");
  });
});
