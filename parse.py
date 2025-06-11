from collections import deque
import sys

from hvm import *

import os
import sys
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'proto'))
sys.path.insert(0, root_dir)

from claude_position import event_loop

def make_memop(seq: int, parts: list[str]) -> MemOp:
    # Extract basic fields (ignoring counter at index 0)
    tid = int(parts[1])
    itr = parts[2]
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
        itr=itr,
        op=op,
        lvl=lvl,
        put=put,
        got=got,
        loc=loc
    )

def is_root_itr(mem_op: MemOp):
    return mem_op.itr == '______'

def is_root_or_appref_itr(mem_op: MemOp):
    return is_root_itr(mem_op) or mem_op.itr == 'APPREF'

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
        is_root_or_appref_itr(mem_op) and
        not is_redex_push(mem_op)
    )

@dataclass(eq=False)
class RedexBuilder:
    redexes: list[Redex] = field(default_factory=list)
    redex_map: dict[tuple[Term, Term], Redex] = field(default_factory=dict)

    def push(self, neg: Term, pos: Term, app_ref: AppRef):
        assert neg and pos
        redex = Redex(neg, pos, app_ref)
        self.redexes.append(redex)
        #print(f"push {redex.neg} {redex.pos}")
        self.redex_map[(neg, pos)] = redex

    def pop(self, neg: Term, pos: Term) -> Redex:
        assert neg and pos
        return self.redex_map[(neg, pos)]
        
@dataclass(eq=False)
class AppRefBuilder:
    app_refs: list[AppRef] = field(default_factory=list)
    app_ref: Optional[AppRef] = None

    def validate(self, fst: MemOp, snd: MemOp):
        return is_node_store(fst) and is_node_store(snd)
            
    def done(self):
        if self.app_ref:
            assert self.app_ref.nodes
            self.app_refs.append(self.app_ref)
            self.app_ref = None
            #print(f"done, appref=None")
            
    def new(self, redex: Redex):
        assert redex.is_appref()
        assert not self.app_ref
        self.app_ref = AppRef(redex.pos.loc, redex)
        #print(f"new ref: {redex.pos.loc}")

    def add(self, fst: MemOp, snd: MemOp):
        self.validate(fst, snd)
        if not self.app_ref:
            assert is_root_itr(fst) and is_root_itr(snd) and fst.put.tag == 'REF'
            self.app_ref = AppRef(fst.put.loc)

        neg = NodeTerm(fst.put, stores=[fst])
        pos = NodeTerm(snd.put, stores=[snd])
        node = Node(fst.loc, neg, pos, self.app_ref)
        neg.node = node;
        pos.node = node;
        self.app_ref.nodes.append(node)
        #print(f"add node: {len(self.app_ref.nodes)}")

def parse_log_file(file_content: str) -> (list[MemOp], list[Redex], list[AppRef]):
    """Parse log file content into a list of MemOp objects."""
    mem_ops = []
    lines = file_content.strip().split('\n')
    for line in lines:
        if not line.strip():
            continue
        parts = line.split(',')
        assert len(parts) >= 7
        mem_op = make_memop(len(mem_ops), parts)
        mem_ops.append(mem_op)

    redex_bldr = RedexBuilder()
    appref_bldr = AppRefBuilder()
    
    ops_que = deque(mem_ops)
    
    while ops_que:
        fst = ops_que.popleft()
        if is_node_store(fst):
            snd = ops_que.popleft()
            appref_bldr.add(fst, snd)
            continue

        if is_redex_push(fst):
            snd = ops_que.popleft()
            redex_bldr.push(fst.put, snd.put, appref_bldr.app_ref)
            continue

        appref_bldr.done()
        
        if fst.op == 'POP':
            snd = ops_que.popleft()
            redex = redex_bldr.pop(fst.got, snd.got)
            if redex.is_appref():
                appref_bldr.new(redex)

    return (mem_ops, redex_bldr.redexes, appref_bldr.app_refs)

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

    return ([], [], [])

def sum_nodes(app_refs: list[AppRef]) -> int:
    return sum(len(a.nodes) for a in app_refs)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        printf(f"usage: parse <filename>")
        sys.exit(1)
        
    filename = sys.argv[1]
    (mem_ops, redexes, app_refs) = parse_log_from_file(filename)
    if not mem_ops:
        print(f"No memory operations loaded")
        sys.exit(1)

    print(f"mem_ops: {len(mem_ops)} app_refs: {len(app_refs)} nodes: {sum_nodes(app_refs)} redexes: {len(redexes)}")
    print(f"{[a.ref for a in app_refs]}")
    print(f"apprefs < 7: {sum(1 for a in app_refs if a.ref < 7)}")
    event_loop([app_ref for app_ref in app_refs if app_ref.ref < 7])
    #for op in mem_ops:
    #print(op)
