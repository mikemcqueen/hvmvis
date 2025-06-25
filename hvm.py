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

    def taken(self) -> bool:
        return self.tag == TAKEN_TAG

    def has_loc(self) -> bool:
        return self.tag in HAS_LOC_TAGS

    def has_num_tag(self) -> bool:
        return self.tag in NUM_TAGS

EMPTY_TERM = Term(EMPTY_TAG, 0, 0)
TAKEN_TERM = Term(TAKEN_TAG, 0, 0)

@dataclass(eq=False)
class MemOpBase:
    seq: int
    tid: int
    itr_name: str
    op: str
    loc: int

@dataclass(eq=False)
class MemOp(MemOpBase):
    lvl: int
    put: Optional[Term] = None
    got: Optional[Term] = None
    # a MemOp originates in an interaction
    itr: Optional['Interaction'] = None
    # a MemOp operates on a memory location within a Node
    node: Optional['Node'] = None

    def __repr__(self) -> str:
        if self.op == 'EXCH':
            return f"{self.tid},{self.itr_name},{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.put.tag},{self.put.loc},{self.loc}"
        elif self.op in ('POP', 'LOAD'):
            return f"{self.tid},{self.itr_name},{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.loc}"
        else: # self.op == 'STOR'
            return f"{self.tid},{self.itr_name},{self.op},{self.lvl},{self.put.tag},{self.put.loc},{self.loc}"

    def __str__(self) -> str:
        if self.op == 'EXCH':
            return f"{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.put.tag},{self.put.loc},{self.loc}"
        elif self.op in ('POP', 'LOAD'):
            return f"{self.op},{self.lvl},{self.got.tag},{self.got.loc},{self.loc}"
        else: # self.op == 'STOR'
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

# A "moveable" term + the node (if any) it originated from
@dataclass(eq=False)
class NodeTerm:
    term: Term
    node: Optional['Node | NodeProxy'] = None
    is_neg: Optional[bool] = None

    @property
    def tag(self): return self.term.tag
    @property
    def lab(self): return self.term.lab
    @property
    def loc(self): return self.term.loc

    def __repr__(self) -> str:
        def_idx = self.node.ref.def_idx if self.node else '??'
        return f"NodeTerm {self.term} {type(self.node).__name__}({def_idx})"

    def _set_neg(self, is_neg: bool):
        self.is_neg = is_neg

    def copy(self) -> 'NodeTerm':
        return NodeTerm(self.term, self.node, self.is_neg)

class HasNodes(ABC):
    @abstractmethod
    def first_loc(self) -> int:
        pass

    @abstractmethod
    def last_loc(self) -> int:
        pass

    def contains(self, loc: int):
        return self.first_loc <= loc <= self.last_loc

@dataclass(eq=False)
class Redex(MemOpBase):
    neg: NodeTerm
    pos: NodeTerm
    # the interaction this redex was pushed from
    psh_itr: Optional['Interaction'] = None

    def __repr__(self) -> str:
        return f"Redex {self.neg} {self.pos} psh_itr.idx({self.psh_itr.idx})"

    # Redexes are constructed by the parser from MemOps, which only contain
    # the `term` field of a NodeTerm. Once the interaction that this redex
    # originated from is known, the `node` field can potentially be set.
    def _init_itr(self, redex: 'Redex', itr: 'Interaction'):
        assert not self.psh_itr
        self.psh_itr = itr
        #self._init_nodes(itr)
        if not isinstance(itr, HasNodes) or not itr.nodes: return
        for nod_trm in (redex.neg, redex.pos):
            if not nod_trm.term.has_loc(): continue
            node = itr.get_node(nod_trm.loc)
            if node:
                nod_trm.node = node
                node._init_redex(self)

    # explicit name due to clash with MemOp.itr_name field
    def redex_itr_name(self) -> str:
        return f"{self.neg.tag}{self.pos.tag}"

    def get_node_term(self, term: Term) -> NodeTerm:
        if term == self.neg: return self.neg
        if term == self.pos: return self.pos
        return None

    @classmethod
    def new(cls, neg: MemOp, pos: MemOp):
        assert neg.itr_name == pos.itr_name
        assert (neg.op, pos.op) == ('STOR', 'STOR')
        assert neg.put and pos.put
        assert pos.loc == neg.loc + 1
        return cls(
            # MemOpBase
            seq = neg.seq,
            tid = neg.tid,
            itr_name = neg.itr_name,
            op = 'PUSH',
            loc = neg.loc,
            # Redex
            neg = NodeTerm(neg.put),
            pos = NodeTerm(pos.put)
        )

