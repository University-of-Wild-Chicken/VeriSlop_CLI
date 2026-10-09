"""Deterministic algorithm benchmark tasks; this module never calls an LLM.

Reference implementations and hidden cases are benchmark-side data and must not
be included in candidate prompts.  Hand-written anchors are checked before any
cases are emitted.  All arithmetic is exact and all generators use local seeds.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
from functools import lru_cache
import heapq
import itertools
import json
import math
import random


def _a01(d):
    jobs = d["jobs"]
    best = (0, ())
    for mask in range(1 << len(jobs)):
        ids = tuple(i for i in range(len(jobs)) if mask >> i & 1)
        ordered = sorted(ids, key=lambda i: (jobs[i][0], jobs[i][1], i))
        if any(jobs[a][1] > jobs[b][0] for a, b in zip(ordered, ordered[1:])):
            continue
        score = sum(jobs[i][2] for i in ids)
        if score > best[0] or score == best[0] and ids < best[1]:
            best = score, ids
    return {"value": best[0], "indices": list(best[1])}


def _a02(d):
    a, b = d["source"], d["target"]
    costs = d["costs"]
    @lru_cache(None)
    def go(i, j):
        if i == len(a): return (len(b)-j)*costs["insert"]
        if j == len(b): return (len(a)-i)*costs["delete"]
        v = min(costs["delete"]+go(i+1,j), costs["insert"]+go(i,j+1),
                (0 if a[i] == b[j] else costs["replace"])+go(i+1,j+1))
        if i+1 < len(a) and j+1 < len(b) and a[i] == b[j+1] and a[i+1] == b[j]:
            v = min(v, costs["transpose"]+go(i+2,j+2))
        return v
    return go(0,0)


def _a03(d):
    a,b=d["a"],d["b"]
    op,ext,mis=d["open"],d["extend"],d["mismatch"]
    @lru_cache(None)
    def go(i,j,state):
        if i==len(a) and j==len(b): return 0
        out=[]
        if i<len(a) and j<len(b): out.append((0 if a[i]==b[j] else mis)+go(i+1,j+1,0))
        if i<len(a): out.append((ext if state==1 else op)+go(i+1,j,1))
        if j<len(b): out.append((ext if state==2 else op)+go(i,j+1,2))
        return min(out)
    return go(0,0,0)


def _a04(d):
    a=d["values"]; lo,hi=d["min_length"],d["max_length"]
    choices=[(sum(a[i:j]),i,j) for i in range(len(a)) for j in range(i+lo,min(len(a),i+hi)+1)]
    if not choices: return None
    score,i,j=min(choices,key=lambda x:(-x[0],x[1],x[2]))
    return {"sum":score,"start":i,"end":j}


def _a05(d):
    strings=sorted(set(d["strings"]))
    strings=[s for s in strings if not any(s!=t and s in t for t in strings)]
    if not strings:return ""
    def combine(a,b):
        for n in range(min(len(a),len(b)),-1,-1):
            if a.endswith(b[:n]):return a+b[n:]
    out=[]
    for p in itertools.permutations(strings):
        cur=p[0]
        for s in p[1:]:cur=combine(cur,s)
        out.append(cur)
    return min(out,key=lambda s:(len(s),s))


def _a06(d):
    coins=d["coins"]; target=d["target"]
    candidates=[]
    for counts in itertools.product(*(range(c[1]+1) for c in coins)):
        if sum(n*c[0] for n,c in zip(counts,coins))==target:
            candidates.append((sum(counts),counts))
    if not candidates:return None
    n,counts=min(candidates)
    return {"count":n,"counts":list(counts)}


def _a07(d):
    a=d["values"]; out=[]
    for mask in range(1<<len(a)):
        ids=tuple(i for i in range(len(a)) if mask>>i&1)
        vals=tuple(a[i] for i in ids)
        if all(x<y for x,y in zip(vals,vals[1:])):out.append((ids,vals))
    ids,vals=min(out,key=lambda p:(-len(p[0]),p[1],p[0]))
    return {"values":list(vals),"indices":list(ids)}


def _a08(d):
    n=d["n"]; allowed={tuple(x) for x in d["pairs"]}
    @lru_cache(None)
    def go(lo,hi):
        if lo>=hi:return ()
        candidates=[go(lo+1,hi)]
        for k in range(lo+1,hi):
            if (lo,k) in allowed:
                candidates.append(((lo,k),)+go(lo+1,k)+go(k+1,hi))
        return min(candidates,key=lambda p:(-len(p),p))
    pairs=go(0,n)
    return {"count":len(pairs),"pairs":[list(p) for p in pairs]}


def _a09(d):
    dims=d["dimensions"]; n=len(dims)-1
    @lru_cache(None)
    def go(i,j):
        if i==j:return 0,f"A{i}"
        choices=[]
        for k in range(i,j):
            x,a=go(i,k);y,b=go(k+1,j)
            choices.append((x+y+dims[i]*dims[k+1]*dims[j+1],f"({a}*{b})"))
        return min(choices)
    cost,expr=go(0,n-1)
    return {"cost":cost,"expression":expr}


def _a10(d):
    items=d["items"]; cap=d["capacity"]; out=[]
    for mask in range(1<<len(items)):
        ids=tuple(i for i in range(len(items)) if mask>>i&1)
        weight=sum(items[i][0] for i in ids)
        if weight<=cap:out.append((sum(items[i][1] for i in ids),weight,ids))
    value,weight,ids=min(out,key=lambda x:(-x[0],x[1],x[2]))
    return {"value":value,"weight":weight,"indices":list(ids)}


def _a11(d):
    a=d["values"]; total=sum(a); out=[]
    for mask in range(1<<len(a)):
        ids=tuple(i for i in range(len(a)) if mask>>i&1)
        out.append((abs(total-2*sum(a[i] for i in ids)),ids))
    diff,ids=min(out)
    return {"difference":diff,"left_indices":list(ids)}


def _a12(d):
    h=d["heights"];n=len(h)
    if n==0:return {"area":0,"start":0,"width":0,"height":0}
    out=[]
    for i in range(n):
        low=None
        for w in range(1,n+1):
            low=h[(i+w-1)%n] if low is None else min(low,h[(i+w-1)%n])
            out.append((low*w,i,w,low))
    area,start,width,height=min(out,key=lambda x:(-x[0],x[1],x[2]))
    return {"area":area,"start":start,"width":width,"height":height}


def _a13(d):
    intervals=d["intervals"]
    if not intervals:return []
    universe=sorted(set(x for p in intervals for x in p))
    # An optimal lexicographically smallest solution can use a left endpoint:
    # shift each point left until the maximum left endpoint it must cover.
    for k in range(1,len(universe)+1):
        for points in itertools.combinations(universe,k):
            if all(any(a<=x<=b for x in points) for a,b in intervals):return list(points)


def _a14(d):
    rs=d["rectangles"]
    xs=sorted({x for x,_,u,_ in rs}|{u for x,_,u,_ in rs})
    ys=sorted({y for _,y,_,v in rs}|{v for _,y,_,v in rs})
    return sum((b-a)*(v-u) for a,b in zip(xs,xs[1:]) for u,v in zip(ys,ys[1:])
               if any(x<=a and b<=z and y<=u and v<=w for x,y,z,w in rs))


def _a15(d):
    bs=d["buildings"];xs=sorted({x for a,b,h in bs for x in (a,b)})
    out=[];last=0
    for x in xs:
        height=max([h for a,b,h in bs if a<=x<b]+[0])
        if height!=last:out.append([x,height]);last=height
    return out


def _a16(d):
    intervals=d["intervals"];xs=sorted({x for p in intervals for x in p})
    cells=[(a,b,sum(lo<=a<hi for lo,hi in intervals)) for a,b in zip(xs,xs[1:])]
    top=max([v for a,b,v in cells]+[0]);out=[]
    if top==0:return {"overlap":0,"segments":[]}
    for a,b,v in cells:
        if v!=top:continue
        if out and out[-1][1]==a:out[-1][1]=b
        else:out.append([a,b])
    return {"overlap":top,"segments":out}


def _a17(d):
    a=list(d["values"]);m=d["modulus"];a=[x%m for x in a];answers=[]
    for op in d["operations"]:
        if op[0]=="affine":
            _,lo,hi,p,q=op
            for i in range(lo,hi):a[i]=(p*a[i]+q)%m
        else:
            _,lo,hi=op;answers.append(sum(a[lo:hi])%m)
    return {"answers":answers,"final":a}


def _a18(d):
    active={};out=[]
    for op in d["operations"]:
        if op[0]=="add":active[op[1]]=op[2]
        elif op[0]=="remove":active.pop(op[1],None)
        else:
            a=sorted(active.values());n=len(a)
            if not n:out.append(None)
            else:
                x=Fraction(a[n//2]) if n%2 else Fraction(a[n//2-1]+a[n//2],2)
                out.append([x.numerator,x.denominator])
    return out


def _a19(d):
    events=d["events"]
    out=[]
    for end,width,k in d["queries"]:
        count=Counter(key for t,key in events if end-width<t<=end)
        ranked=sorted(count.items(),key=lambda kv:(-kv[1],kv[0]))
        out.append([[key,n] for key,n in ranked[:k]])
    return out


def _a20(d):
    word=d["word"];counts=Counter(word);rank=0
    def ways(c):
        n=sum(c.values());v=math.factorial(n)
        for x in c.values():v//=math.factorial(x)
        return v
    for ch in word:
        for low in sorted(counts):
            if low>=ch:break
            if counts[low]:counts[low]-=1;rank+=ways(counts);counts[low]+=1
        counts[ch]-=1
    return rank


def _a21(d):
    value,mod=0,1
    for rem,m in d["congruences"]:
        rem%=m;g=math.gcd(mod,m)
        if (rem-value)%g:return None
        quotient=m//g
        k=((rem-value)//g*pow(mod//g,-1,quotient))%quotient if quotient>1 else 0
        value=(value+mod*k)%(mod*quotient);mod*=quotient
    return {"residue":value,"modulus":mod}


def _a22(d):
    # Exact shunting-yard evaluator, binary operators, unary negation, parentheses.
    s=d["expression"]; tokens=[];i=0
    while i<len(s):
        if s[i].isspace():i+=1;continue
        if s[i].isdigit():
            j=i+1
            while j<len(s) and s[j].isdigit():j+=1
            tokens.append(Fraction(int(s[i:j])));i=j
        else:tokens.append(s[i]);i+=1
    values=[];ops=[];prev_operand=False;prec={"+":1,"-":1,"*":2,"/":2,"neg":3}
    def apply():
        op=ops.pop()
        if op=="neg":values.append(-values.pop());return
        b=values.pop();a=values.pop()
        if op=="+":values.append(a+b)
        elif op=="-":values.append(a-b)
        elif op=="*":values.append(a*b)
        else:values.append(a/b)
    try:
        for t in tokens:
            if isinstance(t,Fraction):values.append(t);prev_operand=True
            elif t=="(":ops.append(t);prev_operand=False
            elif t==")":
                while ops[-1]!="(":apply()
                ops.pop();prev_operand=True
            else:
                op="neg" if t=="-" and not prev_operand else t
                while ops and ops[-1]!="(" and (prec[ops[-1]]>prec[op] or prec[ops[-1]]==prec[op] and op!="neg"):apply()
                ops.append(op);prev_operand=False
        while ops:apply()
    except ZeroDivisionError:return {"error":"division_by_zero"}
    x=values[0]
    return {"numerator":x.numerator,"denominator":x.denominator}


def _a23(d):
    # Negative coefficients and arbitrarily large integers are deliberate.
    return sum((d["a"]*i+d["b"])//d["m"] for i in range(d["n"]))


def _a24(d):
    points=d["points"];lo,hi=d["bounds"]
    out=[]
    for x in range(lo,hi+1):
        for y in range(lo,hi+1):
            score=max([w*(abs(x-a)+abs(y-b)) for a,b,w in points]+[0])
            out.append((score,x,y))
    score,x,y=min(out)
    return {"cost":score,"point":[x,y]}


def _a25(d):
    c=d["costs"];n=len(c);m=len(c[0]) if n else 0;out=[]
    for cols in itertools.permutations(range(m),n):
        if all(c[i][j] is not None for i,j in enumerate(cols)):
            out.append((sum(c[i][j] for i,j in enumerate(cols)),cols))
    if not out:return None
    cost,cols=min(out)
    return {"cost":cost,"columns":list(cols)}


def _a26(d):
    jobs=d["jobs"];out=[]
    for mask in range(1<<len(jobs)):
        ids=tuple(i for i in range(len(jobs)) if mask>>i&1)
        ordered=sorted(ids,key=lambda i:(jobs[i][0],i))
        if all(slot<=jobs[i][0] for slot,i in enumerate(ordered,1)):
            out.append((sum(jobs[i][1] for i in ids),ids,ordered))
    score,ids,ordered=min(out,key=lambda x:(-x[0],x[1]))
    return {"profit":score,"indices":list(ids),"schedule":list(ordered)}


def _a27(d):
    n=d["n"];edges=set(tuple(p) for p in d["edges"]);adj=[[] for _ in range(n)];deg=[0]*n
    for a,b in edges:adj[a].append(b);deg[b]+=1
    ready=[i for i in range(n) if deg[i]==0];heapq.heapify(ready);out=[]
    while ready:
        a=heapq.heappop(ready);out.append(a)
        for b in adj[a]:
            deg[b]-=1
            if deg[b]==0:heapq.heappush(ready,b)
    if len(out)==n:return {"order":out,"cycle":None}
    # Cycles are normalized by starting at their minimum vertex. Select shortest,
    # then lexicographically smallest, including a repeated final vertex.
    cycles=[]
    for start in range(n):
        def walk(path):
            for v in adj[path[-1]]:
                if v==start:cycles.append(tuple(path+[start]))
                elif v>start and v not in path:walk(path+[v])
        walk([start])
    cycle=min(cycles,key=lambda p:(len(p),p))
    return {"order":None,"cycle":list(cycle)}


def _a28(d):
    n=d["n"];adj=[[] for _ in range(n)]
    for a,b,w in d["edges"]:adj[a].append((b,w))
    cycles=[]
    for start in range(n):
        def walk(path,cost):
            for v,w in adj[path[-1]]:
                if v==start:cycles.append((Fraction(cost+w,len(path)),tuple(path+[start])))
                elif v>start and v not in path:walk(path+[v],cost+w)
        walk([start],0)
    if not cycles:return None
    mean,path=min(cycles,key=lambda p:(p[0],len(p[1]),p[1]))
    return {"mean":[mean.numerator,mean.denominator],"cycle":list(path)}


def _a29(d):
    n=d["n"];adj=[[] for _ in range(n)]
    for a,b,w in d["edges"]:adj[a].append((b,w))
    found=[[] for _ in range(n)];queue=[(0,d["source"])]
    while queue:
        dist,u=heapq.heappop(queue)
        if dist in found[u] or len(found[u])==2:continue
        found[u].append(dist)
        for v,w in adj[u]:heapq.heappush(queue,(dist+w,v))
    return found[d["target"]][1] if len(found[d["target"]])==2 else None


def _a30(d):
    points=d["points"];out=[]
    for q in d["queries"]:
        value=Fraction(0)
        for i,(x,y) in enumerate(points):
            term=Fraction(y)
            for j,(other,_) in enumerate(points):
                if i!=j:term*=Fraction(q-other,x-other)
            value+=term
        out.append([value.numerator,value.denominator])
    return out


def _a31(d):
    l,r=d["left"],d["right"];edges=d["edges"];out=[]
    for mask in range(1<<(l+r)):
        vertices=tuple(i for i in range(l+r) if mask>>i&1)
        if all(mask>>a&1 or mask>>(l+b)&1 for a,b in edges):out.append(vertices)
    chosen=min(out,key=lambda x:(len(x),x))
    return {"left":[i for i in chosen if i<l],"right":[i-l for i in chosen if i>=l]}


def _a32(d):
    grid=[row[:] for row in d["grid"]]
    def possible(r,c,x):
        return x not in grid[r] and all(grid[i][c]!=x for i in range(4)) and all(
            grid[i][j]!=x for i in range(r//2*2,r//2*2+2) for j in range(c//2*2,c//2*2+2))
    # Given conflicts make the puzzle unsatisfiable, including a complete grid.
    for r in range(4):
        for c in range(4):
            if grid[r][c]:
                x=grid[r][c];grid[r][c]=0;ok=possible(r,c,x);grid[r][c]=x
                if not ok:return None
    def search():
        empty=[(r,c) for r in range(4) for c in range(4) if grid[r][c]==0]
        if not empty:return [row[:] for row in grid]
        r,c=empty[0]
        for x in range(1,5):
            if possible(r,c,x):
                grid[r][c]=x;result=search()
                if result is not None:return result
        grid[r][c]=0
        return None
    return search()


def _a33(d):
    n=d["n"];dist=[0]*n
    if n==0:return {"feasible":True,"potential":[]}
    for k in range(n):
        changed=False
        for a,b,c in d["constraints"]:
            if dist[b]>dist[a]+c:dist[b]=dist[a]+c;changed=True
        if not changed:return {"feasible":True,"potential":dist}
    return {"feasible":False,"potential":None}


_ORACLES = {f"A{i:02}": globals()[f"_a{i:02}"] for i in range(1,34)}


def reference(task_id, data):
    """Return the exact benchmark oracle result for one valid task input."""
    return _ORACLES[task_id](data)


_SPECS = [
 ("Weighted interval scheduling with stable identity", "dynamic_programming", "Input {jobs:[[start,end,value],...]}, at most 12 jobs, integer start<end, signed values. Select nonoverlapping half-open intervals (touching allowed), maximizing total value. The empty selection is allowed. Break ties by the lexicographically smallest ascending list of original indices (a proper prefix is smaller). Return {value,indices}."),
 ("Weighted restricted Damerau edit distance", "dynamic_programming", "Input {source,target,costs:{insert,delete,replace,transpose}}; strings over abc, lengths<=12, positive integer costs. Return the minimum edit cost for the standard optimal-string-alignment recurrence on prefixes: insert, delete, substitute (matching costs zero), or transpose two adjacent matching crossed characters, consuming two characters from both strings. This is restricted OSA distance, not unrestricted Damerau distance."),
 ("Global alignment with affine gap runs", "dynamic_programming", "Input {a,b,open,extend,mismatch}; strings over abc length<=10, positive integer costs. Align both entire strings. A matching paired character costs 0, a mismatching pair costs mismatch. A contiguous run of k deletions costs open+(k-1)*extend, likewise insertions. Switching directly from deletions to insertions starts a new run. Return minimum total cost."),
 ("Bounded-length maximum subarray", "indexing", "Input {values,min_length,max_length}, signed integers length<=80, 1<=min_length<=max_length<=100. Return null if no contiguous slice has allowed length; otherwise {sum,start,end}, with end exclusive, maximizing sum, then smallest start, then smallest end. Empty slices are never allowed."),
 ("Canonical shortest common superstring", "dynamic_programming", "Input {strings:[...]}, at most 6 strings over abc of length<=6, duplicates and empty strings allowed. Return the shortest string containing every input as a contiguous substring; break ties lexicographically by ASCII. Remove redundant contained strings before solving if desired. Return a string, including empty string for empty/all-empty inputs."),
 ("Bounded coin change with inventory tie breaking", "optimization", "Input {coins:[[positive_denomination,available_count],...],target}, at most 6 coin types, counts<=4, target>=0. Distinct types may have equal denomination. Return null if impossible, else {count,counts} with counts in input order, minimizing total number of coins, then lexicographically minimizing counts. Target zero uses zero of every type."),
 ("Canonical strictly increasing subsequence", "dynamic_programming", "Input {values:[signed integers]}, length<=14. Return {values,indices} for a longest strictly increasing subsequence. Ties first minimize the subsequence value list lexicographically, then its ascending original index list. Equal neighboring values are not increasing; empty input returns two empty lists."),
 ("Noncrossing disjoint pair optimization", "dynamic_programming", "Input {n,pairs:[[i,j],...]}, 0<=n<=12, allowed pairs satisfy 0<=i<j<n. Select the most pairs such that no index appears twice and no two pairs have i<k<j<l; nesting is allowed. Return {count,pairs} where pairs are sorted lexicographically; among maximum-cardinality choices minimize that sorted pair list lexicographically. Duplicate allowed pairs have no effect."),
 ("Exact matrix-chain optimizer", "dynamic_programming", "Input {dimensions:[d0,...,dn]}, 1<=n<=9 matrices, positive dimensions. Matrix Ai has size di by d(i+1). Return {cost,expression} for minimum scalar multiplication cost. Expression uses leaves A0,A1,... and binary form (left*right), with no spaces. Among equal-cost complete expressions select lexicographically smallest ASCII expression."),
 ("Knapsack with weight and identity priorities", "optimization", "Input {items:[[weight,value],...],capacity}, <=14 items, positive weights, signed values, nonnegative capacity. Choose any subset, including empty, to maximize total value within capacity; ties minimize total weight, then lexicographically minimize the ascending original index list. Return {value,weight,indices}."),
 ("Signed balanced partition with canonical side", "optimization", "Input {values:[signed integers]}, length<=14. Assign each item to left or right, allowing empty sides. Return {difference,left_indices}, minimizing absolute difference of side sums, then lexicographically minimizing the ascending indices on the left. The sides are labeled; do not force index zero into the left side."),
 ("Maximum circular histogram rectangle", "interval_algorithms", "Input {heights:[nonnegative integers]}, length<=80. A rectangle chooses start index and width 1..n, wraps around at most once, and height equal to the minimum covered bar. Maximize area, then smallest start, then smallest width. Return {area,start,width,height}. For no bars return {area:0,start:0,width:0,height:0}. Zero-height bars still allow width 1."),
 ("Lexicographic minimum integer interval stabbing", "interval_algorithms", "Input {intervals:[[left,right],...]}, <=8 closed integer intervals, left<=right. Return an ascending list of integer points intersecting every interval, first minimizing point count, then lexicographically minimizing the point list. Empty input returns []. Endpoints count as covered; a point can cover many intervals."),
 ("Exact union area of overlapping rectangles", "interval_algorithms", "Input {rectangles:[[x1,y1,x2,y2],...]}, <=40 axis-aligned rectangles, integer coordinates and x1<=x2,y1<=y2. Return exact integer union area. Zero-area rectangles, duplicates, negative coordinates and shared boundaries must be handled; overlapping area counts once."),
 ("Canonical skyline event stream", "interval_algorithms", "Input {buildings:[[left,right,height],...]}, <=80 buildings, left<right, positive heights. Buildings cover half-open horizontal intervals. Return skyline breakpoints [[x,new_height],...], x strictly increasing; emit only changes, consolidate simultaneous events, and include the final drop to zero. Empty input returns []."),
 ("All maximum-overlap half-open segments", "interval_algorithms", "Input {intervals:[[left,right],...]}, <=80 integer half-open intervals left<=right. Return {overlap,segments}; overlap is maximum positive-length coverage, segments are all maximal adjacent merged half-open segments attaining it, sorted by start. Empty/zero-length-only input returns overlap 0 and []. Endpoints alone have no length."),
 ("Ordered affine range transformations", "indexing", "Input {values,modulus,operations}, length<=60, modulus positive. Operation ['affine',lo,hi,p,q] applies x=(p*x+q) mod modulus on half-open indices; ['sum',lo,hi] appends range sum mod modulus. Coefficients/initial values are signed, indices valid, empty ranges allowed. Return {answers,final}; normalize all final elements into [0,modulus). Up to 100 operations; order matters."),
 ("Token-addressed mutable median stream", "stream_algorithms", "Input {operations:[...]}, <=100 ops: ['add',id,value] inserts or replaces that string ID, ['remove',id] removes if present (missing is no-op), ['median'] queries. Return one result per query: null when empty or reduced rational [numerator,positive_denominator] for conventional median, averaging the middle two for even population. Values are signed integers; IDs are independent even with equal values."),
 ("Exact trailing-window heavy-hitter index", "indexing", "Input {events:[[timestamp,key],...],queries:[[end,width,k],...]}, <=100 events, ASCII lowercase keys, nonnegative width and k. Events need not be ordered and duplicates count. For each query count keys with end-width < timestamp <= end; rank by descending count then key ascending, return top k [key,count] pairs. Return a list of these query results; zero-width windows are empty."),
 ("Exact rank of a multiset permutation", "numeric_exact", "Input {word}, an ASCII lowercase string length<=60. Return its zero-based lexicographic rank among distinct permutations of the same multiset. Repeated letters are indistinguishable; use exact arbitrary-precision integer arithmetic. Empty word has rank zero."),
 ("Generalized noncoprime Chinese remainder", "numeric_exact", "Input {congruences:[[residue,modulus],...]}, <=30 equations, positive integer moduli, signed residues. Return null for inconsistency, else {residue,modulus} describing all solutions x=residue+k*modulus with smallest nonnegative residue and modulus the least common multiple. Empty equations give residue 0, modulus 1. Modulus 1 and repeated equations are legal."),
 ("Exact rational expression evaluator", "numeric_exact", "Input {expression}, a syntactically valid expression of length<=200 using unsigned integer literals, whitespace, parentheses, binary + - * /, and unary -. Precedence: unary minus highest, then * /, then + -, binary operators left associative and chained unary minus right associative. Return reduced {numerator,denominator} with positive denominator, or {error:'division_by_zero'} if any evaluated division has zero denominator. No exponentiation, variables or implicit multiplication."),
 ("Signed arithmetic floor-sum kernel", "numeric_exact", "Input {n,m,a,b}: 0<=n<=500, m>0, a/b any signed integers (possibly magnitude 10^30). Return exact sum of floor((a*i+b)/m) for i=0..n-1. Floor means toward negative infinity, not truncation. Empty sum is zero; avoid floating point."),
 ("Weighted Manhattan minimax facility", "optimization", "Input {points:[[x,y,positive_weight],...],bounds:[lo,hi]}, <=30 points, integer lo<=hi with hi-lo<=25. Choose integer facility (x,y) with both coordinates within inclusive bounds, minimizing max(weight*(abs(x-xi)+abs(y-yi))). Return {cost,point:[x,y]}; ties minimize x then y. With no demand points cost is zero and choose [lo,lo]."),
 ("Forbidden-edge rectangular assignment", "optimization", "Input {costs:[[integer_or_null,...],...]}, 0<=rows<=7, rows<=columns<=8 (empty rows array allowed). Assign one distinct column to each row; null forbids that assignment. Return null if impossible, else {cost,columns}, minimizing summed signed cost then lexicographically minimizing column indices in row order. Empty assignment has cost 0 and columns []."),
 ("Deadline-profit scheduling with stable choice", "optimization", "Input {jobs:[[deadline,profit],...]}, <=14 unit-duration jobs, nonnegative integer deadlines and signed profits. Select jobs admitting slots 1..k no later than each deadline. Maximize total profit, then lexicographically minimize ascending selected original indices. Return {profit,indices,schedule}; schedule is selected indices sorted by (deadline,index), not a second optimization objective. Empty selection is allowed."),
 ("Deterministic topological order or shortest cycle", "graph_algorithms", "Input {n,edges:[[from,to],...]}, 0<=n<=8, vertices 0..n-1, directed edges including duplicates/self-loops. If acyclic return {order,cycle:null}, with lexicographically smallest topological order. Otherwise return {order:null,cycle}, where cycle is a simple directed cycle with first vertex repeated at end, rotated to its smallest vertex; minimize edge count then lexicographic sequence. Duplicate edges have no effect."),
 ("Exact minimum-mean directed cycle", "numeric_exact", "Input {n,edges:[[from,to,weight],...]}, 0<=n<=7, directed graph with signed integer weights and no duplicate ordered edge pair. Consider simple directed cycles including self-loops, rotated to start at their minimum vertex. Return null if no cycle, else {mean:[reduced_numerator,positive_denominator],cycle:[...,start]}; minimize exact mean, then edge count, then lexicographic cycle. Avoid floating comparisons."),
 ("Second distinct shortest walk distance", "graph_algorithms", "Input {n,edges:[[from,to,positive_weight],...],source,target}, 1<=n<=30 directed vertices, <=100 edges including parallel edges. Walks may revisit vertices. Return the second smallest DISTINCT total weight among all source-to-target walks, or null if fewer than two weights exist. When source==target the empty walk counts with weight zero; equal-cost routes do not create a second distance."),
 ("Exact rational polynomial interpolation queries", "numeric_exact", "Input {points:[[x,y],...],queries:[x,...]}, at most 8 points with distinct integer x coordinates and at most 30 integer queries; all input integers have absolute value<=10^12. Interpolate the unique polynomial of degree strictly below number of points through every point, then return its value at each query in input order as reduced [numerator,positive_denominator] fraction pairs. No floating-point interpolation or rounding. Point order is arbitrary; queries may repeat or equal point coordinates. For no points define the zero polynomial; for no queries return []."),
 ("Canonical minimum bipartite vertex cover", "constraint_solving", "Input {left,right,edges:[[left_index,right_index],...]}, left+right<=14. Find a minimum vertex cover. For ties, encode left vertices as 0..left-1 and right vertices as left..left+right-1 and minimize the ascending encoded vertex list lexicographically. Return {left:[indices],right:[indices]}, each ascending. Duplicate edges have no effect; empty edge set has empty cover."),
 ("Lexicographically first 4x4 Sudoku completion", "constraint_solving", "Input {grid}, exactly 4 rows of 4 integers 0..4; zero is blank. Complete with digits 1..4 each occurring once per row, column, and 2x2 box. Return null if unsatisfiable, including conflicting givens; otherwise return the lexicographically smallest solution when all 16 cells are compared in row-major order. Givens must be preserved."),
 ("Difference constraints canonical feasible potential", "constraint_solving", "Input {n,constraints:[[u,v,c],...]}, 0<=n<=40; each means x[v]-x[u]<=c with signed integer c. Add a virtual source with weight-zero edges to every vertex. If any negative cycle exists return {feasible:false,potential:null}. Otherwise return {feasible:true,potential:[...]}, using exact shortest-path distances from this source, not an arbitrary feasible assignment. Distances are nonpositive; isolated vertices are zero."),
]


# Two independent, manually calculated examples per task are both public.
_ANCHORS = {
 "A01":[({"jobs":[[0,2,4],[2,4,4],[0,4,8]]},{"value":8,"indices":[0,1]}),({"jobs":[[1,2,-3]]},{"value":0,"indices":[]})],
 "A02":[({"source":"ab","target":"ba","costs":{"insert":2,"delete":2,"replace":3,"transpose":1}},1),({"source":"","target":"abc","costs":{"insert":2,"delete":4,"replace":1,"transpose":1}},6)],
 "A03":[({"a":"aaa","b":"a","open":3,"extend":1,"mismatch":5},4),({"a":"a","b":"b","open":4,"extend":2,"mismatch":3},3)],
 "A04":[({"values":[-2,3,-1,3],"min_length":2,"max_length":3},{"sum":5,"start":1,"end":4}),({"values":[-1],"min_length":2,"max_length":4},None)],
 "A05":[({"strings":["ab","bc","ca"]},"abca"),({"strings":["","abc","bc","abc"]},"abc")],
 "A06":[({"coins":[[1,3],[2,2],[3,1]],"target":4},{"count":2,"counts":[0,2,0]}),({"coins":[[2,1]],"target":3},None)],
 "A07":[({"values":[3,1,2,2,4]},{"values":[1,2,4],"indices":[1,2,4]}),({"values":[2,2]},{"values":[2],"indices":[0]})],
 "A08":[({"n":4,"pairs":[[0,2],[1,3],[0,3],[1,2]]},{"count":2,"pairs":[[0,3],[1,2]]}),({"n":3,"pairs":[[0,2],[0,1]]},{"count":1,"pairs":[[0,1]]})],
 "A09":[({"dimensions":[10,20,5]},{"cost":1000,"expression":"(A0*A1)"}),({"dimensions":[2,2,2,2]},{"cost":16,"expression":"((A0*A1)*A2)"})],
 "A10":[({"items":[[2,4],[3,4],[5,8]],"capacity":5},{"value":8,"weight":5,"indices":[0,1]}),({"items":[[1,-1]],"capacity":9},{"value":0,"weight":0,"indices":[]})],
 "A11":[({"values":[1,2,3]},{"difference":0,"left_indices":[0,1]}),({"values":[-2,5]},{"difference":3,"left_indices":[]})],
 "A12":[({"heights":[5,1,5]},{"area":10,"start":2,"width":2,"height":5}),({"heights":[0,0]},{"area":0,"start":0,"width":1,"height":0})],
 "A13":[({"intervals":[[1,3],[2,4],[5,6]]},[2,5]),({"intervals":[[-2,0],[0,2]]},[0])],
 "A14":[({"rectangles":[[0,0,2,2],[1,1,3,3]]},7),({"rectangles":[[-2,-1,0,1],[0,0,0,9]]},4)],
 "A15":[({"buildings":[[0,2,3],[2,4,3],[1,3,5]]},[[0,3],[1,5],[3,3],[4,0]]),({"buildings":[]},[])],
 "A16":[({"intervals":[[0,3],[1,2],[2,4]]},{"overlap":2,"segments":[[1,3]]}),({"intervals":[[2,2]]},{"overlap":0,"segments":[]})],
 "A17":[({"values":[1,2,3],"modulus":7,"operations":[["affine",0,2,2,1],["sum",0,3],["affine",1,3,-1,0],["sum",1,3]]},{"answers":[4,6],"final":[3,2,4]}),({"values":[-1,8],"modulus":1,"operations":[["sum",0,2]]},{"answers":[0],"final":[0,0]})],
 "A18":[({"operations":[["median"],["add","a",1],["add","b",4],["median"],["add","a",7],["median"],["remove","b"],["median"]]},[None,[5,2],[11,2],[7,1]]),({"operations":[["remove","missing"],["add","x",-2],["add","y",-1],["median"]]},[[-3,2]])],
 "A19":[({"events":[[1,"b"],[2,"a"],[2,"b"],[3,"a"]],"queries":[[3,2,2],[2,1,1],[3,0,5]]},[[["a",2],["b",1]],[["a",1]],[]]),({"events":[],"queries":[[4,9,3]]},[[]])],
 "A20":[({"word":"baa"},2),({"word":""},0)],
 "A21":[({"congruences":[[2,6],[5,9]]},{"residue":14,"modulus":18}),({"congruences":[[1,2],[0,4]]},None)],
 "A22":[({"expression":"- (2 + 3) / 2 + --1"},{"numerator":-3,"denominator":2}),({"expression":"1 / (3 - 3)"},{"error":"division_by_zero"})],
 "A23":[({"n":4,"m":3,"a":-2,"b":1},-4),({"n":0,"m":7,"a":100,"b":-99},0)],
 "A24":[({"points":[[0,0,1],[2,0,1]],"bounds":[0,2]},{"cost":1,"point":[1,0]}),({"points":[],"bounds":[-2,2]},{"cost":0,"point":[-2,-2]})],
 "A25":[({"costs":[[1,1,None],[1,1,0]]},{"cost":1,"columns":[0,2]}),({"costs":[[None,None],[0,1]]},None)],
 "A26":[({"jobs":[[1,5],[1,5],[2,1]]},{"profit":6,"indices":[0,2],"schedule":[0,2]}),({"jobs":[[0,100],[1,-1]]},{"profit":0,"indices":[],"schedule":[]})],
 "A27":[({"n":3,"edges":[[0,2],[1,2]]},{"order":[0,1,2],"cycle":None}),({"n":3,"edges":[[0,1],[1,0],[2,2]]},{"order":None,"cycle":[2,2]})],
 "A28":[({"n":3,"edges":[[0,1,1],[1,0,2],[2,2,2]]},{"mean":[3,2],"cycle":[0,1,0]}),({"n":2,"edges":[[0,1,-4]]},None)],
 "A29":[({"n":3,"edges":[[0,1,1],[1,2,1],[0,2,2],[1,1,1]],"source":0,"target":2},3),({"n":1,"edges":[[0,0,4]],"source":0,"target":0},4)],
 "A30":[({"points":[[0,1],[1,4],[2,9]],"queries":[-1,3]},[[0,1],[16,1]]),({"points":[[2,1],[0,0]],"queries":[-1,1,2]},[[-1,2],[1,2],[1,1]])],
 "A31":[({"left":2,"right":2,"edges":[[0,0],[0,1],[1,1]]},{"left":[0,1],"right":[]}),({"left":1,"right":2,"edges":[[0,1]]},{"left":[0],"right":[]})],
 "A32":[({"grid":[[1,2,3,4],[3,4,1,2],[2,1,4,3],[4,3,2,0]]},[[1,2,3,4],[3,4,1,2],[2,1,4,3],[4,3,2,1]]),({"grid":[[1,1,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]},None)],
 "A33":[({"n":3,"constraints":[[0,1,-2],[1,2,1],[0,2,5]]},{"feasible":True,"potential":[0,-2,-1]}),({"n":2,"constraints":[[0,1,-1],[1,0,-1]]},{"feasible":False,"potential":None})],
}


def _generated(task_id, rng, case_index):
    """Small, adversarially varied bounded instances; no oracle-derived inputs."""
    k=case_index
    ints=lambda n,lo=-5,hi=8:[rng.randint(lo,hi) for _ in range(n)]
    text=lambda n:"".join(rng.choice("abc") for _ in range(n))
    if task_id=="A01":
        jobs=[]
        for _ in range(12 if k==9 else k%9):
            start=rng.randint(-3,8);jobs.append([start,start+rng.randint(1,5),rng.randint(-4,10)])
        return {"jobs":jobs}
    if task_id=="A02":return {"source":text(12 if k==9 else k%7),"target":text(12 if k==9 else (k*3)%8),"costs":dict(zip(("insert","delete","replace","transpose"),ints(4,1,6)))}
    if task_id=="A03":return {"a":text(10 if k==9 else k%7),"b":text(10 if k==9 else (k*3)%7),"open":rng.randint(1,7),"extend":rng.randint(1,5),"mismatch":rng.randint(1,8)}
    if task_id=="A04":return {"values":ints(80 if k==9 else k%9),"min_length":1+k%3,"max_length":80 if k==9 else 4+k%4}
    if task_id=="A05":return {"strings":[text(6 if k==9 else rng.randint(0,5)) for _ in range(6 if k==9 else k%6)]}
    if task_id=="A06":return {"coins":[[rng.randint(1,7),4 if k==9 else rng.randint(0,3)] for _ in range(6 if k==9 else k%5)],"target":47 if k==9 else rng.randint(0,24)}
    if task_id=="A07":return {"values":ints(14 if k==9 else k%12,-3,4)}
    if task_id=="A08":
        n=12 if k==9 else k%10;return {"n":n,"pairs":[[i,j] for i in range(n) for j in range(i+1,n) if rng.randrange(3)==0]}
    if task_id=="A09":return {"dimensions":ints(10 if k==9 else 2+k%6,1,12)}
    if task_id=="A10":return {"items":[[rng.randint(1,6),rng.randint(-3,9)] for _ in range(14 if k==9 else k%12)],"capacity":rng.randint(0,20)}
    if task_id=="A11":return {"values":ints(14 if k==9 else k%12,-8,8)}
    if task_id=="A12":return {"heights":ints(80 if k==9 else k%12,0,9)}
    if task_id=="A13":
        out=[]
        for _ in range(8 if k==9 else k%7):
            a=rng.randint(-4,5);out.append([a,a+rng.randint(0,5)])
        return {"intervals":out}
    if task_id=="A14":
        out=[]
        for _ in range(40 if k==9 else k%9):
            x,y=rng.randint(-4,4),rng.randint(-4,4);out.append([x,y,x+rng.randint(0,5),y+rng.randint(0,5)])
        return {"rectangles":out}
    if task_id=="A15":
        out=[]
        for _ in range(80 if k==9 else k%10):
            x=rng.randint(-4,5);out.append([x,x+rng.randint(1,5),rng.randint(1,9)])
        return {"buildings":out}
    if task_id=="A16":
        out=[]
        for _ in range(80 if k==9 else k%10):
            x=rng.randint(-4,5);out.append([x,x+rng.randint(0,5)])
        return {"intervals":out}
    if task_id=="A17":
        n=60 if k==9 else k%8;m=[1,2,7,97,10**12+39][k%5];ops=[]
        for j in range(100 if k==9 else 16):
            lo=rng.randint(0,n);hi=rng.randint(lo,n)
            ops.append(["sum",lo,hi] if j%3==0 else ["affine",lo,hi,rng.randint(-5,5),rng.randint(-7,7)])
        return {"values":ints(n,-30,30),"modulus":m,"operations":ops}
    if task_id=="A18":
        ops=[["median"]]
        for j in range(99 if k==9 else 25):
            ident=rng.choice("abcde")
            ops.append(["median"] if j%4==0 else ["remove",ident] if j%3==0 else ["add",ident,rng.randint(-9,9)])
        return {"operations":ops}
    if task_id=="A19":return {"events":[[rng.randint(-5,10),rng.choice("abcd")] for _ in range(100 if k==9 else k*3)],"queries":[[rng.randint(-5,12),rng.randint(0,8),rng.randint(0,5)] for _ in range(8)]}
    if task_id=="A20":return {"word":text([0,1,2,5,10,20,30,45,50,60][k])}
    if task_id=="A21":return {"congruences":[[rng.randint(-20,20),rng.randint(1,15)] for _ in range(30 if k==9 else k%7)]}
    if task_id=="A22":
        expressions=["0","--3","1/2+1/3","10 - 3 - 2","8 / 4 / 2","-(1 - -2)*3","(2+3)/(7-7)","- - - 5 + 2*3","999999999999999999999999/7","3/(1/(2+1))-4"]
        return {"expression":expressions[k]}
    if task_id=="A23":return {"n":[0,1,3,10,20,31,50,100,200,500][k],"m":rng.randint(1,21),"a":rng.randint(-50,50)*(10**25 if k>=8 else 1),"b":rng.randint(-50,50)*(10**24 if k>=8 else 1)}
    if task_id=="A24":return {"points":[[rng.randint(-4,4),rng.randint(-4,4),rng.randint(1,4)] for _ in range(30 if k==9 else k%8)],"bounds":[-10,15] if k==9 else [-3,3]}
    if task_id=="A25":
        n=7 if k==9 else k%5;m=8 if k==9 else n+rng.randint(0,2);return {"costs":[[None if rng.randrange(5)==0 else rng.randint(-7,9) for _ in range(m)] for _ in range(n)]}
    if task_id=="A26":return {"jobs":[[rng.randint(0,5),rng.randint(-4,9)] for _ in range(14 if k==9 else k%12)]}
    if task_id=="A27":
        n=8 if k==9 else k%8;return {"n":n,"edges":[[i,j] for i in range(n) for j in range(n) if rng.randrange(5)==0]}
    if task_id=="A28":
        n=7 if k==9 else k%7;return {"n":n,"edges":[[i,j,rng.randint(-9,9)] for i in range(n) for j in range(n) if rng.randrange(4)==0]}
    if task_id=="A29":
        n=30 if k==9 else 1+k%7;return {"n":n,"edges":[[rng.randrange(n),rng.randrange(n),rng.randint(1,7)] for _ in range(100)] if k==9 else [[i,j,rng.randint(1,7)] for i in range(n) for j in range(n) if rng.randrange(4)==0],"source":rng.randrange(n),"target":rng.randrange(n)}
    if task_id=="A30":
        n=8 if k==9 else k%8
        xs=rng.sample(range(-12,13),n)
        return {"points":[[x,rng.randint(-15,15)] for x in xs],
                "queries":xs+ints(30-n if k==9 else 4,-10**12 if k==9 else -15,10**12 if k==9 else 15)}
    if task_id=="A31":
        l,r=(7,7) if k==9 else (k%6,(k*3)%6);return {"left":l,"right":r,"edges":[[i,j] for i in range(l) for j in range(r) if rng.randrange(3)==0]}
    if task_id=="A32":
        base=[[1,2,3,4],[3,4,1,2],[2,1,4,3],[4,3,2,1]];symbols=rng.sample([1,2,3,4],4)
        grid=[[symbols[x-1] if rng.randrange(4)<k%4 else 0 for x in row] for row in base]
        if k in (4,8):grid[0][0]=1;grid[0][1]=1
        return {"grid":grid}
    if task_id=="A33":
        n=40 if k==9 else k%9;return {"n":n,"constraints":[[i,j,rng.randint(-5,8)] for i in range(n) for j in range(n) if rng.randrange(5)==0]}
    raise KeyError(task_id)


def build_tasks():
    """Return 33 stable JSON-compatible tasks and their fixed 396 cases."""
    if reference("A33",{"n":0,"constraints":[]})!={"feasible":True,"potential":[]}:
        raise AssertionError("A33 independent empty-system anchor")
    tasks=[]
    for index,(title,category,spec) in enumerate(_SPECS,1):
        task_id=f"A{index:02}"
        cases=[]
        for j,(data,expected) in enumerate(_ANCHORS[task_id],1):
            observed=reference(task_id,data)
            if observed!=expected:
                raise AssertionError(f"hand anchor {task_id}/{j}: {observed!r} != {expected!r}")
            cases.append({"id":f"{task_id}-P{j:02}","input":data,"expected":expected,"visibility":"public"})
        rng=random.Random(710000+index)
        seen={json.dumps(c["input"],sort_keys=True,separators=(",",":")) for c in cases}
        attempt=0
        while len(cases)<12:
            if attempt>=1000:
                raise AssertionError(f"could not construct ten distinct hidden inputs for {task_id}")
            data=_generated(task_id,rng,attempt%10)
            attempt+=1
            key=json.dumps(data,sort_keys=True,separators=(",",":"))
            if key in seen:
                continue
            seen.add(key)
            cases.append({"id":f"{task_id}-H{len(cases)-1:02}","input":data,"expected":reference(task_id,data),"visibility":"hidden"})
        prompt=("Implement solution.py with a single solve(data) function. "
                "data and the return value must be JSON-compatible. Use Python 3 standard library only; "
                "perform no external I/O and do not read benchmark files. All supplied inputs satisfy "
                "the stated schema and bounds; no behavior is required for malformed input. "+spec)
        tasks.append({"id":task_id,"title":title,"category":category,"difficulty":"hard","prompt":prompt,"cases":cases})
    return tasks


if __name__=="__main__":
    tasks=build_tasks()
    assert tasks==build_tasks()
    print(json.dumps({"tasks":len(tasks),"cases":sum(len(t["cases"]) for t in tasks),"anchors":66,"deterministic":True}))
