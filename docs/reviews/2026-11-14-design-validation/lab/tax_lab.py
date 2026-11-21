"""Design lab for ADR-0041: the tax computation (rule 9), company-currency tie-out (rule 12),
corrections across a rate change (rule 8) and the Vietnamese seed data.

Usage: python3 -I tax_lab.py <package dir>
  P1 line level: each tax = round(base x rate)
  P2 document level: a code's line taxes sum to round(sum of exact taxes); each within one unit of exact
  P3 prices including tax: base + tax = gross on every line, whichever level is asked (always per line)
  P4 symmetry: a negated document gets exactly the negated taxes, under every rounding mode, at both levels
  P5 compound bases: a VAT code whose base includes an earlier excise code is computed on net + excise
  P6 none codes give zero tax; assessed amounts are taken as given
  P7 company currency: per code, tax rows sum exactly to the journal tax line converted once, and each row is
     within one unit plus the conversion rounding of the total of its exact converted value (INV-300)
  P8 seed data: 8% until 2026-12-31 and 10% from 2027-01-01 for reducible codes; a credit note in 2027 that
     corrects a 2026 line keeps 8%; matrix resolution examples
"""
import csv, os, random, sys
from decimal import Decimal as D, ROUND_HALF_UP, ROUND_HALF_EVEN, ROUND_DOWN, ROUND_UP, ROUND_FLOOR

MODES = {'half_up': ROUND_HALF_UP, 'half_even': ROUND_HALF_EVEN, 'down': ROUND_DOWN, 'up': ROUND_UP}
def rnd(x, unit, mode): return (x / unit).quantize(D(1), rounding=MODES[mode]) * unit

def allocate(exact, total, unit):
    """Largest remainder, sign-normalized (lab finding L-10)."""
    s = sum(exact)
    neg = s < 0 or (s == 0 and next((e for e in exact if e != 0), 0) < 0)
    if neg:
        return [-x for x in allocate([-e for e in exact], -total, unit)]
    q = [e / unit for e in exact]
    fl = [x.to_integral_value(rounding=ROUND_FLOOR) for x in q]
    r = int(total / unit - sum(fl))
    assert 0 <= r <= len(q), (r, total, exact)
    for i in sorted(range(len(q)), key=lambda i: (-(q[i] - fl[i]), i))[:r]: fl[i] += 1
    return [x * unit for x in fl]

def compute_taxes(lines, unit, mode, level, include):
    """lines: [{'amount': D, 'codes': [{'code','calc','rate','seq','kind','base_includes','assessed'}]}].
    Returns {(line_index, code): (base, tax)}. Pure (ADR-0041 rule 9). Codes are processed in `sequence`
    across the whole document: each sequence level is computed, rounded and allocated before its dependents."""
    out = {}
    if include:
        for i, ln in enumerate(lines):
            pct = [c for c in ln['codes'] if c['calc'] == 'percent']
            if len(pct) > 1: raise ValueError('tax_inclusive_multiple_codes')
            r = pct[0]['rate'] / 100 if pct else D(0)
            base = rnd(ln['amount'] / (1 + r), unit, mode)
            for c in ln['codes']:
                out[(i, c['code'])] = (base, ln['amount'] - base if c['calc'] == 'percent' else D(0))
        return out
    done = [dict() for _ in lines]
    for seq in sorted({c['seq'] for ln in lines for c in ln['codes']}):
        exact = {}
        for i, ln in enumerate(lines):
            for c in [c for c in ln['codes'] if c['seq'] == seq]:
                base = ln['amount'] + sum(done[i].get(k, D(0)) for k in c['base_includes'])
                if c['calc'] == 'assessed': out[(i, c['code'])] = (base, c['assessed'])
                elif c['calc'] == 'none': out[(i, c['code'])] = (base, D(0))
                elif level == 'line': out[(i, c['code'])] = (base, rnd(base * c['rate'] / 100, unit, mode))
                else: exact.setdefault(c['code'], []).append((i, base, base * c['rate'] / 100))
        for code, items in exact.items():
            total = rnd(sum(e for _, _, e in items), unit, mode)
            for (i, base, _), t in zip(items, allocate([e for _, _, e in items], total, unit)):
                out[(i, code)] = (base, t)
        for i, ln in enumerate(lines):
            for c in [c for c in ln['codes'] if c['seq'] == seq]:
                done[i][c['kind']] = done[i].get(c['kind'], D(0)) + out[(i, c['code'])][1]
    return out