# A static node term that represents a fixed location in "node memory"
@dataclass(eq=False)
class InPlaceNodeTerm(NodeTerm):
    memops: list[MemOp] = field(default_factory=list)
    memop_idx: int = 0
    empty: bool = False
    # the origin node (and term) of whatever term currently inhabits this node
    origin: Optional[NodeTerm] = None

    # hack (i think) for determining ref dependencies. feels wrong. re-visit.
    #loads: list[MemOp] = field(default_factory=list)

    @property
    def mem_loc(self): return self.memops[0].loc

    def __repr__(self) -> str:
        base_repr = super().__repr__()
        return f"{base_repr} memop_idx {self.memop_idx}"

    def set(self, term: Term):
        # EMPTY_TERM is a hack for viewing/animation
        if term != EMPTY_TERM:
            assert self.memop_idx < len(self.memops)
            self.memop_idx += 1
            memop = self.memops[self.memop_idx]
            assert term == memop.put
            self.term = term
            self.empty = False
        else:
            self.empty = True

    def set_origin(self, nod_trm: NodeTerm):
        self.set(nod_trm.term)
        self.origin = nod_trm
        
    def memops_done(self):
        return self.memop_idx == len(self.memops) - 1

@dataclass(eq=False)
class NodeProxy:
    ref: 'ExpandRef'

@dataclass(eq=False)
class Node:
    neg: InPlaceNodeTerm
    pos: InPlaceNodeTerm
    ref: 'ExpandRef'
    # the redex (if any) that was pushed from within this node's ref, which
    # contains a term with the loc of this node. it helps us determine a
    # "context" for this node.
    redex: Optional[Redex] = None

    # this might make sense
    #parent: Optional[Node]
    #child: Optional[Node]

    def __post_init__(self):
        self.neg._set_neg(True)
        self.pos._set_neg(False)

    def __repr__(self) -> str:
        return f"Node {self.neg} {self.pos} ref.idx({self.ref.idx})"

    # called by parser (via Redex._init_itr) after node is constructed
    def _init_redex(self, redex: Redex):
        assert not self.redex
        self.redex = redex

    def contains(self, loc: int):
        neg_loc = self.neg.mem_loc
        return loc in (neg_loc, neg_loc + 1)

    def get(self, loc: int) -> InPlaceNodeTerm:
        assert self.contains(loc), f"loc {loc} neg_loc {neg_loc}"
        return self.neg if loc == self.neg.mem_loc else self.pos

    # funky.
    def set(self, loc: int, term_nod_trm: Term | NodeTerm):
        nod_trm = self.get(loc)
        if isinstance(term_nod_trm, Term):
            nod_trm.set(term_nod_trm)
        else:
            nod_trm.set_origin(term_nod_trm)

    def take(self, loc: int):
        self.set(loc, TAKEN_TERM)

    def swap(self, loc: int):
        self.set(loc, EMPTY_TERM)

    def get_context(self, nod_trm: NodeTerm) -> str:
        if self.redex:
            cls = Interaction.get_class(self.redex.redex_itr_name())
            return cls.get_context(nod_trm)
        return ''

class DefIdx(IntEnum):
    MAT = 1024

