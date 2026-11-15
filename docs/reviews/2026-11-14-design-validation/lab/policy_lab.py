"""Design lab for ADR-0043: policy evaluation and the save-time monotonicity check.

Decision = (denied, required rank, posting control level free<confirm<human). Matching rules combine by
maximum per dimension (rule 7); defaults per actor kind; floors (rule 9); consequence postings are evaluated
as their person (rule 5); the save-time check enumerates breakpoints of every ordered condition (rule 11).

Checks on 5,000 random rule tables:
  Q1 order independence
  Q2 every rule set the check accepts is monotonic on a fine random grid of all conditions; every rule set it
     rejects has a real counterexample
  Q3 floors: taint, agents only draft, LLM-contributed auto-posts, non-posting submit, change proposals
  Q4 baselines: empty for people; a person posts (submit, post, issue) for agents, systems, integrations;
     approval at submit of types with no posting step
  Q5 approvals satisfy by rank: an approval of rank r stands for a required rank <= r only
  Q6 known cases: approval + human-post combine (round-1 B1); a close job is evaluated as its person (B2);
     a discount-min allowing rule and a rank inversion are rejected; the standard "auto-post below a maximum
     with confirmation" rule is accepted
Usage: python3 -I policy_lab.py
"""
import itertools, random, sys
from decimal import Decimal as D
ACTORS = ['human', 'agent', 'integration', 'system']
LEVEL = {'free': 0, 'confirm': 1, 'human': 2}

def matches(r, action, doc, actor, x):
    if r['action'] != action or r['doc'] not in (None, doc) or r['actor'] not in (None, actor): return False
    if r['amin'] is not None and not x['amount'] >= r['amin']: return False
    if r['amax'] is not None and not x['amount'] < r['amax']: return False
    if r['dmin'] is not None and not x['discount'] >= r['dmin']: return False
    if r['mmax'] is not None and not x['margin'] < r['mmax']: return False
    if r['below_cost'] and not x['below_cost']: return False
    if r.get('outside_list') and not x.get('outside_list'): return False
    return True

def evaluate(rules, action, doc, actor, x, tainted=False, consequence=False, agent_written=False, posting_type=True, proposal=False):
    if consequence: actor = 'human'
    m = [r for r in rules if matches(r, action, doc, actor, x)]
    if any(r['effect'] == 'deny' for r in m): return (1, 0, 2)
    rank = max([r['rank'] for r in m if r['effect'] == 'require_approval'] or [0])
    human = any(r['effect'] == 'require_human_post' for r in m)
    confirm = any(r['effect'] == 'allow' and r['confirm'] for r in m)
    nonhuman = actor != 'human'
    lifted = any(r['effect'] == 'allow' for r in m)
    if nonhuman and not lifted:          # ADR-0043 rule 7: baseline lifted only by an allow rule
        human = True                       # submit too (spec 14); floor 9.8 turns it into approval for non-posting types
    if nonhuman and tainted:
        if action == 'submit': rank = max(rank, 10)
        else: human = True
    if actor == 'agent' and action in ('post', 'issue'): human = True
    if actor == 'system' and agent_written and action in ('post', 'issue'): human = True
    if action == 'submit' and not posting_type and nonhuman and human: rank, human = max(rank, 10), False
    if action == 'submit' and proposal: rank = max(rank, 10)
    return (0, rank, 2 if human else (1 if confirm else 0))

def looser(a, b):   # is b looser than a in any dimension?
    return any(bi < ai for ai, bi in zip(a, b))

STEP = {'amount': D(1), 'discount': D('0.000001'), 'margin': D('0.000001')}
LOW = {'amount': D(0), 'discount': D(0), 'margin': D(-1000)}
def axis_points(rules, key, kmin, kmax):
    pts = {D(0), LOW[key]}
    for r in rules:
        for k in (kmin, kmax):
            if k and r.get(k) is not None: pts |= {r[k], r[k] - STEP[key]}
    return sorted(p for p in pts if p >= LOW[key])

