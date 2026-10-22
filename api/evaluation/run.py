"""Evaluate synthetic data; real API requests require the explicit --live flag."""

import argparse
import csv
import json
import random
from pathlib import Path
from statistics import mean
from time import perf_counter

from app.config import get_settings
from app.infrastructure.compiler import DockerCompiler
from app.infrastructure.openai_optimizer import OpenAIOptimizer
from app.presentation.schemas import ResumeContent
from app.service.errors import ProcessingError
from app.service.proposals import ProposalValidator


def plain_text(content: ResumeContent) -> str:
    blocks = [fact.texto for fact in content.contato]
    if content.resumo:
        blocks.append(content.resumo.texto)
    for title, entries in (
        ("Formação", content.formacao),
        ("Experiências", content.experiencias),
        ("Projetos", content.projetos),
    ):
        if entries:
            blocks.append(title)
        for entry in entries:
            blocks.append(
                " — ".join(
                    fact.texto for fact in (entry.titulo, entry.instituicao, entry.periodo) if fact
                )
            )
            blocks.extend(fact.texto for fact in entry.itens)
    if content.competencias:
        blocks.append("Competências")
        blocks.extend(fact.texto for fact in content.competencias)
    return "\n".join(blocks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Autoriza chamadas pagas à OpenAI")
    parser.add_argument("--compile", action="store_true", help="Requer Docker e imagem Tectonic")
    parser.add_argument("--input-price", type=float, help="Preço por milhão de tokens de entrada")
    parser.add_argument("--output-price", type=float, help="Preço por milhão de tokens de saída")
    parser.add_argument("--output", type=Path, default=Path("evaluation/results"))
    args = parser.parse_args()
    cases = json.loads(Path(__file__).with_name("cases.json").read_text("utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    blind_key = []
    randomizer = random.Random(42)
    for case in cases:
        result = {"id": case["id"], "status": "nao_executado"}
        if args.live:
            started = perf_counter()
            try:
                settings = get_settings()
                generated = OpenAIOptimizer(settings).optimize(case["curriculo"], case["vaga"])
                ProposalValidator().validate(generated.proposal, case["curriculo"], case["vaga"])
                content = plain_text(generated.proposal.curriculo)
                keywords = generated.proposal.palavras_chave_usadas
                supported = sum(
                    term.casefold() in content.casefold() for term in case["termos_com_suporte"]
                )
                unsupported = sum(
                    term.casefold() in content.casefold() for term in case["termos_sem_suporte"]
                )
                cost = None
                if args.input_price is not None and args.output_price is not None:
                    cost = (
                        generated.input_tokens * args.input_price
                        + generated.output_tokens * args.output_price
                    ) / 1_000_000
                result.update(
                    {
                        "status": "gerado",
                        "modelo": generated.model,
                        "tokens_entrada": generated.input_tokens,
                        "tokens_saida": generated.output_tokens,
                        "custo_estimado": cost,
                        "cobertura_termos_suportados": supported / len(case["termos_com_suporte"]),
                        "termos_sem_suporte_detectados": unsupported,
                        "palavras_chave_com_evidencia": len(keywords),
                        "proposta": generated.proposal.model_dump(mode="json"),
                    }
                )
                (args.output / (case["id"] + ".tex")).write_text(
                    generated.proposal.latex_gerado, "utf-8"
                )
                if args.compile:
                    pdf = DockerCompiler(settings).compile(generated.proposal.latex_gerado)
                    (args.output / (case["id"] + ".pdf")).write_bytes(pdf)
                    result["compilou"] = True
                variants = [("original", case["curriculo"]), ("otimizado", content)]
                randomizer.shuffle(variants)
                for index, (kind, text) in enumerate(variants):
                    blind_id = case["id"] + "-" + chr(65 + index)
                    (args.output / (blind_id + ".txt")).write_text(text, "utf-8")
                    blind_key.append({"id_cego": blind_id, "tipo": kind})
            except ProcessingError as error:
                result.update({"status": "falhou", "codigo_erro": error.code})
            result["duracao_segundos"] = perf_counter() - started
        rows.append(result)
    (args.output / "results.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), "utf-8"
    )
    with (args.output / "rubrica.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "id_cego",
                "relevancia_1a5",
                "clareza_1a5",
                "legibilidade_1a5",
                "fatos_indevidos_contagem",
                "observacoes",
            ]
        )
        for variant in blind_key:
            writer.writerow([variant["id_cego"], "", "", "", "", ""])
    (args.output / "chave-cega.json").write_text(json.dumps(blind_key), "utf-8")
    measured = [row for row in rows if "duracao_segundos" in row]
    summary = {
        "casos": len(rows),
        "executados": len(measured),
        "gerados": sum(row["status"] == "gerado" for row in rows),
        "duracao_media_segundos": mean(row["duracao_segundos"] for row in measured)
        if measured
        else None,
        "observacao": "Sem execução real, não há resultados de qualidade ou custo a relatar."
        if not args.live
        else "Detecção automática não substitui avaliação humana; amostra sintética pequena.",
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), "utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
