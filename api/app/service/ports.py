from dataclasses import dataclass
from typing import Protocol

from app.presentation.schemas import Proposal


class Storage(Protocol):
    def put(self, data: bytes, *, temporary: bool = False) -> str: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def purge(self, ttl_seconds: int, protected: set[str] | None = None) -> int: ...


class Extractor(Protocol):
    def extract(self, data: bytes, filename: str) -> str: ...


@dataclass(frozen=True)
class ModelResult:
    proposal: Proposal
    model: str
    input_tokens: int
    output_tokens: int


class Optimizer(Protocol):
    def optimize(self, text: str, job: str) -> ModelResult: ...


class Compiler(Protocol):
    def compile(self, latex: str) -> bytes: ...