@dataclass(eq=False, kw_only=True)
class Interaction(ABC):
    idx: int
    # the popped redex that resulted in this interaction
    redex: Optional[Redex] = None
    # redexes pushed in this interaction
    redexes: list[Redex] = field(default_factory=list)
    memops: list[MemOp] = field(default_factory=list)

    registry: ClassVar[dict[str, type]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        name = getattr(cls, 'NAME', None)
        if name:
            Interaction.registry[name] = cls

    @abstractmethod
    def name(self) -> str:
        pass

    @classmethod
    def get_class(cls, name: str) -> type:
        return Interaction.registry[name]

@dataclass(eq=False, kw_only=True)
class ExpandRef(Interaction, HasNodes):
    def_idx: int
    nodes: list[Node] = field(default_factory=list)

    @property
    def id(self): return (self.def_idx, self.first_loc)
    @property
    def first_loc(self) -> int: return self.nodes[0].neg.mem_loc
    @property
    def last_loc(self) -> int: return self.nodes[-1].pos.mem_loc

    def __repr__(self) -> str:
        return f"ExpandRef {self.id} {self.redex}"

    def _validate(self, loc: int):
        neg_loc = self.neg.mem_loc
        assert loc in (neg_loc, neg_loc + 1), f"loc {loc} neg_loc {neg_loc}"

    def get_node(self, loc: int) -> Node:
        for node in self.nodes:
            if node.contains(loc):
                return node # .get(loc)
        return None

    def memops_done(self) -> bool:
        for node in self.nodes:
            for node_term in (node.neg, node.pos):
                if not node_term.memops_done():
                    return False
        return True

    def name(self) -> str:
        pass

@dataclass(eq=False)
class AppRef(ExpandRef):
    NAME = 'APPREF'
    def __init__(self, def_idx: int, redex: Optional[Redex], idx: int):
        super().__init__(redex=redex, def_idx=def_idx, idx=idx)

    def name(self) -> str:
        return AppRef.NAME

    @classmethod
    def get_context(self, nod_trm: NodeTerm) -> str:
        if nod_trm.is_neg == True:
            return 'arg'
        elif nod_trm.is_neg == False:
            return 'ret'
        else:
            assert False

@dataclass(eq=False)
class AppLam(Interaction):
    NAME = 'APPLAM'
    def __init__(self, redex: Redex, idx: int):
        super().__init__(redex=redex, idx=idx)

    def name(self) -> str:
        return AppLam.NAME

    @classmethod
    def get_context(self, nod_trm: NodeTerm) -> str:
        if nod_trm.is_neg == True:
            return 'var'
        elif nod_trm.is_neg == False:
            return 'bod'
        else:
            assert False

@dataclass(eq=False)
class DupU32(Interaction):
    NAME = 'DUPU32'
    def __init__(self, redex: Redex, idx: int):
        super().__init__(redex=redex, idx=idx)

    def name(self) -> str:
        return DupU32.NAME

    @classmethod
    def get_context(self, nod_trm: NodeTerm) -> str:
        return 'dup'

@dataclass(eq=False)
class OpxU32(Interaction):
    NAME = 'OPXU32'
    def __init__(self, redex: Redex, idx: int):
        super().__init__(redex=redex, idx=idx)

    def name(self) -> str:
        return OpxU32.NAME

    @classmethod
    def get_context(self, nod_trm: NodeTerm) -> str:
        return 'opx'

@dataclass(eq=False)
class OpyU32(Interaction):
    NAME = 'OPYU32'
    def __init__(self, redex: Redex, idx: int):
        super().__init__(redex=redex, idx=idx)

    def name(self) -> str:
        return OpyU32.NAME

    @classmethod
    def get_context(self, nod_trm: NodeTerm) -> str:
        return 'opy'

@dataclass(eq=False)
class MatU32(ExpandRef):
    NAME = 'MATU32'
    def __init__(self, redex: Redex, idx: int):
        super().__init__(redex=redex, def_idx=DefIdx.MAT, idx=idx)

    def name(self) -> str:
        return MatU32.NAME

    def get_context(self, nod_trm: NodeTerm) -> str:
        return 'mat'

@dataclass(eq=False)
class MatRef(Interaction):
    NAME = 'MATREF'
    def __init__(self, redex: Redex, idx: int):
        super().__init__(redex=redex, idx=idx)

    def name(self):
        return MatRef.NAME

    @classmethod
    def get_context(self, nod_trm: NodeTerm) -> str:
        return 'matref'
