from collections import deque
import traceback
import sys

from hvm import *
from vis import event_loop

TermMap = dict[Term, NodeTerm]

def make_memop(seq: int, parts: list[str]) -> MemOp:
    # Extract basic fields (ignoring counter at index 0)
    tid = int(parts[1])
    itr_name = parts[2]
    op = parts[3].strip()
    lvl = int(parts[4])
    #lab = 0

    # Parse terms based on operation type
    if op == 'STOR':
        # STOR: put term only
        put_tag = parts[5]
        put_loc = int(parts[6])
        put = Term(put_tag, 0, put_loc)
        got = None
        loc = int(parts[7])

    elif op.strip() == 'POP':
        # POP: got term only
        got_tag = parts[5]
        got_loc = int(parts[6])
        got = Term(got_tag, 0, got_loc)
        put = None
        loc = int(parts[7])

    elif op == 'EXCH':
        # EXCH format: counter,thread,itr_type,EXCH,lvl,got_tag,got_loc,put_tag,put_loc,loc
        got_tag = parts[5]
        got_loc = int(parts[6])
        got = Term(got_tag, 0, got_loc)

        put_tag = parts[7]
        put_loc = int(parts[8])
        put = Term(put_tag, 0, put_loc)

        loc = int(parts[9])

    return MemOp(
        seq=seq,
        tid=tid,
        itr_name=itr_name,
        op=op,
        lvl=lvl,
        put=put,
        got=got,
        loc=loc
    )

def is_redex_push(mem_op: MemOp) -> bool:
    # Arbitrary limit here will bite me eventually
    # only works with TPC = 1. more threads means node address may be larger.
    # should add "PUSH" op type
    return (
        mem_op.op == 'STOR' and
        mem_op.loc > 100000
    )

def is_node_store(mem_op: MemOp) -> bool:
    return (
        mem_op.op == 'STOR' and
        (mem_op.is_root_itr() or mem_op.is_appref_itr()) and
        not is_redex_push(mem_op)
    )

def ref_from_loc(refs: list[ExpandRef], loc: int):
    for ref in refs:
        if ref.contains(loc):
            return ref
    print(f"No ref for loc {loc} len(refs) {len(refs)}")
    
    return None

def node_from_loc(refs: list[ExpandRef], loc: int):
    ref = ref_from_loc(refs, loc)
    if not ref: return None
    for node in ref.nodes:
        node_loc = node.neg.mem_loc
        if loc in (node_loc, node_loc + 1):
            return node
    print(f"No node for loc {loc} len(ref.nodes) {len(ref.nodes)}")
    return None

@dataclass(eq=False)
class RedexBuilder:
    term_map: TermMap
    refs: list[ExpandRef]
    redexes: list[Redex] = field(default_factory=list)
    redex_map: dict[tuple[Term, Term], Redex] = field(default_factory=dict)

    def get_node_term(self, term: Term):
        if term in self.term_map:
            return self.term_map[term]
        else:
            if term.has_loc():
                # Term with loc *should* be in term_map, but isn't yet - add it
                node = NodeProxy(ref_from_loc(self.refs, term.loc))
                node_term = NodeTerm(term, node=node)
                self.term_map[term] = node_term
            else:
                # Term with without loc should *not* be in term_map, just wrap
                # it in a NodeTerm for convenience
                node_term = NodeTerm(term)
            return node_term

    def push(self, neg_op: MemOp, pos_op: MemOp, itr: Interaction):
        #redex = Redex(self.get_node_term(neg_op.put), self.get_node_term(pos_op.put)) #, ref)
        redex = Redex(neg_op.put, pos_op.put, itr)
        self.redexes.append(redex)
        #print(f"push {redex.neg} {redex.pos}")
        if neg_op.put.has_loc() or pos_op.put.has_loc():
            # this is OK, but using NodeTerms in tuple might provide better
            # validation, and faster hash
            key = (neg_op.put, pos_op.put)
            if key in self.redex_map:
                print(f"key in map: {key}")
            assert key not in self.redex_map
            self.redex_map[key] = redex

    def pop(self, neg_op: MemOp, pos_op: MemOp) -> Redex:
        # this is basically a way of ignoring ERA~REFs
        if neg_op.got.has_loc() or pos_op.got.has_loc():
            popped = self.redex_map[(neg_op.got, pos_op.got)]
            print(f"popped {popped}")
            return popped
        else:
            print(f"popped -None-")
            return None

