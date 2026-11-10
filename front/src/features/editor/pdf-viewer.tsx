"use client";

import { Document, Page, pdfjs } from "react-pdf";
import { useEffect, useRef, useState } from "react";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export function PdfViewer({ url }: { url: string }) {
  const [pages, setPages] = useState(0);
  const [error, setError] = useState(false);
  const [width, setWidth] = useState(600);
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const observer = new ResizeObserver(() =>
      setWidth(Math.max(280, Math.min(760, element.clientWidth - 24))),
    );
    observer.observe(element);
    setWidth(Math.max(280, Math.min(760, element.clientWidth - 24)));
    return () => observer.disconnect();
  }, []);
  return (
    <div
      ref={container}
      className="pdf-viewer"
      aria-label="Prévia do currículo em PDF"
    >
      {error ? (
        <iframe title="Prévia do currículo" src={url} className="pdf-frame" />
      ) : (
        <Document
          file={url}
          onLoadSuccess={(document) => setPages(document.numPages)}
          onLoadError={() => setError(true)}
          loading={<p role="status">Carregando PDF…</p>}
        >
          {pages > 0 &&
            Array.from({ length: pages }, (_, index) => (
              <Page
                key={index}
                pageNumber={index + 1}
                width={width}
                renderAnnotationLayer={false}
                renderTextLayer={false}
              />
            ))}
        </Document>
      )}
    </div>
  );
}
