"""Parse MathQL expressions into the input AST, via the Lark grammar."""

import json
from importlib import resources

from lark import Lark, Token, Transformer, v_args
from lark.exceptions import LarkError, VisitError
from lark.tree import Meta

from bridge_mcp.mathql import input as input_ast
from bridge_mcp.mathql.errors import MathQLError
from bridge_mcp.mathql.operators import BinaryOp, ComparisonOp, UnaryOp

_GRAMMAR = (
    resources.files("bridge_mcp.mathql").joinpath("grammar.lark").read_text(encoding="utf-8")
)


def _span(meta: Meta) -> input_ast.Span | None:
    if meta.empty:
        return None
    return input_ast.Span(
        line=meta.line, column=meta.column, start=meta.start_pos, end=meta.end_pos
    )


@v_args(meta=True, inline=True)
class _ToAst(Transformer[Token, input_ast.Expr]):
    def ite(
        self, meta: Meta, cond: input_ast.Expr, then_: input_ast.Expr, else_: input_ast.Expr
    ) -> input_ast.Ite:
        return input_ast.Ite(cond, then_, else_, _span(meta))

    def or_(self, meta: Meta, left: input_ast.Expr, right: input_ast.Expr) -> input_ast.BinOp:
        return input_ast.BinOp(BinaryOp.OR, left, right, _span(meta))

    def and_(self, meta: Meta, left: input_ast.Expr, right: input_ast.Expr) -> input_ast.BinOp:
        return input_ast.BinOp(BinaryOp.AND, left, right, _span(meta))

    def add(self, meta: Meta, left: input_ast.Expr, right: input_ast.Expr) -> input_ast.BinOp:
        return input_ast.BinOp(BinaryOp.ADD, left, right, _span(meta))

    def sub(self, meta: Meta, left: input_ast.Expr, right: input_ast.Expr) -> input_ast.BinOp:
        return input_ast.BinOp(BinaryOp.SUB, left, right, _span(meta))

    def mul(self, meta: Meta, left: input_ast.Expr, right: input_ast.Expr) -> input_ast.BinOp:
        return input_ast.BinOp(BinaryOp.MUL, left, right, _span(meta))

    def eq(self, meta: Meta, left: input_ast.Expr, right: input_ast.Expr) -> input_ast.Compare:
        return input_ast.Compare(ComparisonOp.EQ, left, right, _span(meta))

    def ne(self, meta: Meta, left: input_ast.Expr, right: input_ast.Expr) -> input_ast.Compare:
        return input_ast.Compare(ComparisonOp.NE, left, right, _span(meta))

    def lt(self, meta: Meta, left: input_ast.Expr, right: input_ast.Expr) -> input_ast.Compare:
        return input_ast.Compare(ComparisonOp.LT, left, right, _span(meta))

    def le(self, meta: Meta, left: input_ast.Expr, right: input_ast.Expr) -> input_ast.Compare:
        return input_ast.Compare(ComparisonOp.LE, left, right, _span(meta))

    def gt(self, meta: Meta, left: input_ast.Expr, right: input_ast.Expr) -> input_ast.Compare:
        return input_ast.Compare(ComparisonOp.GT, left, right, _span(meta))

    def ge(self, meta: Meta, left: input_ast.Expr, right: input_ast.Expr) -> input_ast.Compare:
        return input_ast.Compare(ComparisonOp.GE, left, right, _span(meta))

    def not_(self, meta: Meta, expr: input_ast.Expr) -> input_ast.UnOp:
        return input_ast.UnOp(UnaryOp.NOT, expr, _span(meta))

    def neg(self, meta: Meta, expr: input_ast.Expr) -> input_ast.UnOp:
        return input_ast.UnOp(UnaryOp.NEG, expr, _span(meta))

    def defined(self, meta: Meta, expr: input_ast.Expr) -> input_ast.Defined:
        return input_ast.Defined(expr, _span(meta))

    def undefined(self, meta: Meta, expr: input_ast.Expr) -> input_ast.Undefined:
        return input_ast.Undefined(expr, _span(meta))

    def proj(self, meta: Meta, obj: input_ast.Expr, index: Token) -> input_ast.Proj:
        return input_ast.Proj(obj, int(index), _span(meta))

    def field(self, meta: Meta, obj: input_ast.Expr, label: Token) -> input_ast.Field:
        if isinstance(obj, input_ast.Const):
            return input_ast.Field(obj.name, str(label), _span(meta))
        raise MathQLError("field access requires a variable, for example x.label")

    def int_(self, meta: Meta, token: Token) -> input_ast.IntLit:
        return input_ast.IntLit(int(token), _span(meta))

    def true_(self, meta: Meta) -> input_ast.BoolLit:
        return input_ast.BoolLit(True, _span(meta))

    def false_(self, meta: Meta) -> input_ast.BoolLit:
        return input_ast.BoolLit(False, _span(meta))

    def str_(self, meta: Meta, token: Token) -> input_ast.StrLit:
        try:
            value = json.loads(str(token))
        except json.JSONDecodeError as exc:
            raise MathQLError(f"invalid string literal {token}") from exc
        return input_ast.StrLit(value, _span(meta))

    def const(self, meta: Meta, token: Token) -> input_ast.Const:
        return input_ast.Const(str(token), _span(meta))

    def empty_list(self, meta: Meta) -> input_ast.ListExpr:
        return input_ast.ListExpr((), _span(meta))

    def list_(self, meta: Meta, *items: input_ast.Expr) -> input_ast.ListExpr:
        return input_ast.ListExpr(items, _span(meta))

    def tuple_(self, meta: Meta, *items: input_ast.Expr) -> input_ast.TupleExpr:
        return input_ast.TupleExpr(items, _span(meta))


_PARSER = Lark(_GRAMMAR, parser="lalr", propagate_positions=True)
_TRANSFORMER = _ToAst()


def parse_expression(text: str) -> input_ast.Expr:
    """Parse a MathQL expression. Raises `MathQLError` on malformed input."""
    try:
        tree = _PARSER.parse(text)
        return _TRANSFORMER.transform(tree)
    except VisitError as exc:
        if isinstance(exc.orig_exc, MathQLError):
            raise exc.orig_exc from None
        raise
    except LarkError as exc:
        raise MathQLError(f"parse error: {exc}") from exc
