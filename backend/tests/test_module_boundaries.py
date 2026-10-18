"""Enforces the modular-monolith rule: a module under app/modules/<name>/ may
import another module's `public` surface only, never its models/service/api
internals directly. Pure stdlib (ast + pathlib), no new dependency, runs as
an ordinary pytest test."""

import ast
from pathlib import Path

MODULES_DIR = Path(__file__).resolve().parent.parent / "app" / "modules"


def _cross_module_imports(file_path: Path) -> list[str]:
    """Returns 'app.modules.X[.Y]' strings this file imports, one per import."""
    tree = ast.parse(file_path.read_text())
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("app.modules."):
                for alias in node.names:
                    imports.append(f"{node.module}.{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app.modules."):
                    imports.append(alias.name)
    return imports


def test_modules_only_import_each_others_public_surface() -> None:
    if not MODULES_DIR.exists():
        return
    module_names = sorted(
        p.name for p in MODULES_DIR.iterdir() if p.is_dir() and not p.name.startswith("__")
    )

    violations = []
    for module_name in module_names:
        for py_file in (MODULES_DIR / module_name).rglob("*.py"):
            if py_file.name == "public.py":
                continue  # this IS the public surface, not a consumer of it
            for imported in _cross_module_imports(py_file):
                parts = imported.split(".")
                # imported looks like app.modules.<other>.<rest...>
                other = parts[2]
                if other == module_name:
                    continue  # importing from yourself is fine
                if other not in module_names:
                    continue  # not one of our tracked modules
                rest = parts[3:]
                if rest[:1] == ["public"]:
                    continue  # the one allowed path
                violations.append(f"{py_file.relative_to(MODULES_DIR.parent.parent)}: {imported}")

    assert not violations, "module boundary violations (must go through .public):\n" + "\n".join(
        violations
    )
