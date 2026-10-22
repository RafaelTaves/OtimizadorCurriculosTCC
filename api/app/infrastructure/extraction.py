import io
import multiprocessing
import re
import zipfile
from multiprocessing.connection import Connection
from pathlib import PurePath

from docx import Document
from docx.table import Table
from pypdf import PdfReader

from app.config import Settings
from app.service.errors import AppError


def normalize_text(text: str) -> str:
    return "\n".join(
        re.sub(r"[^\S\n]+", " ", line).strip()
        for line in text.replace("\x00", "").replace("\r", "\n").splitlines()
        if line.strip()
    )


def extract_document(data: bytes, extension: str, settings: Settings) -> str:
    if extension == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise AppError("assinatura_invalida", "O arquivo não é um PDF válido.", 415)
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise AppError("pdf_protegido", "Envie um PDF sem proteção por senha.")
        if len(reader.pages) > settings.max_pages:
            raise AppError("paginas_excedidas", "O PDF excede o limite de páginas.")
        parts: list[str] = []
        total = 0
        for page in reader.pages:
            # Bound expanded streams before passing them to the layout/text parser.
            contents = page.get_contents()
            if contents and len(contents.get_data()) > settings.max_docx_unpacked_bytes:
                raise AppError("conteudo_excessivo", "Conteúdo descompactado excede o limite.")
            part = page.extract_text() or ""
            total += len(part)
            if total > settings.max_extracted_chars:
                raise AppError("texto_excessivo", "Texto extraído excede o limite.", 413)
            parts.append(part)
        text = "\n".join(parts)
    else:
        if not data.startswith(b"PK\x03\x04"):
            raise AppError("assinatura_invalida", "O arquivo não é um DOCX válido.", 415)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if (
                len(infos) > 2000
                or sum(i.file_size for i in infos) > settings.max_docx_unpacked_bytes
            ):
                raise AppError("docx_excessivo", "Conteúdo descompactado excede o limite.", 413)
            if {"[Content_Types].xml", "word/document.xml"} - set(archive.namelist()):
                raise AppError("docx_invalido", "Pacote DOCX inválido.", 415)
            if any(i.flag_bits & 1 for i in infos):
                raise AppError("docx_protegido", "Envie um DOCX sem criptografia.")
        document = Document(io.BytesIO(data))
        blocks: list[str] = []
        for block in document.iter_inner_content():
            if isinstance(block, Table):
                blocks.extend(" | ".join(cell.text for cell in row.cells) for row in block.rows)
            else:
                blocks.append(block.text)
        text = "\n".join(blocks)
    text = normalize_text(text)
    if len(text) > settings.max_extracted_chars:
        raise AppError("texto_excessivo", "Texto extraído excede o limite.", 413)
    if len(text) < 50 or sum(c.isalpha() for c in text) < 30:
        raise AppError(
            "texto_insuficiente",
            "Texto insuficiente. Envie PDF com texto selecionável ou DOCX; "
            "OCR não está disponível.",
            422,
        )
    return text


def _extract_child(conn: Connection, data: bytes, extension: str, settings: Settings) -> None:
    try:
        # Linux API container: cap address space and CPU in addition to parent wall timeout.
        try:
            import resource

            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
            resource.setrlimit(resource.RLIMIT_CPU, (settings.extraction_timeout_seconds,) * 2)
        except ImportError:
            pass
        conn.send((True, extract_document(data, extension, settings), 200, ""))
    except AppError as exc:
        conn.send((False, exc.message, exc.status, exc.code))
    except Exception:
        conn.send((False, "Arquivo corrompido ou formato inválido.", 400, "arquivo_corrompido"))
    finally:
        conn.close()


class ProcessExtractor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def extract(self, data: bytes, filename: str) -> str:
        if not data:
            raise AppError("arquivo_vazio", "Envie um arquivo não vazio.")
        if len(data) > self.settings.max_upload_bytes:
            raise AppError("arquivo_grande", "O arquivo excede 10 MB.", 413)
        extension = PurePath(filename).suffix.casefold()
        if extension not in (".pdf", ".docx"):
            raise AppError("formato_nao_aceito", "Envie um arquivo PDF ou DOCX.", 415)
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        process = context.Process(
            target=_extract_child, args=(child, data, extension, self.settings)
        )
        process.start()
        child.close()
        try:
            if not parent.poll(self.settings.extraction_timeout_seconds):
                raise AppError(
                    "extracao_timeout", "Não foi possível ler o arquivo no tempo limite."
                )
            try:
                success, text, status, code = parent.recv()
            except EOFError as exc:
                raise AppError("extracao_falhou", "Não foi possível ler o arquivo.") from exc
            if not success:
                raise AppError(code, text, status)
            return str(text)
        finally:
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join()
            parent.close()
