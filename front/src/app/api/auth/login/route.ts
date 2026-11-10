import { loginSchema } from "@/lib/validation/auth";
import { tokenSchema } from "@/lib/contracts";
import { SESSION_COOKIE } from "@/lib/navigation";
import { backend } from "@/lib/server/backend";
import {
  checkOrigin,
  smallJson,
  privateJson,
  errorResponse,
} from "@/lib/server/route-utils";
import { HttpError } from "@/lib/http/errors";

export async function POST(request: Request) {
  try {
    checkOrigin(request);
    const input = loginSchema.safeParse(await smallJson(request));
    if (!input.success)
      throw new HttpError(422, "validacao", "Confira seu usuário e sua senha.");
    const token = tokenSchema.parse(
      await backend("/v1/auth/token", undefined, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams(input.data),
      }),
    );
    const response = privateJson({ ok: true });
    response.cookies.set(SESSION_COOKIE, token.access_token, {
      httpOnly: true,
      sameSite: "lax",
      secure:
        new URL(process.env.APP_ORIGIN ?? "http://localhost:3000").protocol ===
        "https:",
      path: "/",
      maxAge: token.expires_in,
    });
    return response;
  } catch (error) {
    if (error instanceof HttpError && error.status === 401)
      return errorResponse(
        new HttpError(
          401,
          "credenciais_invalidas",
          "E-mail, usuário ou senha incorretos.",
        ),
      );
    return errorResponse(error);
  }
}
