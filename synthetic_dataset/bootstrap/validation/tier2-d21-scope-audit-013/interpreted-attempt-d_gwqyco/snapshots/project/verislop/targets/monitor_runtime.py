"""VeriSlop Tier 1 monitor runtime (python-v0_1). Shipped verbatim beside generated wrappers.

Self-contained: the delivered artifact does not import VeriSlop. It evaluates accepted DSL
formulas exactly for one observed call. Only formulas whose universal prefix is bound by the
call's arguments and result, and whose remaining quantifiers range over finite sorts or bounded
ranges, are monitored. A violation raises ContractViolation before the wrapper returns; effects
performed inside the target before that point are not rolled back (detection, not prevention).
"""

RUNTIME_VERSION = "verislop.monitor-runtime/0.1"


class ContractViolation(AssertionError):
    def __init__(self, obligation, symbol, args, result):
        super().__init__(f"VeriSlop monitor: {symbol}{tuple(args)} -> {result!r} violates obligation {obligation}")
        self.obligation = obligation
        self.symbol = symbol
        self.call_args = args
        self.result = result


def to_value(v, sort):
    """python-v0_1 -> DSL value; raises ValueError outside the profile."""
    if sort == "Nat":
        if type(v) is int and v >= 0:
            return v
        raise ValueError(f"{v!r} is not a Nat")
    if sort == "Bool":
        if type(v) is bool:
            return v
        raise ValueError(f"{v!r} is not a Bool")
    if sort == "Unit":
        if v is None:
            return ("unit",)
        raise ValueError(f"{v!r} is not Unit")
    if "enum" in sort:
        if isinstance(v, str):
            return ("enum", sort["enum"], v)
        raise ValueError(f"{v!r} is not an enumeration constructor")
    if isinstance(v, tuple) and len(v) == 2 and v[0] in ("ok", "error"):
        return (v[0], to_value(v[1], sort["result"][v[0]]))
    raise ValueError(f"{v!r} is not a Result")


def from_value(v):
    if isinstance(v, tuple):
        if v[0] == "unit":
            return None
        if v[0] == "enum":
            return v[2]
        return (v[0], from_value(v[1]))
    return v


class Evaluator:
    def __init__(self, enums, call):
        self.enums = enums
        self.call = call

    def term(self, t, env):
        tag = t["tag"]
        if tag == "var":
            return env[t["index"]]
        if tag == "nat":
            return int(t["value"])
        if tag == "bool":
            return t["value"]
        if tag == "unit":
            return ("unit",)
        if tag == "enum":
            return ("enum", t["sort"], t["constructor"])
        if tag in ("add", "sub", "mul"):
            a, b = self.term(t["left"], env), self.term(t["right"], env)
            return a + b if tag == "add" else (max(0, a - b) if tag == "sub" else a * b)
        if tag == "call":
            return self.call(t["symbol"], [self.term(a, env) for a in t["args"]])
        if tag == "ok":
            return ("ok", self.term(t["value"], env))
        if tag == "error":
            return ("error", self.term(t["value"], env))
        raise ValueError(tag)

    def finite(self, s):
        if s == "Bool":
            return [False, True]
        if s == "Unit":
            return [("unit",)]
        if "enum" in s:
            return [("enum", s["enum"], c) for c in self.enums[s["enum"]]]
        r = s["result"]
        return [("error", v) for v in self.finite(r["error"])] + [("ok", v) for v in self.finite(r["ok"])]

    def formula(self, p, env):
        tag = p["tag"]
        if tag == "true":
            return True
        if tag == "false":
            return False
        if tag in ("eq", "lt", "le"):
            a, b = self.term(p["left"], env), self.term(p["right"], env)
            return a == b if tag == "eq" else (a < b if tag == "lt" else a <= b)
        if tag == "holds":
            return self.term(p["term"], env) is True
        if tag == "not":
            return not self.formula(p["body"], env)
        if tag == "and":
            return self.formula(p["left"], env) and self.formula(p["right"], env)
        if tag == "or":
            return self.formula(p["left"], env) or self.formula(p["right"], env)
        if tag == "implies":
            return (not self.formula(p["left"], env)) or self.formula(p["right"], env)
        if tag == "iff":
            return self.formula(p["left"], env) == self.formula(p["right"], env)
        if tag in ("forall", "exists"):
            vals = self.finite(p["sort"])
            res = (self.formula(p["body"], [v] + env) for v in vals)
            return all(res) if tag == "forall" else any(res)
        if tag in ("forall_range", "exists_range"):
            lo, hi = self.term(p["lower"], env), self.term(p["upper"], env)
            res = (self.formula(p["body"], [n] + env) for n in range(lo, max(lo, hi)))
            return all(res) if tag == "forall_range" else any(res)
        raise ValueError(tag)


def check(spec, symbol, impls, args, result):
    """Evaluate every monitored obligation for one observed call; raise on a definite violation."""
    sym = spec["symbols"][symbol]
    dargs = [to_value(a, s) for a, s in zip(args, sym["args"])]
    try:
        dres = to_value(result, sym["result"])
    except ValueError:
        raise ContractViolation("python-v0_1 profile", symbol, args, result) from None

    def call(name, vals):
        if name == symbol and vals == dargs:
            return dres
        other = spec["symbols"][name]
        return to_value(impls[name](*[from_value(v) for v in vals]), other["result"])

    ev = Evaluator(spec["enums"], call)
    for ob in sym["obligations"]:
        k = len(ob["prefix"])
        vals = [None] * k
        for pos, var in enumerate(ob["arg_vars"]):
            vals[var] = dargs[pos]
        rb = ob["result_binding"]
        if rb is not None:
            if rb["wrap"] is None:
                vals[rb["var"]] = dres
            elif dres[0] == rb["wrap"]:
                vals[rb["var"]] = dres[1]
            else:
                continue  # the binding equality is false for every value: vacuous for this call
        if any(v is None for v in vals):
            continue
        env = list(reversed(vals))
        if not ev.formula(ob["body"], env):
            raise ContractViolation(ob["id"], symbol, args, result)
