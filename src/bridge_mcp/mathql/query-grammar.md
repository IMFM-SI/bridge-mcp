# MathQL query grammar

This document describes the grammar of the MathQL query language: the structure of a
query, the expressions that appear in its clauses, and the shape of its results.

## Queries

A query is a JSON object:

```
{
  "domains":     [[variable, domain], ...],
  "output":      [[name, "<expression>"], ...],
  "condition":   "<expression>",
  "order":       [["<expression>", "asc" | "desc"], ...],
  "limit":       <integer>,
  "postprocess": [[name, "<expression>"], ...]
}
```

- `domains` (required) binds distinct variables, each ranging over a named domain;
  several bindings form a join.
- `output` (required) is an ordered list of `[name, expression]` pairs. Each name is
  a plain identifier, distinct from the other names, and names a result column whose
  value is the value of the expression. The list order is the column order of every
  row. Each output expression may refer to the variables bound by `domains`.
- `condition` (optional, default `true`) restricts the result to the objects, or
  tuples of objects, that satisfy it; it must have type `bool`.
- `order` (optional) sorts the result by one or more scalar expressions, each
  ascending or descending; an order expression may refer to the output columns
  by name.
- `limit` (optional) bounds the number of rows returned.
- `postprocess` (optional, default empty) is an ordered list of `[name, expression]`
  pairs, each appended to every row as a further column, evaluated outside the
  database after it returns the rows. Each name is a plain identifier, distinct from
  the output column names and from the names of the other entries. Each expression may
  refer to the output columns and to the entries preceding it, so the list order
  determines the names in scope. A postprocess column whose expression fails to
  evaluate has the value `null`.

## Results

A query returns the matching rows. Each row is a list of `[name, value]` pairs: the
output columns in the order `output` names them, then the postprocess columns in the
order `postprocess` names them. An absent value is `null`.

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
- `string` — text in UTF-8; a value may carry any character.
- `list` τ — an ordered list of values of type τ.
- a product `τ₁ * … * τₙ` — a tuple of components of the given types; the nullary
  product is the unit type.

A query is written without type annotations; types appear in error messages.

## Expressions

Expressions in every clause follow the grammar summarized below. The alternatives
appear in order of precedence; **Precedence and associativity** gives the precedence
levels and the associativity of each operator.

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
       | expr "." field
       | integer
       | string
       | "true"
       | "false"
       | variable
       | domain "[" expr "," … "," expr "]"
       | "id" "(" expr ")"
       | function "(" expr "," … "," expr ")"
       | constant
       | "(" expr ")"
       | "(" expr "," … "," expr ")"
       | "[" "]"
       | "[" expr "," … "," expr "]"
```

A `variable`, an `expr . field` on a domain field, and a `domain[…]` denote
*objects*; they appear only under `id` or as the head of a further projection. A
query that returns or compares a bare object is ill-typed.

Every identifier — a variable, a column name, a domain name, a field label, a constant
and a function — is ASCII: a letter followed by letters, digits and `_`. UTF-8 text
belongs in string literals and in the values a database holds.

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
- `defined e` and `undefined e` — of type `bool`. `defined e` is `true` when `e`
  evaluates to a value other than `null`, and `false` when `e` evaluates to `null`
  and when evaluating `e` fails. `undefined e` is `true` in exactly the cases where
  `defined e` is `false`.
- `id(e)` — the primary key of the object `e`: for a single-column key, that
  column's value; otherwise the tuple of its components.
- `f(e₁, …, eₙ)` — the function `f` applied to the given arguments; its type is `f`'s
  declared result type. Each database declares its functions in two groups: those
  available in `condition`, `output` and `order`, and those available in
  `postprocess`.
- `e.i` — the `i`-th component (counting from zero) of the tuple `e`; its type is
  that component's type.
- `42` – integer literal of type `int`
- `'text'` – string literal of type `string`, holding any UTF-8 text; a literal single
  quote is written by doubling it (`'it''s'`).
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
- `!` (UTF-8 `¬`), unary `-`, `defined`, and `undefined`, the prefix operators.
