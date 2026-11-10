import "server-only";
import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE, safeReturnPath } from "@/lib/navigation";
import { userSchema } from "@/lib/contracts";
import { HttpError } from "@/lib/http/errors";
import { backend } from "./backend";

export const session = cache(async () => {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return null;
  try {
    return {
      user: userSchema.parse(await backend("/v1/auth/me", token)),
      token,
    };
  } catch (error) {
    if (error instanceof HttpError && error.status === 401) return null;
    throw error;
  }
});
export async function requireSession(path = "/painel") {
  const current = await session();
  if (!current)
    redirect(`/login?retorno=${encodeURIComponent(safeReturnPath(path))}`);
  return current;
}