def is_monotonic(rules, action, doc, actor):
    """Rule 11: riskier = larger amount, larger discount, smaller margin, true booleans."""
    A = axis_points(rules, 'amount', 'amin', 'amax'); Dd = axis_points(rules, 'discount', 'dmin', None)
    M = sorted(axis_points(rules, 'margin', None, 'mmax') + [D(100)], reverse=True)   # riskier = smaller margin
    B = [False, True]
    grid = {}
    for a, d, mm, b, o in itertools.product(A, Dd, M, B, B):
        grid[(a, d, mm, b, o)] = evaluate(rules, action, doc, actor, {'amount': a, 'discount': d, 'margin': mm, 'below_cost': b, 'outside_list': o})
    axes = [A, Dd, M, B, B]
    for key, dec in grid.items():
        for i, ax in enumerate(axes):
            j = ax.index(key[i])
            if j + 1 < len(ax):
                k2 = list(key); k2[i] = ax[j + 1]
                if looser(dec, grid[tuple(k2)]): return False, (key, tuple(k2), dec, grid[tuple(k2)])
    return True, None

def rand_rule(i):
    eff = random.choice(['deny', 'require_approval', 'require_human_post', 'allow'])
    actor = random.choice([None] + ACTORS)
    r = {'id': f'r{i:03d}', 'action': random.choice(['submit', 'post', 'issue']), 'outside_list': random.choice([None, True]), 'doc': random.choice([None, 'sales_invoice']), 'actor': actor,
         'amin': random.choice([None, D(10_000_000), D(50_000_000)]), 'amax': random.choice([None, D(20_000_000), D(100_000_000)]),
         'dmin': random.choice([None, D(5), D(15)]), 'mmax': random.choice([None, D(10), D(30)]), 'below_cost': random.choice([None, True]),
         'effect': eff, 'rank': random.choice([10, 20]) if eff == 'require_approval' else 0, 'confirm': False}
    if eff == 'allow' and actor != 'human':
        r.update(confirm=True, amax=r['amax'] or D(100_000_000))   # rule 3
    return r

