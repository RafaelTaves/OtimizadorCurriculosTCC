"use client";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  loginSchema,
  signupSchema,
  type LoginFields,
  type SignupFields,
} from "@/lib/validation/auth";
import { safeReturnPath } from "@/lib/navigation";

async function submitAuth(path: string, data: unknown) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }).catch(() => {
    throw new Error(
      "Não foi possível conectar. Verifique sua conexão e tente novamente.",
    );
  });
  const body = await response.json().catch(() => {
    throw new Error(
      "O serviço está indisponível. Tente novamente em instantes.",
    );
  });
  if (!response.ok)
    throw new Error(
      body.erro?.mensagem ?? "Não foi possível concluir. Tente novamente.",
    );
}
function PasswordField({
  show,
  toggle,
  children,
}: {
  show: boolean;
  toggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="password-field">
      {children}
      <button
        type="button"
        onClick={toggle}
        aria-label={show ? "Ocultar senha" : "Mostrar senha"}
        aria-pressed={show}
      >
        {show ? (
          <EyeOff size={18} aria-hidden="true" />
        ) : (
          <Eye size={18} aria-hidden="true" />
        )}
      </button>
    </div>
  );
}
export function LoginForm({
  returnTo,
  registered,
}: {
  returnTo: string;
  registered: boolean;
}) {
  const [show, setShow] = useState(false),
    [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFields>({ resolver: zodResolver(loginSchema) });
  async function submit(data: LoginFields) {
    setError("");
    try {
      await submitAuth("/api/auth/login", data);
      window.location.replace(safeReturnPath(returnTo));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Não foi possível entrar. Verifique sua conexão.",
      );
    }
  }
  return (
    <form onSubmit={handleSubmit(submit)} noValidate className="auth-form">
      {registered && (
        <p className="notice" role="status">
          Conta criada. Entre com seus dados para continuar.
        </p>
      )}
      <div>
        <label htmlFor="username">E-mail ou nome de usuário</label>
        <Input
          id="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          aria-invalid={!!errors.username}
          aria-describedby={errors.username ? "username-error" : undefined}
          {...register("username")}
        />
        {errors.username && (
          <p className="field-error" id="username-error">
            {errors.username.message}
          </p>
        )}
      </div>
      <div>
        <label htmlFor="password">Senha</label>
        <PasswordField show={show} toggle={() => setShow(!show)}>
          <Input
            id="password"
            type={show ? "text" : "password"}
            autoComplete="current-password"
            aria-invalid={!!errors.password}
            aria-describedby={errors.password ? "password-error" : undefined}
            {...register("password")}
          />
        </PasswordField>
        {errors.password && (
          <p className="field-error" id="password-error">
            {errors.password.message}
          </p>
        )}
      </div>
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? "Entrando…" : "Entrar"}
      </Button>
      <p className="auth-alternative">
        Ainda não tem uma conta? <Link href="/cadastro">Criar conta</Link>
      </p>
    </form>
  );
}
export function SignupForm() {
  const [show, setShow] = useState(false),
    [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SignupFields>({ resolver: zodResolver(signupSchema) });
  async function submit(data: SignupFields) {
    setError("");
    try {
      await submitAuth("/api/auth/cadastro", {
        username: data.username,
        email: data.email,
        password: data.password,
      });
      window.location.replace("/login?cadastro=concluido");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Não foi possível criar sua conta. Verifique sua conexão.",
      );
    }
  }
  return (
    <form onSubmit={handleSubmit(submit)} noValidate className="auth-form">
      <div>
        <label htmlFor="username">Nome de usuário</label>
        <Input
          id="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          aria-invalid={!!errors.username}
          aria-describedby="username-help username-error"
          {...register("username")}
        />
        <p id="username-help" className="field-hint">
          Letras sem acento, números, ponto, hífen ou sublinhado.
        </p>
        <p className="field-error" id="username-error">
          {errors.username?.message}
        </p>
      </div>
      <div>
        <label htmlFor="email">E-mail</label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          aria-invalid={!!errors.email}
          aria-describedby="email-error"
          {...register("email")}
        />
        <p className="field-error" id="email-error">
          {errors.email?.message}
        </p>
      </div>
      <div>
        <label htmlFor="password">Senha</label>
        <PasswordField show={show} toggle={() => setShow(!show)}>
          <Input
            id="password"
            type={show ? "text" : "password"}
            autoComplete="new-password"
            aria-invalid={!!errors.password}
            aria-describedby="password-help password-error"
            {...register("password")}
          />
        </PasswordField>
        <p id="password-help" className="field-hint">
          Entre 10 e 128 caracteres.
        </p>
        <p className="field-error" id="password-error">
          {errors.password?.message}
        </p>
      </div>
      <div>
        <label htmlFor="confirmation">Confirmar senha</label>
        <Input
          id="confirmation"
          type={show ? "text" : "password"}
          autoComplete="new-password"
          aria-invalid={!!errors.confirmation}
          aria-describedby="confirmation-error"
          {...register("confirmation")}
        />
        <p className="field-error" id="confirmation-error">
          {errors.confirmation?.message}
        </p>
      </div>
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? "Criando conta…" : "Criar conta"}
      </Button>
      <p className="auth-alternative">
        Já tem uma conta? <Link href="/login">Entrar</Link>
      </p>
    </form>
  );
}
