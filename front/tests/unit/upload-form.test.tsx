import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ExtractedTextReview } from "@/features/curriculos/extracted-text-review";
import { UploadForm } from "@/features/curriculos/upload-form";

const { routerPush } = vi.hoisted(() => ({ routerPush: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: routerPush }) }));

const resumeId = "00000000-0000-4000-8000-000000000042";
const resumeResponse = {
  id: resumeId,
  tipo: "original",
  curriculo_origem_id: null,
  nome_arquivo: "curriculo.pdf",
  descricao_vaga: "Descrição de uma vaga para desenvolvimento de software.",
  texto_extraido:
    "Conteúdo extraído de demonstração com mais de cinquenta caracteres.",
  texto_confirmado: false,
  latex_gerado: null,
  latex_revisao: 0,
  pdf_revisao: null,
  template_versao: null,
  conteudo_estruturado: null,
  created_at: "2026-10-23T12:00:00Z",
  updated_at: "2026-10-23T12:00:00Z",
  pdf_disponivel: false,
  avisos: [],
};

function renderUpload() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <UploadForm />
    </QueryClientProvider>,
  );
}

function renderTextReview() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ExtractedTextReview resumeId={resumeId} userId="synthetic-user" />
    </QueryClientProvider>,
  );
}

function enterValidFields(
  file = new File(["synthetic"], "curriculo.pdf", { type: "application/pdf" }),
) {
  fireEvent.change(screen.getByLabelText("Arquivo do currículo"), {
    target: { files: [file] },
  });
  fireEvent.change(screen.getByLabelText("Descrição da vaga"), {
    target: {
      value:
        "Vaga de desenvolvimento de software com foco em APIs, testes e trabalho em equipe.",
    },
  });
}

function submitForm() {
  fireEvent.submit(
    screen
      .getByRole("button", {
        name: /Enviar e revisar|Tentar o envio novamente/,
      })
      .closest("form")!,
  );
}

beforeEach(() => routerPush.mockReset());
afterEach(() => vi.unstubAllGlobals());

describe("envio de currículo", () => {
  it("valida a extensão e mantém os campos antes de enviar", async () => {
    renderUpload();
    enterValidFields(
      new File(["synthetic"], "curriculo.txt", { type: "text/plain" }),
    );

    submitForm();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Use um arquivo com extensão PDF ou DOCX.",
    );
    expect(screen.getByLabelText("Descrição da vaga")).toHaveValue(
      "Vaga de desenvolvimento de software com foco em APIs, testes e trabalho em equipe.",
    );
    expect(routerPush).not.toHaveBeenCalled();
  });

  it("envia multipart e segue para a revisão do texto extraído", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(resumeResponse), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderUpload();
    enterValidFields();

    submitForm();

    await waitFor(() =>
      expect(routerPush).toHaveBeenCalledWith(
        `/curriculos/${resumeId}/revisao`,
      ),
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/api/backend/v1/curriculos");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("arquivo")).toBeInstanceOf(File);
    expect((init.body as FormData).get("descricao_vaga")).toContain(
      "Vaga de desenvolvimento",
    );
  });

  it("pede confirmação explícita antes de tentar novamente após resultado incerto", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValue(new TypeError("connection lost"));
    vi.stubGlobal("fetch", fetchMock);
    renderUpload();
    enterValidFields();

    submitForm();

    expect(
      await screen.findByText(/outro original poderá ser criado/),
    ).toBeInTheDocument();
    const retry = screen.getByRole("button", {
      name: "Tentar o envio novamente",
    });
    expect(retry).toBeDisabled();
    fireEvent.click(
      screen.getByRole("checkbox", { name: /Entendo que um novo envio/ }),
    );
    expect(retry).toBeEnabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("preserva edições feitas enquanto a confirmação do texto está pendente", async () => {
    let resolvePatch!: (response: Response) => void;
    const patchResponse = new Promise<Response>((resolve) => {
      resolvePatch = resolve;
    });
    const confirmedResume = { ...resumeResponse, texto_confirmado: true };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PATCH") return patchResponse;
      return Promise.resolve(
        new Response(JSON.stringify(resumeResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    renderTextReview();

    const textarea = await screen.findByLabelText("Texto extraído");
    fireEvent.click(screen.getByRole("button", { name: "Confirmar texto" }));
    const editedText = `${resumeResponse.texto_extraido} Edição durante o envio.`;
    fireEvent.change(textarea, { target: { value: editedText } });
    resolvePatch(
      new Response(JSON.stringify(confirmedResume), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    expect(
      await screen.findByText(
        "A versão enviada foi confirmada. Há novas alterações no campo; confirme-as antes de continuar.",
      ),
    ).toBeInTheDocument();
    expect(textarea).toHaveValue(editedText);
    expect(
      screen.getByText("Há alterações não confirmadas"),
    ).toBeInTheDocument();
  });
});
