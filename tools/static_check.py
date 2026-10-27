"""Lightweight static analyser used when SonarQube / Pylint are not installed.

Severity levels:
  CRITICAL - likely bug or security hole (bare except, eval/exec, SQL built from strings,
             mutable default argument, syntax error)
  WARNING  - code smell (unused import, unused local variable, very long function)

Usage:  python tools/static_check.py [path ...]      exit code 1 if any CRITICAL issue
"""
import ast
import os
import sys

MAX_FUNC_LINES = 60


def py_files(paths):
    for root in paths:
        if os.path.isfile(root):
            yield root
            continue
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "venv", ".venv")]
            for name in files:
                if name.endswith(".py"):
                    yield os.path.join(folder, name)


def used_names(tree):
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.value.id for n in ast.walk(tree)
              if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    return names


def check_imports(tree, path, out):
    if os.path.basename(path) == "__init__.py":
        return
    used = used_names(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound = (alias.asname or alias.name).split(".")[0]
                if bound not in used and bound != "*":
                    out.append(("WARNING", path, node.lineno, f"Unused import '{bound}'"))


def check_function(func, path, out):
    length = (func.end_lineno or func.lineno) - func.lineno + 1
    if length > MAX_FUNC_LINES:
        out.append(("WARNING", path, func.lineno, f"Function '{func.name}' is {length} lines long"))
    for default in func.args.defaults + func.args.kw_defaults:
        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
            out.append(("CRITICAL", path, func.lineno, f"Mutable default argument in '{func.name}'"))
    stored, loaded = {}, set()
    for node in ast.walk(func):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                stored.setdefault(node.id, node.lineno)
            else:
                loaded.add(node.id)
    for name, line in stored.items():
        if name not in loaded and not name.startswith("_"):
            out.append(("WARNING", path, line, f"Local variable '{name}' assigned but never used"))


def check_calls(node, path, out):
    if isinstance(node, ast.Call):
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id in ("eval", "exec"):
            out.append(("CRITICAL", path, node.lineno, f"Use of {fn.id}()"))
        if isinstance(fn, ast.Attribute) and fn.attr in ("execute", "executescript") and node.args:
            arg = node.args[0]
            if isinstance(arg, (ast.JoinedStr, ast.BinOp)) or (
                    isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == "format"):
                out.append(("CRITICAL", path, node.lineno, "SQL built from a string expression (injection risk)"))
    if isinstance(node, ast.ExceptHandler) and node.type is None:
        out.append(("CRITICAL", path, node.lineno, "Bare 'except:' hides real errors"))


def analyse(path):
    out = []
    try:
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
    except SyntaxError as exc:
        return [("CRITICAL", path, exc.lineno or 0, f"Syntax error: {exc.msg}")]
    check_imports(tree, path, out)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check_function(node, path, out)
        check_calls(node, path, out)
    return out


def main(argv):
    issues = []
    files = list(py_files(argv or ["backend", "tests", "tools"]))
    for path in files:
        issues.extend(analyse(path))
    for severity, path, line, message in sorted(issues, key=lambda i: (i[0] != "CRITICAL", i[1], i[2])):
        print(f"{severity:8} {path}:{line}: {message}")
    critical = sum(1 for i in issues if i[0] == "CRITICAL")
    warnings = len(issues) - critical
    print(f"\nFiles scanned: {len(files)} | Critical bugs: {critical} | Warnings: {warnings}")
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
