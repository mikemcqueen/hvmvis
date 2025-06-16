from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import NamedTuple, Optional

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
TAKEN_TERM = Term(TAKEN_TAG, 0, 0)

class MemOpProxy(NamedTuple):
    loc: int

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
    # a MemOp occurs within the memory of a Node: MemOp.loc is either the loc
    # Node.neg or the loc of Node.pos
    node: Optional['Node'] = None
    # a MemOp originates from an interaction. Often, but not always, the same
    # as node.ref.
    itr: Optional['Interaction'] = None

    def __repr__(self) -> str:
        if self.op == 'EXCH':
            return f"{self.tid},{self.itr_name},{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.put.tag},{self.put.loc},{self.loc}"
        if self.op in ('POP', 'LOAD'):
            return f"{self.tid},{self.itr_name},{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.loc}"
        # self.op == 'STOR'
        return f"{self.tid},{self.itr_name},{self.op},{self.lvl},{self.put.tag},{self.put.loc},{self.loc}"

    def __str__(self) -> str:
        if self.op == 'EXCH':
            return f"{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.put.tag},{self.put.loc},{self.loc}"
        if self.op in ('POP', 'LOAD'):
            return f"{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.loc}"
        # self.op == 'STOR'
        return f"{self.op},{self.lvl},{self.put.tag},{self.put.loc},{self.loc}"

    def is_take(self) -> bool:
        return self.op == 'EXCH' and self.put.taken()

    def is_swap(self) -> bool:
        return self.op == 'EXCH' and not self.put.taken()

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
    #kind: Optional[Kind] = None
    loads: list[MemOp] = field(default_factory=list)
    stores: list[MemOp | MemOpProxy] = field(default_factory=list)

    @property
    def tag(self): return self.term.tag
    @property
    def lab(self): return self.term.lab
    @property
    def loc(self): return self.term.loc
    @property
    def mem_loc(self): return self.stores[0].loc

    def __repr__(self) -> str:
        return f"{self.term} {type(self.node).__name__}({self.node.ref.def_idx if self.node and self.node.ref else 'None'})"

    def empty(self) -> bool:
        return self.term.empty()

@dataclass(eq=False)
class Redex:
    # These are stored as NodeTerms for convenience, to assist looking up the
    # origin node of a push/pop operation.
    neg: NodeTerm
    pos: NodeTerm

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

    def validate(self, loc: int):
        neg_loc = self.neg.stores[0].loc
        assert loc in (neg_loc, neg_loc + 1), f"loc {loc} neg_loc {neg_loc}"

    def set_term_at(self, loc: int, term: Term):
        self.validate(loc)
        memop = MemOpProxy(loc)
        if loc == self.neg.mem_loc:
            self.neg = NodeTerm(term, self, stores=[memop])
        else:
            self.pos = NodeTerm(term, self, stores=[memop])

    def get_term_at(self, loc: int) -> NodeTerm:
        self.validate(loc)
        return self.neg if loc == self.neg.mem_loc else self.pos

    def take(self, loc: int):
        self.set_term_at(loc, TAKEN_TERM)

    def swap(self, loc: int):
        self.set_term_at(loc, EMPTY_TERM)


class DefIdx(IntEnum):
    MAT = 1024

class HasNodes(ABC):
    @abstractmethod
    def first_loc(self) -> int:
        pass

    @abstractmethod
    def last_loc(self) -> int:
        pass

    def contains(self, loc: int):
        return self.first_loc() <= loc <= self.last_loc()

@dataclass(eq=False, kw_only=True)
class Interaction(ABC):
    idx: int
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

    def name(self) -> str:
        pass

    def first_loc(self) -> int:
        return self.nodes[0].neg.stores[0].loc

    def last_loc(self) -> int:
        return self.nodes[-1].pos.stores[0].loc

@dataclass(eq=False)
class AppRef(ExpandRef):
    NAME = 'APPREF'
    def __init__(self, def_idx: int, redex: Optional[Redex], idx: int):
        super().__init__(redex=redex, def_idx=def_idx, idx=idx)

    def name(self) -> str:
        return AppRef.NAME

@dataclass(eq=False)
class AppLam(Interaction):
    NAME = 'APPLAM'
    def __init__(self, redex: Redex, idx: int):
        super().__init__(redex=redex, idx=idx)

    def name(self) -> str:
        return AppLam.NAME

@dataclass(eq=False)
class DupNum(Interaction):
    NAME = 'DUPU32'
    def __init__(self, redex: Redex, idx: int):
        super().__init__(redex=redex, idx=idx)

    def name(self) -> str:
        return DupNum.NAME

@dataclass(eq=False)
class OpxNum(Interaction):
    NAME = 'OPXU32'
    def __init__(self, redex: Redex, idx: int):
        super().__init__(redex=redex, idx=idx)

    def name(self) -> str:
        return OpxNum.NAME

@dataclass(eq=False)
class OpyNum(Interaction):
    NAME = 'OPYU32'
    def __init__(self, redex: Redex, idx: int):
        super().__init__(redex=redex, idx=idx)

    def name(self) -> str:
        return OpyNum.NAME

@dataclass(eq=False)
class MatNum(ExpandRef):
    NAME = 'MATU32'
    def __init__(self, redex: Redex, idx: int):
        super().__init__(redex=redex, def_idx=DefIdx.MAT, idx=idx)

    def name(self) -> str:
        return MatNum.NAME

@dataclass(eq=False)
class MatRef(Interaction):
    NAME = 'MATREF'
    def __init__(self, redex: Redex, idx: int):
        super().__init__(redex=redex, idx=idx)

    def name(self):
        return MatRef.NAME
