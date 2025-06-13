from collections import deque
import sys

from hvm import *

import os
import sys
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'proto'))
sys.path.insert(0, root_dir)

from claude_position import event_loop

TermMap = dict[Term, NodeTerm]

def make_memop(seq: int, parts: list[str]) -> MemOp:
    # Extract basic fields (ignoring counter at index 0)
    tid = int(parts[1])
    itr_name = parts[2]
    op = parts[3].strip()
    lvl = int(parts[4])
    lab = 0
    
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
    print(f"No ref for loc {loc}")
    return None

@dataclass(eq=False)
class RedexBuilder:
    term_map: TermMap
    refs: list[ExpandRef]
    redexes: list[Redex] = field(default_factory=list)
    redex_map: dict[tuple[Term, Term], Redex] = field(default_factory=dict)

    def get_node_term(self, term: Term):
        if term not in self.term_map:
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
        else:
            return self.term_map[term]

    def push(self, neg_op: MemOp, pos_op: MemOp, ref: ExpandRef):
        redex = Redex(self.get_node_term(neg_op.put), self.get_node_term(pos_op.put)) #, ref)
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
    refs: list[ExpandRef]
    ref: Optional[ExpandRef] = None

    def add_node_term(self, node_term: NodeTerm):
        if not node_term.term.has_loc(): return
        assert not node_term.term in self.term_map
        self.term_map[node_term.term] = node_term

    def done(self):
        if self.ref:
            assert self.ref.nodes
            print(f"done, ref {self.ref.def_idx} {self.ref.redex}")
            self.ref = None
            
    def new(self, redex: Redex, loc: Optional[int] = None):
        assert not self.ref
        if not loc: loc = redex.pos.loc
        self.ref = AppRef(loc, redex)
        self.refs.append(self.ref)
        print(f"new {redex.neg.tag}{redex.pos.tag} def_idx: {loc}")

    def add(self, fst: MemOp, snd: MemOp):
        # TODO move conditional out of builder, into parse loop?
        #assert is_node_store(fst) and is_node_store(snd)
        if not self.ref:
            assert fst.is_root_itr() and snd.is_root_itr() and fst.put.tag == 'REF'
            self.ref = AppRef(fst.put.loc, None)
            self.refs.append(self.ref)

        print(f"adding node: {fst.put} {snd.put} @ {fst.loc}")
        neg = NodeTerm(fst.put, stores=[fst])
        pos = NodeTerm(snd.put, stores=[snd])
        node = Node(neg, pos, self.ref)
        neg.node = node;
        pos.node = node;

        self.ref.nodes.append(node)
        print(f"added node: {len(self.ref.nodes)}")

        self.add_node_term(neg)
        self.add_node_term(pos)

@dataclass(eq=False)
class ItrBuilder:
    term_map: TermMap
    refs: list[ExpandRef]
    itr: Optional[Interaction] = None
    itrs: list[Interaction] = field(default_factory=list)

    def make_itr(self, itr_name: str, redex: Redex):
        match itr_name:
            case AppLam.NAME: return AppLam(redex)
            case MatRef.NAME: return MatRef(redex)
            case MatNum.NAME: return MatNum(redex)
            case OpxNum.NAME: return OpxNum(redex)
            case OpyNum.NAME: return OpyNum(redex)
            case DupNum.NAME: return DupNum(redex)
            case _: raise RuntimeError(f"{redex.itr_name}")

    def new(self, redex: Redex, itr_name: str):
        assert not self.itr
        self.itr = self.make_itr(itr_name, redex)
        self.itrs.append(self.itr)
        print(f"new {redex.neg.tag}{redex.pos.tag} itr")

    def add(self, mem_op: MemOp):
        if mem_op.got and mem_op.got.has_loc():
            node_term = self.term_map[mem_op.got]
            node_term.loads.append(mem_op)
        if mem_op.put and mem_op.put.has_loc():
            # sometimes we materialize a new term out of thin air, e.g. matnum VAR;
            # now's a good time to add it to the term_map
            if not mem_op.put in self.term_map:
                node = NodeProxy(ref_from_loc(self.refs, mem_op.put.loc))
                node_term = NodeTerm(mem_op.put, node=node, stores=[mem_op])
                self.term_map[mem_op.put] = node_term
            else:
                node_term = self.term_map[mem_op.put]
                node_term.stores.append(mem_op)

    def done(self):
        if self.itr:
            #assert self.itr.memops
            print(f"done, itr {self.itr.NAME} {self.itr.redex} ops {len(self.itr.memops)}")
            self.itr = None


def parse_log_file(file_content: str) -> (list[MemOp], list[Redex], list[ExpandRef]):
    mem_ops = []
    lines = file_content.strip().split('\n')
    for line in lines:
        if not line.strip():
            continue
        parts = line.split(',')
        assert len(parts) >= 7
        mem_op = make_memop(len(mem_ops), parts)
        mem_ops.append(mem_op)

    term_map: TermMap = {}
    refs: list[ExpandRef] = []

    redex_bldr = RedexBuilder(term_map, refs)
    ref_bldr = RefBuilder(term_map, refs)
    itr_bldr = ItrBuilder(term_map, refs)
    last_popped: Optional[Redex] = None
    
    ops_que = deque(mem_ops)
    
    while ops_que:
        fst = ops_que.popleft()
        if is_node_store(fst):
            snd = ops_que.popleft()
            ref_bldr.add(fst, snd)
            continue

        if is_redex_push(fst):
            snd = ops_que.popleft()
            redex_bldr.push(fst, snd, ref_bldr.ref)
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
            last_popped = redex
            if fst.is_appref_itr():
                ref_bldr.new(redex)
            else:
                itr_bldr.new(redex, fst.itr_name)
            continue

        print(f"{fst}")

        # if a MATNUM is STORing a NUM, it is a new node it has created
        if fst.is_matnum_itr() and fst.op == 'STOR' and fst.put.has_num_tag():
            snd = ops_que.popleft()
            ref_bldr.new(last_popped, DefIdx.MAT + last_popped.neg.loc)
            ref_bldr.add(fst, snd)
            ref_bldr.done()
            continue

        # at this point, it should just a "normal" memory operation, i.e., the
        # "meat" of an interaction.
        itr_bldr.add(fst)

    return (mem_ops, redex_bldr.redexes, refs, itr_bldr.itrs)

def parse_log_from_file(filename: str):
    try:
        with open(filename, 'r') as f:
            return parse_log_file(f.read())
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
    except Exception as e:
        print(f"Error parsing file: {e}")
        import traceback
        traceback.print_exc()

    return ([], [], [], [])

def sum_nodes(refs: list[ExpandRef]) -> int:
    return sum(len(a.nodes) for a in refs)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        printf(f"usage: parse <filename>")
        sys.exit(1)
        
    filename = sys.argv[1]
    (mem_ops, redexes, refs, itrs) = parse_log_from_file(filename)
    if not mem_ops:
        print(f"No memory operations loaded")
        sys.exit(1)

    print(f"mem_ops {len(mem_ops)} itrs {len(itrs)} refs {len(refs)} nodes {sum_nodes(refs)} redexes {len(redexes)}")
    print(f"{[ref.def_idx for ref in refs]}")
    print(f"ref.def_idx < 7 or >= 1024: {sum(1 for ref in refs if ref.def_idx < 7 or ref.def_idx >= DefIdx.MAT)}")
    event_loop([ref for ref in refs if ref.def_idx < 7 or ref.def_idx >= DefIdx.MAT])
    #for op in mem_ops:
    #print(op)
