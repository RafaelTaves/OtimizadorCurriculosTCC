import { SESSION_COOKIE } from "@/lib/navigation";
import {
  checkOrigin,
  privateJson,
  errorResponse,
} from "@/lib/server/route-utils";
export async function POST(request: Request) {
  try {
    checkOrigin(request);
    const response = privateJson({ ok: true });
    response.cookies.set(SESSION_COOKIE, "", {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      maxAge: 0,
    });
    return response;
  } catch (error) {
    return errorResponse(error);
  }
}
