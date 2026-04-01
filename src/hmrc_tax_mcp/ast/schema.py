"""
AST node types for the HMRC tax rule engine.

The AST is the canonical, deterministic, machine-readable representation of a tax rule.
It is intentionally NOT Turing-complete: no loops, no recursion, no arbitrary execution.

Approved node types:
  Primitive:       CONST, VAR, LET, IF
  Arithmetic:      ADD, SUB, MUL, DIV, NEG
  Comparison:      GT, LT, GTE, LTE, EQ, NEQ
  Logical:         AND, OR, NOT
  Domain-specific: BAND_APPLY, TAPER, CALL
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Primitive nodes
# ---------------------------------------------------------------------------


class ConstNode(BaseModel):
    node: Literal["CONST"]
    # bool must precede int because bool is a subclass of int in Python
    value: bool | int | float
    metadata: dict[str, Any] | None = None


class VarNode(BaseModel):
    node: Literal["VAR"]
    name: str
    metadata: dict[str, Any] | None = None


class LetNode(BaseModel):
    node: Literal["LET"]
    bindings: dict[str, ASTNode]
    body: ASTNode
    metadata: dict[str, Any] | None = None


class IfNode(BaseModel):
    node: Literal["IF"]
    cond: ASTNode
    then: ASTNode
    else_: ASTNode = Field(alias="else")
    metadata: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Arithmetic nodes
# ---------------------------------------------------------------------------


class AddNode(BaseModel):
    node: Literal["ADD"]
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


class SubNode(BaseModel):
    node: Literal["SUB"]
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


class MulNode(BaseModel):
    node: Literal["MUL"]
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


class DivNode(BaseModel):
    node: Literal["DIV"]
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


class NegNode(BaseModel):
    """Unary negation: evaluates `arg` and returns its arithmetic inverse."""
    node: Literal["NEG"]
    arg: ASTNode
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Comparison nodes
# ---------------------------------------------------------------------------


class GtNode(BaseModel):
    node: Literal["GT"]
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


class LtNode(BaseModel):
    node: Literal["LT"]
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


class GteNode(BaseModel):
    node: Literal["GTE"]
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


class LteNode(BaseModel):
    node: Literal["LTE"]
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


class EqNode(BaseModel):
    node: Literal["EQ"]
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


class NeqNode(BaseModel):
    node: Literal["NEQ"]
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Logical nodes
# ---------------------------------------------------------------------------


class AndNode(BaseModel):
    node: Literal["AND"]
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


class OrNode(BaseModel):
    node: Literal["OR"]
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


class NotNode(BaseModel):
    node: Literal["NOT"]
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Domain-specific nodes
# ---------------------------------------------------------------------------


class TaxBand(BaseModel):
    lower: int | float
    upper: int | float | None = None
    rate: float


class BandApplyNode(BaseModel):
    node: Literal["BAND_APPLY"]
    args: list[ASTNode]
    bands: list[TaxBand]
    metadata: dict[str, Any] | None = None


class TaperNode(BaseModel):
    node: Literal["TAPER"]
    args: list[ASTNode]
    threshold: ASTNode
    ratio: ASTNode
    base: ASTNode
    metadata: dict[str, Any] | None = None


class CallNode(BaseModel):
    node: Literal["CALL"]
    name: str
    args: list[ASTNode]
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Discriminated union — order matters for Pydantic disambiguation
# ---------------------------------------------------------------------------

ASTNode = Annotated[
    Union[
        ConstNode, VarNode, LetNode, IfNode,
        AddNode, SubNode, MulNode, DivNode, NegNode,
        GtNode, LtNode, GteNode, LteNode, EqNode, NeqNode,
        AndNode, OrNode, NotNode,
        BandApplyNode, TaperNode, CallNode,
    ],
    Field(discriminator="node"),
]

# Rebuild forward references
for _cls in [LetNode, IfNode, AddNode, SubNode, MulNode, DivNode, NegNode,
             GtNode, LtNode, GteNode, LteNode, EqNode, NeqNode,
             AndNode, OrNode, NotNode, BandApplyNode, TaperNode, CallNode]:
    _cls.model_rebuild()  # type: ignore[attr-defined]


def parse_ast(data: dict[str, Any]) -> ASTNode:
    """Parse a raw dict into a typed ASTNode. Raises ValueError for unknown node types."""
    node_type = data.get("node")
    _map: dict[str, type[BaseModel]] = {
        "CONST": ConstNode, "VAR": VarNode, "LET": LetNode, "IF": IfNode,
        "ADD": AddNode, "SUB": SubNode, "MUL": MulNode, "DIV": DivNode, "NEG": NegNode,
        "GT": GtNode, "LT": LtNode, "GTE": GteNode, "LTE": LteNode,
        "EQ": EqNode, "NEQ": NeqNode,
        "AND": AndNode, "OR": OrNode, "NOT": NotNode,
        "BAND_APPLY": BandApplyNode, "TAPER": TaperNode, "CALL": CallNode,
    }
    cls = _map.get(node_type)  # type: ignore[arg-type]
    if cls is None:
        raise ValueError(f"Unknown AST node type: {node_type!r}")
    return cls.model_validate(data)  # type: ignore[return-value]
