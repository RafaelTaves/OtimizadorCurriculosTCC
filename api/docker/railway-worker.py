"""Verify the actual sandbox before consuming any PDF jobs."""

from app.config import get_settings
from app.infrastructure.compiler import SandboxCompiler
from app.service.proposals import TEMPLATE
from app.worker import main

if __name__ == "__main__":
    SandboxCompiler(get_settings()).compile(TEMPLATE)
    print("compiler_sandbox_ready", flush=True)
    main()
