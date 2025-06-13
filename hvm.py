from dataclasses import dataclass, field
from enum import IntEnum
from typing import NamedTuple, Optional

class Term(NamedTuple):
    tag: str
    lab: int
    loc: int

    HAS_LOC_TAGS = {'VAR', 'LAM', 'APP', 'SUP', 'DUP', 'OPX', 'OPY', 'MAT'}
    NUM_TAGS = {'U32', 'I32', 'F32'}

    def has_loc(self):
        return self.tag in Term.HAS_LOC_TAGS

    def has_num_tag(self):
        return self.tag in Term.NUM_TAGS

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

    def is_root_itr(self):
        return self.itr == '______'

    def is_appref_itr(self):
        return self.itr == 'APPREF'

    def is_applam_itr(self):
        return self.itr == 'APPLAM'

    def is_matnum_itr(self):
        return self.itr[:3] == 'MAT' and self.itr[3:] in Term.NUM_TAGS

@dataclass(eq=False)
class NodeTerm:
    class Kind(IntEnum):
        Var = 1
        Bod = 2
        Arg = 3
        Ret = 4
        Arm = 5

    term: Term
    node: Optional['Node | NodeProxy'] = None
    kind: Optional[Kind] = None
    loads: list[MemOp] = field(default_factory=list)
    stores: list[MemOp] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"{self.term} {type(self.node).__name__}({self.node.ref.def_idx if self.node and self.node.ref else 'None'})"

    @property
    def tag(self): return self.term.tag
    @property
    def lab(self): return self.term.lab
    @property
    def loc(self): return self.term.loc

TermMap = dict[Term, NodeTerm]

# TODO: perhaps a "Pair" base class of Redex and Node?
@dataclass(eq=False)
class Redex:
    # These are stored as NodeTerms for convenience, to assist looking up the
    # origin node or last node that a term was stored to/loaded from.
    # However, that information isn't available for all terms, in which case
    # this is just a thin wrapper around a Term with empty load/store lists.
    # The alternative would be to store simple Terms here, and pass around a
    # TermMap anywhere we needed to do a lookup.
    neg: NodeTerm
    pos: NodeTerm

    #def __repr__(self) -> str:
    #return f"{self.neg.term} {self.pos.term}"

    # of questionable necessity. technically neg.node.ref gets us this
    #ref: Optional['ExpandRef'] = None
    # similarly, i believe, neg.stores/neg.loads gets us these
    #push_op: Optional[MemOp] = None
    #pop_op: Optional[MemOp] = None
    #def is_appref(self):
    #    return self.neg.tag == 'APP' and self.pos.tag == 'REF'

# hack-o-matic.. or.. beautiful design pattern.. judge not lest u be judged
@dataclass(eq=False)
class NodeProxy:
    ref: 'ExpandRef'

@dataclass(eq=False)
class Node:
    neg: NodeTerm
    pos: NodeTerm
    ref: 'ExpandRef'
    # this might make sense
    #parent: Optional[Node]
    #child: Optional[Node]

class DefIdx(IntEnum):
    MAT=1024

@dataclass(eq=False)
class ExpandRef:
    def_idx: int
    redex: Optional[Redex] = None
    nodes: list[Node] = field(default_factory=list)

    @property
    def first_loc(self): return self.nodes[0].neg.stores[0].loc

    @property
    def last_loc(self): return self.nodes[-1].pos.stores[0].loc

    @property
    def id(self): return (self.def_idx, self.first_loc)

    def __repr__(self) -> str:
        return f"def_idx: {self.def_idx} {self.redex}"

    def contains(self, loc: int):
        return loc >= self.first_loc and loc <= self.last_loc

