import { z } from "zod";
export const loginSchema = z.object({
  username: z
    .string()
    .trim()
    .min(1, "Informe seu e-mail ou nome de usuário.")
    .max(254),
  password: z
    .string()
    .min(1, "Informe sua senha.")
    .max(128, "A senha deve ter até 128 caracteres."),
});
export const registrationSchema = z.object({
  username: z
    .string()
    .trim()
    .min(3, "Use ao menos 3 caracteres.")
    .max(50)
    .regex(
      /^[a-zA-Z0-9_.-]+$/,
      "Use letras sem acento, números, ponto, hífen ou sublinhado.",
    ),
  email: z.email("Informe um e-mail válido."),
  password: z.string().min(10, "Use ao menos 10 caracteres.").max(128),
});
export const signupSchema = registrationSchema
  .extend({ confirmation: z.string() })
  .refine((data) => data.password === data.confirmation, {
    message: "As senhas não coincidem.",
    path: ["confirmation"],
  });
export type LoginFields = z.infer<typeof loginSchema>;
export type SignupFields = z.infer<typeof signupSchema>;