@dataclass(eq=False)
class RefBuilder:
    term_map: TermMap
    itrs: list[Interaction]
    refs: list[ExpandRef]
    ref: Optional[ExpandRef] = None

    def add_node_term(self, node_term: NodeTerm):
        if not node_term.term.has_loc(): return
        assert not node_term.term in self.term_map
        self.term_map[node_term.term] = node_term

    # total hack
    def hijack(self, ref: ExpandRef, add_ref: bool = True):
        self.ref = ref
        if add_ref:
            self.refs.append(ref)

    def done(self):
        if self.ref:
            assert self.ref.nodes
            print(f"done, ref {self.ref.def_idx} {self.ref.redex}")
            self.ref = None

    def new(self, redex: Redex, loc: Optional[int] = None):
        assert not self.ref
        if not loc: loc = redex.pos.loc
        self.ref = AppRef(loc, redex, len(self.itrs))
        self.refs.append(self.ref)
        self.itrs.append(self.ref)
        print(f"new {redex.neg.tag}{redex.pos.tag} def_idx: {loc}")

    def add(self, fst: MemOp, snd: MemOp):
        # TODO move conditional out of builder, into parse loop?
        #assert is_node_store(fst) and is_node_store(snd)
        if not self.ref:
            assert fst.is_root_itr() and snd.is_root_itr() and fst.put.tag == 'REF'
            self.ref = AppRef(fst.put.loc, None, len(self.itrs))
            self.refs.append(self.ref)
            self.itrs.append(self.ref)

        print(f"adding node: {fst.put} {snd.put} @ {fst.loc}")
        neg = NodeTerm(fst.put, memops=[fst])
        pos = NodeTerm(snd.put, memops=[snd])
        node = Node(neg, pos, self.ref)
        neg.node = node
        pos.node = node

        self.ref.nodes.append(node)
        print(f"added node: {len(self.ref.nodes)}")

        self.add_node_term(neg)
        self.add_node_term(pos)

@dataclass(eq=False)
class ItrBuilder:
    term_map: TermMap
    itrs: list[Interaction]
    refs: list[ExpandRef]
    itr: Optional[Interaction] = None

    def make_itr(self, itr_name: str, redex: Redex):
        match itr_name:
            case AppLam.NAME: return AppLam(redex, len(self.itrs))
            case MatRef.NAME: return MatRef(redex, len(self.itrs))
            case MatNum.NAME: return MatNum(redex, len(self.itrs))
            case OpxNum.NAME: return OpxNum(redex, len(self.itrs))
            case OpyNum.NAME: return OpyNum(redex, len(self.itrs))
            case DupNum.NAME: return DupNum(redex, len(self.itrs))
            case _: raise RuntimeError(f"{redex.itr_name}")

    def new(self, redex: Redex, itr_name: str):
        assert not self.itr
        self.itr = self.make_itr(itr_name, redex)
        self.itrs.append(self.itr)
        print(f"new {redex.neg.tag}{redex.pos.tag} itr")

    def add(self, memop: MemOp):
        assert self.itr
        if memop.got and memop.got.has_loc():
            node_term = self.term_map[memop.got]
            node_term.loads.append(memop)
        if memop.put and memop.put.has_loc():
            # sometimes a new term is materialized out of thin air, e.g. VAR
            # in matnum; now is a good time to add it to the term_map
            if not memop.put in self.term_map:
                node = NodeProxy(ref_from_loc(self.refs, memop.put.loc))
                node_term = NodeTerm(memop.put, node=node, memops=[memop])
                self.term_map[memop.put] = node_term
            #else:
            #    node_term = self.term_map[memop.put]
            #    node_term.stores.append(memop)

        node = node_from_loc(self.refs, memop.loc)
        memop.node = node
        memop.itr = self.itr
        node_term = node.get(memop.loc)
        node_term.memops.append(memop)
        self.itr.memops.append(memop)

    def done(self):
        if self.itr:
            #assert self.itr.memops
            print(f"done, itr {self.itr.name()} {self.itr.redex} ops {len(self.itr.memops)}")
            self.itr = None

