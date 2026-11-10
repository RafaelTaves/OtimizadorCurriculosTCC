"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { HttpError, browserRequest } from "@/lib/http/errors";
import { resumeDetailSchema } from "@/lib/contracts";

const maxFileBytes = 10 * 1024 * 1024;
const uploadSchema = z.object({
  arquivo: z
    .custom<File>(
      (value) => typeof File !== "undefined" && value instanceof File,
      "Escolha um arquivo PDF ou DOCX.",
    )
    .refine((file) => file.size > 0, "O arquivo está vazio.")
    .refine(
      (file) => file.size <= maxFileBytes,
      "O arquivo deve ter até 10 MiB.",
    )
    .refine(
      (file) => /\.(pdf|docx)$/i.test(file.name),
      "Use um arquivo com extensão PDF ou DOCX.",
    ),
  descricao_vaga: z
    .string()
    .trim()
    .min(30, "Informe pelo menos 30 caracteres.")
    .max(20_000, "A descrição pode ter até 20.000 caracteres."),
});
type UploadFormValues = z.infer<typeof uploadSchema>;

function fileSize(bytes: number) {
  return `${(bytes / (1024 * 1024)).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} MiB`;
}

export function UploadForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const [acknowledgedUncertain, setAcknowledgedUncertain] = useState(false);
  const form = useForm<UploadFormValues>({
    resolver: zodResolver(uploadSchema),
    defaultValues: { descricao_vaga: "" },
    mode: "onSubmit",
  });
  const descriptionLength =
    useWatch({ control: form.control, name: "descricao_vaga" })?.trim()
      .length ?? 0;

  function selectFile(file: File | undefined) {
    setSelectedFile(file ?? null);
    form.setValue("arquivo", file as File, {
      shouldValidate: form.formState.isSubmitted,
      shouldDirty: true,
    });
    setUncertain(false);
    setAcknowledgedUncertain(false);
  }

  async function submit(values: UploadFormValues) {
    if (uncertain && !acknowledgedUncertain) return;
    const body = new FormData();
    body.append("arquivo", values.arquivo);
    body.append("descricao_vaga", values.descricao_vaga.trim());
    try {
      const result = await browserRequest(
        "/v1/curriculos",
        { method: "POST", body },
        resumeDetailSchema.parse,
      );
      await queryClient.invalidateQueries({ queryKey: ["curriculos"] });
      router.push(`/curriculos/${result.data.id}/revisao`);
    } catch (error) {
      if (
        error instanceof HttpError &&
        (error.status === 503 || error.code === "tempo_esgotado")
      ) {
        setUncertain(true);
        setAcknowledgedUncertain(false);
      }
      form.setError("root", {
        message:
          error instanceof HttpError
            ? error.message
            : "Não foi possível enviar o currículo.",
      });
    }
  }

  return (
    <form
      className="panel form-stack upload-form"
      onSubmit={form.handleSubmit(submit)}
      noValidate
    >
      <div>
        <h2>Currículo e vaga</h2>
        <p className="section-intro">
          Primeiro extraímos o texto para você conferir. Nada é enviado à IA
          nesta etapa.
        </p>
      </div>

      <div className="form-field">
        <label htmlFor="arquivo">Arquivo do currículo</label>
        <p id="arquivo-ajuda" className="field-hint">
          PDF com texto selecionável (até 10 páginas) ou DOCX. Até 10 MiB.
        </p>
        <input
          ref={inputRef}
          id="arquivo"
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          aria-describedby={`arquivo-ajuda${form.formState.errors.arquivo ? " arquivo-erro" : ""}`}
          className="file-input"
          onChange={(event) => selectFile(event.currentTarget.files?.[0])}
        />
        <div
          className="drop-zone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            selectFile(event.dataTransfer.files[0]);
          }}
        >
          {selectedFile ? (
            <div className="selected-file">
              <div>
                <strong>{selectedFile.name}</strong>
                <span>{fileSize(selectedFile.size)}</span>
              </div>
              <div className="inline-actions">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => inputRef.current?.click()}
                >
                  Substituir
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    selectFile(undefined);
                    if (inputRef.current) inputRef.current.value = "";
                  }}
                >
                  Remover
                </Button>
              </div>
            </div>
          ) : (
            <div>
              <p>Escolha um arquivo ou solte-o aqui</p>
              <Button
                type="button"
                variant="outline"
                onClick={() => inputRef.current?.click()}
              >
                Selecionar arquivo
              </Button>
            </div>
          )}
        </div>
        {form.formState.errors.arquivo && (
          <p id="arquivo-erro" className="field-error" role="alert">
            {form.formState.errors.arquivo.message}
          </p>
        )}
      </div>

      <div className="form-field">
        <label htmlFor="descricao-vaga">Descrição da vaga</label>
        <p id="vaga-ajuda" className="field-hint">
          Inclua responsabilidades e requisitos relevantes. De 30 a 20.000
          caracteres.
        </p>
        <textarea
          id="descricao-vaga"
          rows={8}
          maxLength={20_000}
          aria-describedby={`vaga-ajuda vaga-contador${form.formState.errors.descricao_vaga ? " vaga-erro" : ""}`}
          {...form.register("descricao_vaga")}
        />
        <div className="form-hint-row">
          {form.formState.errors.descricao_vaga ? (
            <span id="vaga-erro" className="field-error" role="alert">
              {form.formState.errors.descricao_vaga.message}
            </span>
          ) : (
            <span />
          )}
          <span id="vaga-contador" className="character-count">
            {descriptionLength.toLocaleString("pt-BR")} / 20.000
          </span>
        </div>
      </div>

      {uncertain && (
        <div className="notice warning-notice" role="alert">
          <strong>Não foi possível confirmar o resultado do envio.</strong>
          <p>
            O currículo pode já ter sido salvo. Consulte seu histórico antes de
            reenviar; se decidir tentar, outro original poderá ser criado.
          </p>
          <label className="check-row">
            <input
              type="checkbox"
              checked={acknowledgedUncertain}
              onChange={(event) =>
                setAcknowledgedUncertain(event.target.checked)
              }
            />{" "}
            Entendo que um novo envio pode criar outra cópia.
          </label>
        </div>
      )}
      {form.formState.errors.root?.message && (
        <p className="field-error" role="alert">
          {form.formState.errors.root.message}
        </p>
      )}
      <div className="form-actions">
        <Button
          type="submit"
          disabled={
            form.formState.isSubmitting || (uncertain && !acknowledgedUncertain)
          }
        >
          {form.formState.isSubmitting
            ? "Enviando e extraindo texto…"
            : uncertain
              ? "Tentar o envio novamente"
              : "Enviar e revisar"}
        </Button>
        {uncertain && (
          <a className="text-link" href="/curriculos">
            Ver histórico
          </a>
        )}
      </div>
      <p className="field-hint">
        A revisão do texto extraído é obrigatória. O envio à IA só acontece após
        consentimento separado.
      </p>
    </form>
  );
}
