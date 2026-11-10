import Link from "next/link";
import Image from "next/image";
export function Brand({ href = "/painel" }: { href?: string }) {
  return (
    <Link
      href={href}
      className="brand"
      aria-label="Otimizador de currículos — início"
    >
      <Image
        src="/brand/logo-otimizador.png"
        width={2172}
        height={724}
        sizes="(min-width: 1024px) 204px, 168px"
        alt=""
        className="brand-logo"
        preload
      />
      {/* <span className="brand-subtitle">de currículos</span> */}
    </Link>
  );
}
