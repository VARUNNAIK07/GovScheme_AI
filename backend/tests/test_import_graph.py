"""Static import rules (reads source with ast, imports nothing):
* contracts imports nothing from the repo
* knowledge never imports ingestion / agents / controller / api
* every internal import is absolute from the repo root (no 'from app.' style)
* no import cycles between repo modules
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("contracts", "ingestion", "backend")
FORBIDDEN = {
    "contracts": ("ingestion", "backend"),
    "backend.app.knowledge": ("ingestion", "backend.app.agents", "backend.app.controller", "backend.app.api"),
    "backend.app.db": ("ingestion", "backend.app.knowledge", "backend.app.agents", "backend.app.controller"),
}


def _module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = rel.parts[:-1] if rel.name == "__init__" else rel.parts
    return ".".join(parts)


def _graph() -> dict[str, set[str]]:
    graph = {}
    for pkg in PACKAGES:
        for path in (ROOT / pkg).rglob("*.py"):
            if "migrations" in path.parts or "tests" in path.parts:
                continue
            mod = _module_name(path)
            deps = set()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    deps |= {a.name for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    deps.add(node.module)
                    deps |= {f"{node.module}.{a.name}" for a in node.names}
            graph[mod] = {d for d in deps if d.split(".")[0] in PACKAGES or d.startswith("app.")}
    return graph


def test_every_written_module_imports():
    """Catches broken imports in modules no other test touches (skips empty placeholders)."""
    import importlib
    for pkg in ("contracts", "ingestion", "backend/app/core", "backend/app/db", "backend/app/knowledge"):
        for path in (ROOT / pkg).glob("*.py"):
            if path.stat().st_size:
                importlib.import_module(_module_name(path))


def test_no_relative_app_imports():
    bad = {m: sorted(d for d in deps if d.startswith("app.")) for m, deps in _graph().items()}
    assert not {m: d for m, d in bad.items() if d}, "use 'backend.app...' imports from the repo root"


def test_forbidden_directions():
    violations = []
    for mod, deps in _graph().items():
        for owner, banned in FORBIDDEN.items():
            if mod == owner or mod.startswith(owner + "."):
                violations += [f"{mod} -> {d}" for d in deps if any(d == b or d.startswith(b + ".") for b in banned)]
    assert not violations, violations


def test_no_cycles():
    graph = _graph()
    modules = set(graph)
    edges = {m: {d if d in modules else d.rsplit(".", 1)[0] for d in deps} & modules - {m} for m, deps in graph.items()}
    state, stack, cycles = {}, [], []

    def visit(m):
        state[m] = "active"
        stack.append(m)
        for d in edges[m]:
            if state.get(d) == "active":
                cycles.append(stack[stack.index(d):] + [d])
            elif d not in state:
                visit(d)
        stack.pop()
        state[m] = "done"

    for m in sorted(modules):
        if m not in state:
            visit(m)
    assert not cycles, cycles
