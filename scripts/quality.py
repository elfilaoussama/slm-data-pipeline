from __future__ import annotations
import ast
from typing import Any, Dict, List, Tuple

# Lightweight complexity metrics with optional radon
try:  # pragma: no cover - optional dependency
    from radon.complexity import cc_visit  # type: ignore
except Exception:  # pragma: no cover
    cc_visit = None  # type: ignore


def safe_parse(code: str) -> ast.AST | None:
    try:
        return ast.parse(code)
    except Exception:
        return None


def function_loc(node: ast.AST) -> int:
    start = getattr(node, 'lineno', 1)
    end = getattr(node, 'end_lineno', start)
    return max(0, int(end) - int(start) + 1)


def nesting_depth(node: ast.AST) -> int:
    # Depth of nested control structures within a function
    max_depth = 0

    class Walker(ast.NodeVisitor):
        def __init__(self) -> None:
            self.depth = 0
            super().__init__()

        def generic_visit(self, n: ast.AST) -> None:  # type: ignore[override]
            nonlocal max_depth
            push = isinstance(
                n,
                (
                    ast.If,
                    ast.For,
                    ast.While,
                    ast.With,
                    ast.Try,
                    ast.AsyncFor,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            if push:
                self.depth += 1
                max_depth = max(max_depth, self.depth)
            super().generic_visit(n)
            if push:
                self.depth -= 1

    Walker().visit(node)
    return max_depth


def cyclomatic_complexity(code: str) -> float:
    if cc_visit is None:
        # Fallback heuristic: count branch keywords
        tokens = sum(
            code.count(k)
            for k in [" if ", " for ", " while ", " and ", " or ", " except ", " elif "]
        )
        return 1 + tokens
    try:
        results = cc_visit(code)
        if not results:
            return 1.0
        # average complexity across blocks
        return float(sum(r.complexity for r in results) / len(results))
    except Exception:
        return 1.0


class DocumentationQualityScorer:
    def __init__(self, expected_len: int = 60) -> None:
        self.expected_len = expected_len

    @staticmethod
    def _token_count(text: str) -> int:
        return len((text or "").split())

    def score(self, func_name: str, params: List[str], docstring: str | None) -> Dict[str, Any]:
        doc = docstring or ""
        lower = doc.lower()
        # param coverage: naive check of parameter names present
        covered = 0
        for p in params:
            if p and p.lower() in lower:
                covered += 1
        param_cov = (covered / max(1, len(params))) if params else 1.0
        # return coverage: mentions return(s)
        return_cov = 1.0 if ("return" in lower or "returns" in lower) else 0.0
        # example bonus: detect code fenced blocks or 'example'
        example_bonus = 1.0 if ("example" in lower or "::" in doc or "```" in doc) else 0.0
        # doc length score
        dl = self._token_count(doc)
        doc_length_score = max(0.0, min(1.0, dl / float(self.expected_len)))
        # aggregate (weighted)
        score = 0.45 * param_cov + 0.25 * return_cov + 0.20 * doc_length_score + 0.10 * example_bonus
        tier = (
            "high_quality"
            if score >= 0.7
            else "medium_quality"
            if score >= 0.4
            else "low_quality"
        )
        return {
            "score": round(float(score), 4),
            "tier": tier,
            "param_coverage": param_cov,
            "return_coverage": return_cov,
            "example_bonus": example_bonus,
            "doc_length_score": doc_length_score,
        }

    def synthetic_template(self, func_name: str, params: List[str]) -> str:
        params_sig = ", ".join(params)
        ex_params = ", ".join(f"{p}=..." for p in params[:2])
        example = f"\n\nExamples:\n>>> {func_name}({ex_params})\n" if func_name else ""
        return f"""{func_name}({params_sig})\n\nBriefly describe what this function does.\nArguments:\n{''.join(f'- {p}: description\n' for p in params)}\nReturns:\n- description{example}"""


def ast_equivalent(a_code: str, b_code: str) -> Tuple[bool, str]:
    a_tree = safe_parse(a_code)
    b_tree = safe_parse(b_code)
    if a_tree is None or b_tree is None:
        return False, "parse_error"
    # Compare dumps without attribute line numbers to check structural equivalence
    a_dump = ast.dump(a_tree, include_attributes=False)
    b_dump = ast.dump(b_tree, include_attributes=False)
    return a_dump == b_dump, ("ast_equiv" if a_dump == b_dump else "not_equiv")


def split_code_for_completion(code: str) -> List[Tuple[str, str, str]]:
    """
    AST-aware splitting of a function into (prefix, completion, completion_type).
    Targets:
      - control_flow: split before an if/for/while/try block body
      - argument_list: split inside a long function signature arguments
      - method_body: split inside body between statements
    Returns a list of candidates ensuring prefix+completion parses.
    """
    out: List[Tuple[str, str, str]] = []
    tree = safe_parse(code)
    if tree is None:
        return out
    lines = code.splitlines(True)

    def add(prefix_idx: int, end_idx: int, ctype: str):
        prefix = "".join(lines[:prefix_idx])
        completion = "".join(lines[prefix_idx:end_idx])
        if safe_parse(prefix + completion) is not None:
            out.append((prefix, completion, ctype))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # argument_list split: between def line and first body stmt if long signature
            def_line_end = getattr(node, 'lineno', 1)
            body_start = getattr(node.body[0], 'lineno', def_line_end + 1) if node.body else def_line_end + 1
            if (body_start - def_line_end) >= 2:
                add(def_line_end - 1, body_start - 1, "argument_list")
            # method_body/control_flow: inside body
            for stmt in node.body:
                if isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try)):
                    add(stmt.lineno - 1, getattr(stmt, 'end_lineno', stmt.lineno), "control_flow")
                else:
                    # generic method body split at statement boundaries
                    add(stmt.lineno - 1, getattr(stmt, 'end_lineno', stmt.lineno), "method_body")
    # fallbacks: end chunk
    if not out and len(lines) > 3:
        add(len(lines) - 3, len(lines), "method_body")
    return out
