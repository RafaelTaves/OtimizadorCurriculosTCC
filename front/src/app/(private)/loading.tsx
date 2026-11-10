export default function Loading() {
  return (
    <div role="status" aria-live="polite">
      <h1>Carregando seu espaço…</h1>
      <div className="skeleton-layout">
        <div />
        <div />
      </div>
    </div>
  );
}
