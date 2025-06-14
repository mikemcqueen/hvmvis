from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import ClassVar, NamedTuple, Optional

HAS_LOC_TAGS = {'VAR', 'LAM', 'APP', 'SUP', 'DUP', 'OPX', 'OPY', 'MAT'}
NUM_TAGS = {'U32', 'I32', 'F32'}
TAKEN_TAG = "___"
EMPTY_TAG = "EMP"

class Term(NamedTuple):
    tag: str
    lab: int
    loc: int

    def __repr__(self) -> str:
        return f"{self.tag[:3]},{self.lab:03d},{self.loc:04d}"

    def taken(self):
        return self.tag == TAKEN_TAG

    def empty(self) -> bool:
        return self.tag == EMPTY_TAG

    def has_loc(self) -> bool:
        return self.tag in HAS_LOC_TAGS

    def has_num_tag(self) -> bool:
        return self.tag in NUM_TAGS

EMPTY_TERM = Term(EMPTY_TAG, 0, 0)

@dataclass(eq=False)
class MemOp:
    seq: int
    tid: int
    itr_name: str
    op: str
    lvl: int
    put: Optional[Term]
    got: Optional[Term]
    loc: int
    node: Optional['Node'] = None
    #ref: Optional['ExpandRef'] = None
    #itr: Optional['Interaction'] = None
    
    def __repr__(self) -> str:
        if self.op == 'EXCH':
            return f"{self.tid},{self.itr_name},{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.put.tag},{self.put.loc},{self.loc}"
        elif self.op == 'POP' or self.op == 'LOAD':
            return f"{self.tid},{self.itr_name},{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.loc}"
        else: # self.op == 'STOR'
            return f"{self.tid},{self.itr_name},{self.op},{self.lvl},{self.put.tag},{self.put.loc},{self.loc}"

    def __str__(self) -> str:
        if self.op == 'EXCH':
            return f"{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.put.tag},{self.put.loc},{self.loc}"
        elif self.op == 'POP' or self.op == 'LOAD':
            return f"{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.loc}"
        else: # self.op == 'STOR'
            return f"{self.op},{self.lvl},{self.put.tag},{self.put.loc},{self.loc}"

    def is_take(self) -> bool:
        return self.op == 'EXCH' and self.put.taken()

    def is_root_itr(self) -> bool:
        return self.itr_name == '______'

    def is_appref_itr(self) -> bool:
        return self.itr_name == 'APPREF'

    def is_applam_itr(self) -> bool:
        return self.itr_name == 'APPLAM'

    def is_matnum_itr(self) -> bool:
        return self.itr_name[:3] == 'MAT' and self.itr_name[3:] in NUM_TAGS

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

    @property
    def tag(self): return self.term.tag
    @property
    def lab(self): return self.term.lab
    @property
    def loc(self): return self.term.loc

    def __repr__(self) -> str:
        return f"{self.term} {type(self.node).__name__}({self.node.ref.def_idx if self.node and self.node.ref else 'None'})"

    def empty(self) -> bool:
        return self.term.empty()

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

@dataclass(eq=False)
class NodeProxy:
    ref: 'ExpandRef'
    #itr: 'Interaction'

@dataclass(eq=False)
class Node:
    neg: NodeTerm
    pos: NodeTerm
    ref: 'ExpandRef'
    #itr: 'Interaction'
    # this might make sense
    #parent: Optional[Node]
    #child: Optional[Node]

    def validate(self, loc: int):
        neg_loc = self.neg.stores[0].loc
        assert loc in (neg_loc, neg_loc + 1)

    def take(self, loc: int):
        self.validate(loc)
        if loc == self.neg.stores[0].loc:
            # late night hack
            self.neg = NodeTerm(EMPTY_TERM, stores=[self.neg.stores[0]])
        else:
            self.pos = NodeTerm(EMPTY_TERM, stores=[self.pos.stores[0]])

    def term_at(self, loc: int):
        self.validate(loc)
        return self.neg if loc == self.neg.stores[0].loc else self.pos

class DefIdx(IntEnum):
    MAT=1024

class HasNodes(ABC):
    @abstractmethod
    def first_loc(self) -> int:
        pass

    @abstractmethod
    def last_loc(self) -> int:
        pass

    def contains(self, loc: int):
        return loc >= self.first_loc() and loc <= self.last_loc()

@dataclass(eq=False, kw_only=True)
class Interaction(ABC):
    redex: Optional[Redex] = None
    memops: list[MemOp] = field(default_factory=list)

    @abstractmethod
    def name(self) -> str:
        pass

@dataclass(eq=False, kw_only=True)
class ExpandRef(Interaction, HasNodes):
    def_idx: int
    nodes: list[Node] = field(default_factory=list)

    @property
    def id(self): return (self.def_idx, self.first_loc)

    def __repr__(self) -> str:
        return f"def_idx: {self.def_idx} {self.redex}"

    def name() -> str:
        pass

    def first_loc(self) -> int:
        return self.nodes[0].neg.stores[0].loc

    def last_loc(self) -> int:
        return self.nodes[-1].pos.stores[0].loc

@dataclass(eq=False)
class AppRef(ExpandRef):
    NAME = 'APPREF'
    def __init__(self, def_idx: int, redex: Optional[Redex]):
        super().__init__(redex=redex, def_idx=def_idx)

    def name(self) -> str:
        return AppRef.NAME

@dataclass(eq=False)
class AppLam(Interaction):
    NAME = 'APPLAM'
    def __init__(self, redex: Redex):
        super().__init__(redex=redex)

    def name(self) -> str:
        return AppLam.NAME

@dataclass(eq=False)
class DupNum(Interaction):
    NAME = 'DUPU32'
    def __init__(self, redex: Redex):
        super().__init__(redex=redex)

    def name(self) -> str:
        return DupNum.NAME

@dataclass(eq=False)
class OpxNum(Interaction):
    NAME = 'OPXU32'
    def __init__(self, redex: Redex):
        super().__init__(redex=redex)

    def name(self) -> str:
        return OpxNum.NAME

@dataclass(eq=False)
class OpyNum(Interaction):
    NAME = 'OPYU32'
    def __init__(self, redex: Redex):
        super().__init__(redex=redex)

    def name(self) -> str:
        return OpyNum.NAME

@dataclass(eq=False)
class MatNum(Interaction): # , HasNodes):
    NAME = 'MATU32'
    def __init__(self, redex: Redex):
        super().__init__(redex=redex)

    def name(self) -> str:
        return MatNum.NAME

    def first_loc(self) -> int:
        pass

    def last_loc(self) -> int:
        pass

@dataclass(eq=False)
class MatRef(Interaction):
    NAME = 'MATREF'
    def __init__(self, redex: Redex):
        super().__init__(redex=redex)

    def name(self):
        return MatRef.NAME
