"use client";

export function intentKey(scope: string) {
  const name = `intencao:${scope}`;
  const stored = sessionStorage.getItem(name);
  if (stored) return stored;
  const value = crypto.randomUUID();
  sessionStorage.setItem(name, value);
  return value;
}

export function clearIntent(scope: string) {
  sessionStorage.removeItem(`intencao:${scope}`);
}
