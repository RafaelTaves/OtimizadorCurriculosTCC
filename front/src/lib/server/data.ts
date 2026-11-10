import "server-only";
import { redirect } from "next/navigation";
import { z } from "zod";
import { HttpError, type LoadResult } from "@/lib/http/errors";
import { usageSchema, resumePageSchema } from "@/lib/contracts";
import { requireSession } from "./session";
import { backend } from "./backend";

async function load<T>(
  path: string,
  schema: z.ZodType<T>,
): Promise<LoadResult<T>> {
  const { token } = await requireSession();
  try {
    return { data: schema.parse(await backend(path, token)) };
  } catch (error) {
    if (error instanceof HttpError && error.status === 401) redirect("/login");
    return { error: "Não foi possível carregar estes dados. Tente novamente." };
  }
}
export const loadUsage = () => load("/v1/uso", usageSchema);
export const loadHistory = (size = 4, page = 1) =>
  load(`/v1/curriculos?pagina=${page}&tamanho=${size}`, resumePageSchema);
