"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { HttpError } from "@/lib/http/errors";
export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: true,
            refetchIntervalInBackground: false,
            networkMode: "online",
            retry: (count, error) => {
              if (count >= 1) return false;
              if (
                error instanceof HttpError &&
                [401, 403, 404, 410, 412, 422, 428, 429].includes(error.status)
              )
                return false;
              return true;
            },
          },
          mutations: { retry: false },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
