from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple, Optional

class Term(NamedTuple):
    tag: str
    lab: int
    loc: int

@dataclass(eq=False)
class MemOp:
    seq: int
    tid: int
    itr: str
    op: str
    lvl: int
    put: Optional[Term]
    got: Optional[Term]
    loc: int
    
    def __repr__(self) -> str:
        if self.op == 'EXCH':
            return f"{self.tid},{self.itr},{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.put.tag},{self.put.loc},{self.loc}"
        elif self.op == 'POP' or self.op == 'LOAD':
            return f"{self.tid},{self.itr},{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.loc}"
        else: # self.op == 'STOR'
            return f"{self.tid},{self.itr},{self.op},{self.lvl},{self.put.tag},{self.put.loc},{self.loc}"

@dataclass(eq=False)
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

@dataclass(eq=False)
class Redex:
    neg: Term
    pos: Term
    app_ref: Optional['AppRef'] = None
    #push_op: Optional[MemOp] = None
    #pop_op: Optional[MemOp] = None

    def is_appref(self):
        return self.neg.tag == 'APP' and self.pos.tag == 'REF'

@dataclass(eq=False)
class Node:
    loc: int
    neg: NodeTerm
    pos: NodeTerm
    app_ref: 'AppRef'
    # this probably doesn't make sense
    #parent: Optional[Node]
    #child: Optional[Node]

@dataclass(eq=False)
class AppRef:
    ref: int
    redex: Optional[Redex] = None
    nodes: list[Node] = field(default_factory=list)

    @property
    def id(self): return (self.ref, self.nodes[0].neg.stores[0].loc)

    @property
    def first_loc(self): return self.nodes[0].neg.stores[0].loc

    @property
    def last_loc(self):
        # if this is a MAT node, the actual size might (eventually) be two more
        # than what expand_ref gives us.
        # it's a bit of a hack here because I don't know which MemOps have been
        # "processed" by the visualizer yet. Assuming unprocessed for now but
        # i'll have to return to this later.
        # TODO: FIXME
        mat = self.nodes[0].neg.tag == 'MAT'
        last = self.nodes[-1].pos.stores[0].loc
        return last if not mat else last + 2
