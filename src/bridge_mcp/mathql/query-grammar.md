# MathQL query grammar

This document describes the grammar of the MathQL query language: the structure of a
query and the expressions that appear in its condition and ordering.

## Queries

A query is a JSON object:

```
{
  "domains":   [[variable, domain], ...],
  "output":    { name: "<expression>", ... },
  "condition": "<expression>",
  "order":     [["<expression>", "asc" | "desc"], ...],
  "limit":     <integer>
}
```

- `domains` (required) binds one or more variables, each ranging over a named
  domain; several bindings form a join.
- `output` (required) maps each result column name (a plain identifier) to the
  expression whose value that column returns; the expressions use the same
  grammar as `condition`. The output expressions are independent of one
  another: one may not refer to another's column name.
- `condition` (optional, default `true`) restricts the result to the objects, or
  tuples of objects, that satisfy it; it must have type `bool`.
- `order` (optional) sorts the result by one or more scalar expressions, each
  ascending or descending; an order expression may refer to the output columns
  by name.
- `limit` (optional) bounds the number of rows returned.

## Domains

A domain is a named collection of objects (a table). A variable bound to a domain
denotes one object of it. An object has two kinds of field:

- an *input field*, a scalar value (`int`, `bool`, `string`, or a list), written
  `x.field`;
- a *domain field*, a link to an object of another domain, also written `x.field`,
  whose value is that object — which can itself be projected (`x.field.field2`) or
  passed to `id`.

Every object has a *primary key*, the tuple of its identifying input fields;
`id(x)` returns it. The available domains, their input fields, and their domain
fields are obtained from the `describe` tool.

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

The output, condition, and order expressions are written in the following grammar. It is
ambiguous as written, but the clauses are written in the order of precedence.
Precedence and associativity are described in detail in **Precedence and associativity** below.

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
       | "id" expr
       | expr "." integer
       | expr "." field
       | integer
       | string
       | "true"
       | "false"
       | variable
       | domain "[" expr "," … "," expr "]"
       | constant
       | "(" expr ")"
       | "(" expr "," … "," expr ")"
       | "[" "]"
       | "[" expr "," … "," expr "]"
```

A `variable`, an `expr . field` on a domain field, and a `domain[…]` denote
*objects*, not scalars; they appear only under `id` or as the head of a further
projection. A query that returns or compares a bare object is ill-typed.

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
- `id e` — the primary key of the object `e`: for a single-column key, that
  column's value; otherwise the tuple of its components.
- `e.i` — the `i`-th component (counting from zero) of the tuple `e`; its type is
  that component's type.
- `42` – integer literal of type `int`
- `'text'` – string literal of type `string`; a literal single quote is written by
  doubling it (`'it''s'`).
- `true` and `false` – truth values of type `bool`
- `x` — a variable, denoting the object it is bound to.
- `x.field` — the field `field` of the object `x`: an input field yields its scalar
  value (of the field's declared type), a domain field yields the linked object
  (see `describe` tool).
- `D[e₁, …, eₙ]` — the object of domain `D` whose primary key is `(e₁, …, eₙ)`.
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
- `!` (UTF-8 `¬`), unary `-`, `defined`, `undefined`, and `id`, the prefix operators.
