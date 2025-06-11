from collections import deque
import sys

from hvm import *

def get_memop(seq: int, parts: list[str]) -> MemOp:
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

def redex_lookup(neg: Term) -> Redex:
    return None

@dataclass
class RedexBuilder:
    redexes: list[Redex] = field(default_factory=list)

    def add(self, neg: Term, pos: Term, app_ref: AppRef):
        redex = Redex(neg, pos, app_ref)
        self.redexes.append(redex)

@dataclass
class AppRefBuilder:
    app_refs: list[AppRef] = field(default_factory=list)
    app_ref: Optional[AppRef] = None

    def root_itr(self, fst: MemOp, snd: MemOp):
        return fst.itr == '______' and snd.itr == fst.itr

    def appref_itr(self, fst: MemOp, snd: MemOp):
        return fst.itr == 'APPREF' and snd.itr == fst.itr

    def validate(self, fst: MemOp, snd: MemOp):
        #print(f"fst {fst}, snd {snd}")
        assert fst.put and snd.put
        assert fst.op == 'STOR' and snd.op == fst.op
        assert self.root_itr(fst, snd) or self.appref_itr(fst, snd)
            
    def new(self, loc: int):
        assert self.app_ref
        self.app_refs.append(self.app_ref)
        self.app_ref = AppRef(loc)

    def add(self, fst: MemOp, snd: MemOp):
        self.validate(fst, snd)
        if not self.app_ref:
            assert self.root_itr(fst, snd) and fst.put.tag == 'REF'
            self.app_ref = AppRef(fst.put.loc)

        neg = NodeTerm(fst.put)
        neg.stores.append(fst)

        pos = NodeTerm(snd.put)
        pos.stores.append(snd)

        node = Node(fst.loc, neg, pos, self.app_ref)
        self.app_ref.nodes.append(node)


def parse_log_file(file_content: str) -> (list[MemOp], list[Redex], list[AppRef]):
    """Parse log file content into a list of MemOp objects."""
    mem_ops: list[str] = []
    lines = file_content.strip().split('\n')
    for line in lines:
        if not line.strip():
            continue
        parts = line.split(',')
        assert len(parts) >= 7
        mem_op = get_memop(len(mem_ops), parts)
        mem_ops.append(mem_op)

    ops_que: deque[str] = deque(mem_ops)

    redex_bldr = RedexBuilder()
    appref_bldr = AppRefBuilder()
    
    while ops_que:
        fst = ops_que.popleft()
        snd = ops_que.popleft()
        if fst.op == 'STOR' and (fst.itr == 'APPREF' or fst.itr == '______'):
            if (fst.loc < 100000):
                appref_bldr.add(fst, snd)
            else:
                redex_bldr.add(fst.put, snd.put, appref_bldr.app_ref)
    
        if fst.op == 'POP':
            #print(f"fst.got {fst.got} snd.got {snd.got}")
            redex = Redex(fst.got, snd.got)
            if redex.is_appref():
                appref_bldr.new(snd.got.loc)

    return (mem_ops, redex_bldr.redexes, appref_bldr.app_refs)

def parse_log_from_file(filename: str): #-> List[MemOp]:
    """Parse log file from disk."""
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

# Example usage:
if __name__ == "__main__":
    # Check if filename provided as command line argument
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
    #for op in mem_ops:
    #print(op)
