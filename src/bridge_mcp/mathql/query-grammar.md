# MathQL query grammar

This document describes the grammar of the MathQL query language: the structure of a
query and the expressions that appear in its condition and ordering.

## Queries

A query is a JSON object:

```
{
  "domains":   [[variable, domain], ...],
  "output":    [item, ...],
  "condition": "<expression>",
  "order":     [["<expression>", "asc" | "desc"], ...],
  "limit":     <integer>
}
```

- `domains` (required) binds one or more variables, each ranging over a named
  domain; several bindings form a join.
- `output` (required) lists the values to return. An item is either a variable `x`,
  which returns the whole object, or `x.field`, which returns a single field.
- `condition` (optional, default `true`) restricts the result to the objects, or
  tuples of objects, that satisfy it; it must have type `bool`.
- `order` (optional) sorts the result by one or more scalar expressions, each
  ascending or descending.
- `limit` (optional) bounds the number of rows returned.

## Domains

The available domains and their fields are obtained from the `describe` tool.

## Types

Expressions are typed. The types are:

```
type ::= "int"
       | "bool"
       | "string"
       | "list" type
       | type "*" … "*" type
```

- `int` — integers.
- `bool` — the truth values `true` and `false`.
- `string` — text.
- `list` τ — an ordered list of values of type τ.
- a product `τ₁ * … * τₙ` — a tuple of components of the given types; the nullary
  product is the unit type.

Types are never written down in a query, but may appear in error messages.

## Expressions

The condition and the order expressions are written in the following grammar. It is
ambiguous as written, but the clauses are written in the order of precedence.
Precedence and associativity are described in detail in *Precedence and associativity** below.

```
expr ::= "if" expr "then" expr "else" expr
       | expr "||" expr
       | expr "&&" expr
       | expr "==" expr
       | expr "!=" expr
       | expr "<" expr
       | expr "<=" expr
       | expr ">" expr
       | expr ">=" expr
       | expr "+" expr
       | expr "-" expr
       | expr "*" expr
       | "!" expr
       | "-" expr
       | "defined" expr
       | "undefined" expr
       | expr "." integer
       | integer
       | string
       | "true"
       | "false"
       | variable "." field
       | constant
       | "(" expr ")"
       | "(" expr "," … "," expr ")"
       | "[" "]"
       | "[" expr "," … "," expr "]"
```

The meaning and types of the above expressions is as follows:

- `if c then a else b` — evaluates to `a` when `c` is true and to `b` otherwise; `c` must be
  `bool`, the two branches must have the same type, which is the type of the whole
  expression.
- `e1 || e2` and `e1 && e2` — disjunction and conjunction; the operands and the
  result are `bool`.
- `e1 == e2`, `e1 != e2`, `e1 < e2`, `e1 <= e2`, `e1 > e2`, `e1 >= e2` — comparisons;
  the two operands must have the same type, and the result is `bool`.
- `e1 + e2`, `e1 - e2`, `e1 * e2`, and `- e` — integer arithmetic; the operands and
  the result are `int`.
- `! e` — boolean negation; the operand and the result are `bool`.
- `defined e` and `undefined e` — test whether `e` has a value or is absent; the
  result is `bool`.
- `e.i` — the `i`-th component (counting from zero) of the tuple `e`; its type is
  that component's type.
- `42` – integer literal of type `int`
- `"text"` – string literal of type `string`
- `true` and `false` – truth values of type `bool`
- `x.field` — the value of the field `field` of the variable `x`, of the field's
  declared type (see `describe` tool).
- `c` — a named constant declared by the database, of its declared type (see `describe` tool)
- `(e)` — grouping
- `(e1, …, en)` — a tuple, of the corresponding product type.
- `[]` and `[e1, …, en]` — a list literal, of type `list τ` where its elements have type `τ`.

## Precedence and associativity

The operators are listed in order of increasing precedence; operators on the same
line share a precedence level. Alternative UTF-8 forms shown in parentheses are
accepted equivalents:

- `if … then … else …`, the conditional.
- `||` (UTF-8 `∨`), disjunction, left-associative.
- `&&` (UTF-8 `∧`), conjunction, left-associative.
- `==` `!=` `<` `<=` `>` `>=`, comparison, non-associative (UTF-8 `=`, `≠`,
  `≤`, `≥`).
- `+` `-`, addition and subtraction, left-associative.
- `*`, multiplication, left-associative.
- `!` (UTF-8 `¬`), unary `-`, `defined`, and `undefined`, the prefix operators.
