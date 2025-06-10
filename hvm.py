from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple, Optional

class Term(NamedTuple):
    tag: str
    loc: int
    lab: Optional[int] = None

class MemOp(NamedTuple):
    seq: int
    tid: int
    itr: str
    op: str
    lvl: int
    put: Optional[Term]
    got: Optional[Term]
    loc: int
    
    def __str__(self) -> str:
        if self.op == 'EXCH':
            return f"{self.tid},{self.itr},{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.put.tag},{self.put.loc},{self.loc}"
        elif self.op == 'POP' or self.op == 'LOAD':
            return f"{self.tid},{self.itr},{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.loc}"
        else: # self.op == 'STOR'
            return f"{self.tid},{self.itr},{self.op},{self.lvl},{self.put.tag},{self.put.loc},{self.loc}"

@dataclass
class NodeTerm:
    class Kind(Enum):
        Var = 1
        Bod = 2
        Arg = 3
        Ret = 4
        Arm = 5

    term: Term
    node: Optional['Node'] = None
    kind: Optional[Kind] = None
    loads: list[MemOp] = field(default_factory=list)
    stores: list[MemOp] = field(default_factory=list)

    @property
    def tag(self): return self.term.tag
    @property
    def lab(self): return self.term.lab
    @property
    def loc(self): return self.term.loc

@dataclass
class Redex:
    neg: Term
    pos: Term
    app_ref: Optional['AppRef'] = None
    #push_op: Optional[MemOp] = None
    #pop_op: Optional[MemOp] = None

    def is_appref(self):
        return self.neg.tag == 'APP' and self.pos.tag == 'REF'

@dataclass
class Node:
    loc: int
    app_ref: 'AppRef'
    neg: NodeTerm
    pos: NodeTerm
    # this probably doesn't make sense
    #parent: Optional[Node]
    #child: Optional[Node]

@dataclass
class AppRef:
    ref: int
    #app: Term
    #lam: Term
    # --or--
    #app_lam : Redex
    nodes: list[Node] = field(default_factory=list)