def main():
    random.seed(20261114)
    fails, stats = 0, {'sets': 0, 'rejected': 0}
    def check(c, m):
        nonlocal fails
        if not c:
            fails += 1
            if fails <= 10: print('FAIL', m)
    def rand_x(): return {'amount': D(random.choice([0, 5, 15, 25, 60, 150])) * 1_000_000, 'discount': D(random.choice([0, 3, 7, 20])),
                          'margin': D(random.choice([-5, 2, 12, 40])), 'below_cost': random.random() < 0.3, 'outside_list': random.random() < 0.3}
    for _ in range(5000):
        rules = [rand_rule(i) for i in range(random.randint(0, 10))]
        action, actor = random.choice(['submit', 'post', 'issue']), random.choice(ACTORS)
        x = rand_x(); t = random.random() < 0.3
        base = evaluate(rules, action, 'sales_invoice', actor, x, tainted=t)
        sh = rules[:]; random.shuffle(sh)
        check(evaluate(sh, action, 'sales_invoice', actor, x, tainted=t) == base, 'Q1 order')
        if t and actor != 'human':
            check(base[0] == 1 or (base[1] >= 10 if action == 'submit' else base[2] == 2), 'Q3 taint')
        if actor == 'agent' and action == 'post': check(base[0] == 1 or base[2] == 2, 'Q3 agent post')
        if not rules and actor == 'human':
            check(base == (0, 0, 0), 'Q4 human default')
        stats['sets'] += 1
        ok, ce = is_monotonic(rules, action, 'sales_invoice', actor)
        if not ok:
            stats['rejected'] += 1
            lo, hi, d1, d2 = ce
            x1 = dict(zip(['amount', 'discount', 'margin', 'below_cost', 'outside_list'], lo)); x2 = dict(zip(['amount', 'discount', 'margin', 'below_cost', 'outside_list'], hi))
            check(looser(evaluate(rules, action, 'sales_invoice', actor, x1), evaluate(rules, action, 'sales_invoice', actor, x2)), 'Q2 counterexample is real')
            continue
        pts = [rand_x() for _ in range(40)]
        def riskier(p, q): return p['amount'] >= q['amount'] and p['discount'] >= q['discount'] and p['margin'] <= q['margin'] and (p['below_cost'] or not q['below_cost']) and (p['outside_list'] or not q['outside_list'])
        for p, q in itertools.combinations(pts, 2):
            lo, hi = (q, p) if riskier(p, q) else ((p, q) if riskier(q, p) else (None, None))
            if lo is None: continue
            check(not looser(evaluate(rules, action, 'sales_invoice', actor, lo), evaluate(rules, action, 'sales_invoice', actor, hi)), 'Q2 accepted set not monotonic')
    x = rand_x()
    check(evaluate([], 'post', 'x', 'human', x) == (0, 0, 0), 'Q4 human default')
    for e in ('agent', 'system', 'integration'):
        check(evaluate([], 'post', 'x', e, x) == (0, 0, 2), f'Q4 {e} post baseline')
        check(evaluate([], 'submit', 'x', e, x) == (0, 0, 2), f'Q4 {e} submit baseline: a person posts')
        check(evaluate([], 'submit', 'x', e, x, posting_type=False)[1] >= 10, f'Q4 {e} non-posting submit needs approval')
    check(evaluate([], 'post', 'x', 'system', x, agent_written=True)[2] == 2, 'Q3 LLM-contributed auto-post')
    check(evaluate([], 'submit', 'x', 'human', x, proposal=True)[1] >= 10, 'Q3 change proposal needs approval')
    allow_sys = [{'id': 'z', 'action': 'submit', 'doc': None, 'actor': 'system', 'amin': None, 'amax': D(10**12), 'dmin': None, 'mmax': None, 'below_cost': None, 'effect': 'require_human_post', 'rank': 0, 'confirm': False}]
    check(evaluate(allow_sys, 'submit', 'x', 'system', x, posting_type=False)[1] >= 10, 'Q3 non-posting submit by a non-human needs approval')
    def satisfies(approval_rank, required_rank): return required_rank == 0 or approval_rank >= required_rank
    check(satisfies(20, 10) and satisfies(10, 10) and not satisfies(10, 20) and satisfies(0, 0), 'Q5 approval by rank')
    def R(**k):
        base = {'id': 'k', 'action': 'post', 'doc': None, 'actor': None, 'amin': None, 'amax': None, 'dmin': None, 'mmax': None, 'below_cost': None, 'effect': 'allow', 'rank': 0, 'confirm': False}
        base.update(k); return base
    x0 = {'amount': D(150_000_000), 'discount': D(0), 'margin': D(40), 'below_cost': False}
    both = [R(id='a', effect='require_approval', rank=10, amin=D(100_000_000)), R(id='b', actor='agent', effect='require_human_post', action='post')]
    check(evaluate(both, 'post', 'x', 'agent', x0) == (0, 10, 2), 'Q6 approval and human post combine')
    check(evaluate([], 'post', 'x', 'system', x0, consequence=True) == (0, 0, 0), 'Q6 close job evaluated as its person')
    bad_discount = [R(id='c', actor='system', effect='allow', confirm=True, amax=D(100_000_000), dmin=D(10))]
    check(not is_monotonic(bad_discount, 'post', 'x', 'system')[0], 'Q6 discount-min allowing rule accepted')
    inversion = [R(id='d', effect='require_approval', rank=20, amax=D(20_000_000)), R(id='e', effect='require_approval', rank=10, amin=D(20_000_000))]
    check(not is_monotonic(inversion, 'post', 'x', 'human')[0], 'Q6 rank inversion accepted')
    standard = [R(id='f', actor='system', effect='allow', confirm=True, amax=D(50_000_000))]
    check(is_monotonic(standard, 'post', 'x', 'system')[0], 'Q6 standard auto-post rule rejected')
    all_actor_approval = [R(id='g', effect='require_approval', rank=10, amin=D(100_000_000))]
    for e in ACTORS:
        check(is_monotonic(all_actor_approval, 'post', 'x', e)[0], f'Q6 all-actor approval rule rejected for {e}')
    seeded = [R(id='h', action='submit', actor='human', effect='require_approval', rank=10, below_cost=True)]
    for e in ACTORS:
        check(is_monotonic(seeded, 'submit', 'x', e)[0], f'Q6 seeded set fails for {e}')
    neg_margin = [R(id='i', actor='system', effect='allow', confirm=True, amax=D(50_000_000), mmax=D(0))]
    check(not is_monotonic(neg_margin, 'post', 'x', 'system')[0], 'Q6 margin-max allowing rule accepted (negative margins)')
    print(f"rule sets checked: {stats['sets']}, rejected by the save-time check: {stats['rejected']}")
    print('policy lab: Q1-Q6', 'PASS' if not fails else f'{fails} failures')
    return fails

if __name__ == '__main__':
    sys.exit(1 if main() else 0)