def vat(rate, code=None): return {'code': code or f'v{rate}', 'calc': 'percent', 'rate': D(rate), 'seq': 2, 'kind': 'vat', 'base_includes': ['special_consumption'], 'assessed': None}

def main(pkg):
    random.seed(20261114)
    fails = 0
    def check(cond, msg):
        nonlocal fails
        if not cond:
            fails += 1
            if fails <= 12: print('FAIL', msg)
    for n in range(20000):
        unit = random.choice([D('1'), D('0.01')])
        mode = random.choice(list(MODES))
        lines = [{'amount': D(random.randint(-500000, 50000000)) * unit, 'codes': [vat(random.choice(['10', '8', '5']))]} for _ in range(random.randint(1, 12))]
        for level in ('line', 'document'):
            res = compute_taxes(lines, unit, mode, level, False)
            if level == 'line':
                for i, ln in enumerate(lines):
                    c = ln['codes'][0]; check(res[(i, c['code'])][1] == rnd(ln['amount'] * c['rate'] / 100, unit, mode), 'P1')
            else:
                for code in {ln['codes'][0]['code'] for ln in lines}:
                    idx = [i for i, ln in enumerate(lines) if ln['codes'][0]['code'] == code]
                    ex = [lines[i]['amount'] * lines[i]['codes'][0]['rate'] / 100 for i in idx]
                    check(sum(res[(i, code)][1] for i in idx) == rnd(sum(ex), unit, mode), 'P2 sum')
                    for i, e in zip(idx, ex): check(abs(res[(i, code)][1] - e) < unit, 'P2 within unit')
            neg = compute_taxes([{'amount': -ln['amount'], 'codes': ln['codes']} for ln in lines], unit, mode, level, False)
            check(all(neg[k][1] == -res[k][1] for k in res), f'P4 {level} {mode}')
            inc = compute_taxes(lines, unit, mode, level, True)
            for i, ln in enumerate(lines):
                b, t = inc[(i, ln['codes'][0]['code'])]; check(b + t == ln['amount'], f'P3 {level}')
        rate_fx = D(random.choice(['25432.5', '24999.987', '26001.1']))
        res = compute_taxes(lines, D('0.01'), 'half_up', 'line', False)
        by = {}
        for (i, code), (b, t) in res.items(): by.setdefault(code, []).append(t)
        for code, ts in by.items():
            journal = rnd(sum(ts) * rate_fx, D(1), 'half_up')
            rows = allocate([t * rate_fx for t in ts], journal, D(1))
            check(sum(rows) == journal, 'P7 tie-out')
            check(all(abs(rw - t * rate_fx) < 1 + abs(journal - sum(ts) * rate_fx) for rw, t in zip(rows, ts)), 'P7 row within a unit')
    sct = {'code': 'sct', 'calc': 'percent', 'rate': D('30'), 'seq': 1, 'kind': 'special_consumption', 'base_includes': [], 'assessed': None}
    for level in ('line', 'document'):
        r = compute_taxes([{'amount': D('1000000'), 'codes': [vat('10'), sct]}, {'amount': D('333333'), 'codes': [vat('10'), sct]}], D(1), 'half_up', level, False)
        check(r[(0, 'sct')][1] == D('300000') and r[(0, 'v10')] == (D('1300000'), D('130000')), f'P5 {level} {r}')
        check(r[(1, 'v10')][0] == D('333333') + r[(1, 'sct')][1], f'P5 compound base {level}')
    zero = {'code': 'kct', 'calc': 'none', 'rate': None, 'seq': 2, 'kind': 'vat', 'base_includes': [], 'assessed': None}
    duty = {'code': 'duty', 'calc': 'assessed', 'rate': None, 'seq': 1, 'kind': 'import_duty', 'base_includes': [], 'assessed': D('123456')}
    r = compute_taxes([{'amount': D('500000'), 'codes': [zero]}, {'amount': D('1000000'), 'codes': [duty]}], D(1), 'half_up', 'line', False)
    check(r[(0, 'kct')] == (D('500000'), D(0)) and r[(1, 'duty')][1] == D('123456'), 'P6')
    try:
        compute_taxes([{'amount': D('1100'), 'codes': [vat('10'), sct]}], D(1), 'half_up', 'line', True); check(False, 'P3 multi-code inclusive accepted')
    except ValueError: pass
    print('computation: 20000 random documents, P1-P7', 'PASS' if not fails else f'{fails} failures')

    tdir = os.path.join(pkg, 'tax')
    def load(n): return list(csv.DictReader(open(os.path.join(tdir, n), encoding='utf-8')))
    rate_rows = load('tax_rates.csv'); matrix = load('tax_matrix.csv')
    for x in matrix:   # ADR-0080: column tax_treatment; a package not yet reworked keeps partner_tax_group, read as the treatment
        x.setdefault('partner_tax_group', x.get('tax_treatment', ''))
    def rate(code, date):
        rows = sorted((x for x in rate_rows if x['tax_code'] == code and x['effective_from'] <= date), key=lambda x: x['effective_from'])
        return D(rows[-1]['rate_percent']) if rows else None
    def codes(d, pg, ig, date):
        rows = sorted((x for x in matrix if (x['direction'], x['partner_tax_group'], x['item_tax_group']) == (d, pg, ig) and x['effective_from'] <= date), key=lambda x: x['effective_from'])
        return rows[-1]['tax_codes'].split(';') if rows else None
    def tax_date(line):
        return line['original']['tax_date'] if line.get('original') else line['tax_date']
    invoice = {'tax_date': '2026-12-20', 'code': 'vat_out_reducible', 'amount': D('10000000')}
    credit = {'tax_date': '2027-01-15', 'code': 'vat_out_reducible', 'amount': D('-10000000'), 'original': invoice}
    t_inv = rnd(invoice['amount'] * rate(invoice['code'], tax_date(invoice)) / 100, D(1), 'half_up')
    t_cr = rnd(credit['amount'] * rate(credit['code'], tax_date(credit)) / 100, D(1), 'half_up')
    p8 = [
        (rate('vat_out_reducible', '2026-12-31') == 8, '8% on 2026-12-31'),
        (rate('vat_out_reducible', '2027-01-01') == 10, '10% on 2027-01-01'),
        (rate('vat_in_fa_reducible', '2026-06-30') == 8, 'fixed-asset input 8% in 2026'),
        (rate('vat_out_10', '2026-12-31') == 10, 'standard stays 10%'),
        (t_inv == D('800000') and t_cr == D('-800000'), f'credit note in 2027 keeps 8%: {t_inv} {t_cr}'),
        (codes('sale', 'domestic', 'standard_reducible', '2026-11-14') == ['vat_out_reducible'], 'domestic reducible sale'),
        (codes('sale', 'export', 'standard', '2026-11-14') == ['vat_out_0'], 'export at 0%'),
        (codes('sale', 'domestic', 'not_declared', '2026-11-14') == ['vat_out_not_declared'], 'not declared'),
        (codes('purchase', 'no_vat_invoice', 'standard', '2026-11-14') == ['vat_in_none'], 'no VAT invoice'),
    ]
    for ok, name in p8: check(ok, f'P8 {name}')
    print('seed and correction checks:', len(p8), 'RESULT', 'PASS' if not fails else f'{fails} failures')
    return fails

if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1]) else 0)
