import { registrationSchema } from "@/lib/validation/auth";
import { userSchema } from "@/lib/contracts";
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
    const input = registrationSchema.safeParse(await smallJson(request));
    if (!input.success)
      throw new HttpError(422, "validacao", "Confira os dados do cadastro.");
    userSchema.parse(
      await backend("/v1/auth/register", undefined, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input.data),
      }),
    );
    return privateJson({ ok: true }, 201);
  } catch (error) {
    return errorResponse(error);
  }
}
