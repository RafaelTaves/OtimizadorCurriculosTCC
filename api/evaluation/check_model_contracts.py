"""Live contract checks using ONLY the repository's explicitly fictional fixtures."""

import argparse
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.config import Settings
from app.infrastructure.openai_interviewer import OpenAIInterviewAnalyzer
from app.infrastructure.openai_optimizer import OpenAIOptimizer
from app.presentation.interviews import Question, RecordedAnswer
from app.service.errors import ProcessingError
from app.service.interview_validation import validate_analysis
from app.service.ports import AnalysisResult, ModelResult
from app.service.proposals import ProposalValidator


def check[Result: (ModelResult, AnalysisResult)](
    name: str,
    call: Callable[[str | None], Result],
    validate: Callable[[Result], None],
    rows: list[dict[str, object]],
    output: Path,
) -> Result | None:
    feedback = None
    for execution in range(1, 4):
        row: dict[str, object] = {"phase": name, "execution": execution}
        result = None
        try:
            result = call(feedback)
            row.update(
                {
                    "model": result.model,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                }
            )
            if isinstance(result, ModelResult):
                (output / f"{name}-{execution}.tex").write_text(
                    result.proposal.latex_gerado, encoding="utf-8"
                )
                data = result.proposal.model_dump(mode="json")
            else:
                data = result.analysis.model_dump(mode="json")
            (output / f"{name}-{execution}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            validate(result)
            row["status"] = "valid"
            rows.append(row)
            print(json.dumps(row, ensure_ascii=True), flush=True)
            return result
        except ProcessingError as error:
            feedback = error.message
            row.update({"status": "rejected", "code": error.code, "reason": error.message})
            rows.append(row)
            print(json.dumps(row, ensure_ascii=True), flush=True)
            if not error.transient:
                break
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Autoriza chamadas pagas com fixtures")
    parser.add_argument("--case", action="append", dest="cases")
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/model-contracts"))
    args = parser.parse_args()
    if not args.live:
        parser.error("--live é obrigatório; nenhuma chamada foi feita")
    cases = json.loads(Path(__file__).with_name("cases.json").read_text(encoding="utf-8"))
    if args.cases:
        if set(args.cases) - {case["id"] for case in cases}:
            parser.error("Caso inexistente nas fixtures")
        cases = [case for case in cases if case["id"] in args.cases]
    settings = Settings()
    optimizer, analyzer = OpenAIOptimizer(settings), OpenAIInterviewAnalyzer(settings)
    report: dict[str, object] = {
        "date": datetime.now(UTC).isoformat(),
        "model": settings.openai_model,
        "synthetic_data_only": True,
    }
    reports = []
    success = True
    for case in cases:
        output = args.output / case["id"]
        output.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, object]] = []
        optimized = check(
            "optimization",
            lambda feedback, case=case: optimizer.optimize(
                case["curriculo"],
                case["vaga"],
                feedback=feedback,
            ),
            lambda result, case=case: ProposalValidator().validate(
                result.proposal,
                case["curriculo"],
                case["vaga"],
            ),
            rows,
            output,
        )
        context: dict[str, object] = {
            "curriculo_confirmado": case["curriculo"],
            "descricao_vaga": case["vaga"],
            "rodada": 1,
            "limite_perguntas": settings.interview_questions_per_round,
            "historico": [],
        }
        first = check(
            "interview-round-1",
            lambda feedback, context=context: analyzer.analyze(
                {**context, "correcao_anterior": feedback}
            ),
            lambda result, context=context: validate_analysis(
                result.analysis,
                context,
                settings.interview_questions_per_round,
            ),
            rows,
            output,
        )
        second_ok = True
        if first and first.analysis.perguntas:
            questions = [
                Question(id=uuid4(), **question.model_dump())
                for question in first.analysis.perguntas
            ]
            answers = [
                RecordedAnswer(
                    id=uuid4(),
                    pergunta_id=question.id,
                    texto=case["curriculo"] if index == 0 else None,
                    pulada=index != 0,
                )
                for index, question in enumerate(questions)
            ]
            context = {
                **context,
                "rodada": 2,
                "historico": [
                    {
                        "perguntas": [q.model_dump(mode="json") for q in questions],
                        "respostas": [a.model_dump(mode="json") for a in answers],
                        "complemento_livre": None,
                        "complemento_livre_id": None,
                    }
                ],
            }
            second = check(
                "interview-round-2",
                lambda feedback, context=context: analyzer.analyze(
                    {**context, "correcao_anterior": feedback}
                ),
                lambda result, context=context: validate_analysis(
                    result.analysis,
                    context,
                    settings.interview_questions_per_round,
                ),
                rows,
                output,
            )
            second_ok = second is not None
        case_ok = optimized is not None and first is not None and second_ok
        success = success and case_ok
        reports.append({"case": case["id"], "passed": case_ok, "executions": rows})
    report.update({"passed": success, "cases": reports})
    (args.output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