def parse_log_file(file_content: str) -> (list[MemOp], list[Redex],
                                          list[ExpandRef], list[Interaction]):
    memops = []
    lines = file_content.strip().split('\n')
    for line in lines:
        if not line.strip():
            continue
        parts = line.split(',')
        assert len(parts) >= 7
        memop = make_memop(len(memops), parts)
        memops.append(memop)

    term_map: TermMap = {}
    itrs: list[Interaction] = []
    refs: list[ExpandRef] = []

    redex_bldr = RedexBuilder(term_map, refs)
    ref_bldr = RefBuilder(term_map, itrs, refs)
    itr_bldr = ItrBuilder(term_map, itrs, refs)

    ops_que = deque(memops)

    while ops_que:
        fst = ops_que.popleft()
        if is_node_store(fst):
            snd = ops_que.popleft()
            ref_bldr.add(fst, snd)
            continue

        if is_redex_push(fst):
            snd = ops_que.popleft()
            itr = ref_bldr.ref if ref_bldr.ref else itr_bldr.itr
            assert itr
            redex_bldr.push(fst, snd, itr)
            continue

        # can i move this above is_redex_push()?
        # or peek into queue to see if next is also a node_stor?
        # and while fst and is_node_store(fst): above
        ref_bldr.done()

        # TODO: is_redex_pop(fst)
        if fst.op == 'POP':
            itr_bldr.done()
            snd = ops_que.popleft()
            assert fst.itr_name == snd.itr_name
            redex = redex_bldr.pop(fst, snd)
            if not redex: continue
            if fst.is_appref_itr():
                ref_bldr.new(redex)
            else:
                itr_bldr.new(redex, fst.itr_name)
            continue

        print(f"{fst}")

        # if a MATNUM is STORing a NUM, it is a new node it has created
        if fst.is_matnum_itr() and fst.op == 'STOR' and fst.put.has_num_tag():
            snd = ops_que.popleft()
            #ref_bldr.new(last_popped, DefIdx.MAT + last_popped.neg.loc)
            itr_bldr.itr.def_idx = DefIdx.MAT + fst.loc
            ref_bldr.hijack(itr_bldr.itr)
            ref_bldr.add(fst, snd)
            ref_bldr.done()
            continue

        # at this point, it should just a "normal" memory operation, i.e., the
        # "meat" of an interaction.
        itr_bldr.add(fst)

    return (memops, redex_bldr.redexes, refs, itr_bldr.itrs)

def parse_log_from_file(filename: str):
    try:
        with open(filename, 'r') as f:
            return parse_log_file(f.read())
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
    except Exception as e:
        print(f"Error parsing file: {e}")
        traceback.print_exc()

    return ([], [], [], [])

def sum_nodes(refs: list[ExpandRef]) -> int:
    return sum(len(a.nodes) for a in refs)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"usage: parse <filename>")
        sys.exit(1)

    the_filename = sys.argv[1]
    (all_memops, redexes, all_refs, all_itrs) = parse_log_from_file(the_filename)
    if not all_memops:
        print(f"No memory operations loaded")
        sys.exit(1)

    print(f"memops {len(all_memops)} itrs {len(all_itrs)} refs {len(all_refs)} nodes {sum_nodes(all_refs)} redexes {len(redexes)}")
    print(f"{[ref.def_idx for ref in all_refs]}")
    print(f"ref.def_idx < 7 or >= 1024: {sum(1 for ref in all_refs if ref.def_idx < 7 or ref.def_idx >= DefIdx.MAT)}")
    #event_loop([ref for ref in refs if ref.def_idx < 7 or ref.def_idx >= DefIdx.MAT])
    event_loop(all_itrs)
