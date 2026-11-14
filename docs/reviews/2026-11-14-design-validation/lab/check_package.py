"""Design-lab check of a localization package regime against the core catalogs (DS-19, ADR-0039 rule 11).

It applies what the package CI will (ADR-0016 rule 15):
- chart template: ADR-0010 rule 11, template analogues of rule 16 (unique codes, parents, no cycles,
  only leaves postable) and rule 17 (reachability, with stated exceptions), per declared legal form;
- default determination: ADR-0015 rules 4, 9, 10 and 13;
- bases: ADR-0016 rule 6 on every template entry and setting; open questions must exist;
- required settings: the `movement_type.<code>.*` keys that movement-types.csv marks `regime`.

Usage:
  python3 -I check_package.py <docs dir> <package dir> <regime>
  python3 -I check_package.py --self-test <docs dir> <package dir> <regime>
"""
import csv, itertools, os, shutil, sys, tempfile

def run(docs, pkg, regime, quiet=False):
    import yaml
    cat = os.path.join(docs, 'catalogs')
    rdir = os.path.join(pkg, 'regimes', regime)
    def load(p): return list(csv.DictReader(open(p, encoding='utf-8')))
    SA = {r['code']: r for r in load(os.path.join(cat, 'system-accounts.csv'))}
    TK = {r['code']: r for r in load(os.path.join(cat, 'transaction-keys.csv'))}
    MT = load(os.path.join(cat, 'movement-types.csv'))
    # Only open questions count: lines starting '- [ ]' (an answered '[x]' question cannot back an unverified entry).
    oq_text = '\n'.join(x for x in open(os.path.join(docs, 'open-questions.md'), encoding='utf-8').read().split('\n') if x.startswith('- [ ]'))
    manifest = yaml.safe_load(open(os.path.join(pkg, 'manifest.yaml'), encoding='utf-8'))
    forms = [f['code'] for f in manifest.get('legal_forms', [])] or [None]
    chart = load(os.path.join(rdir, 'chart_template.csv'))
    det = load(os.path.join(rdir, 'account_determination.csv'))
    seed_files = {'valuation_class': 'valuation_classes.csv', 'item_group': 'item_groups.csv', 'partner_group': 'partner_groups.csv'}
    seed_rows = {k: load(os.path.join(rdir, v)) for k, v in seed_files.items()}
    seeds = {k: [r['code'] for r in v] for k, v in seed_rows.items()}
    unreached_stated = {r['system_account']: r for r in load(os.path.join(rdir, 'unreached_system_accounts.csv'))}
    fails, notes = [], []
    def fail(m): fails.append(m)

    def anc(code):
        seen = set()
        while code:
            if code in seen: return
            seen.add(code); yield code; code = SA[code]['parent_code']
    def under(sa, node): return node in set(anc(sa))

    def oq_ok(text, where):
        for seg in [s.strip().strip('"') for s in text.split(';')]:
            tag_end = seg.find(') ')
            if not seg.startswith('(DS-') or tag_end < 0 or len(seg) - tag_end < 12 or seg not in oq_text:
                fail(f'{where}: no open question in open-questions.md matches {seg[:80]!r}')

    def basis_csv(r, where):
        b = r['basis']
        if b == 'legal_source':
            if not (r['basis_document'] and r['basis_article'] and r['basis_date']): fail(f'{where}: legal_source needs document, article, date')
        elif b == 'author_decision':
            if not (r['basis_document'] and r['basis_date']): fail(f'{where}: author_decision needs reference and date')
        elif b == 'unverified':
            oq_ok(r['basis_document'], where)
        else:
            fail(f'{where}: bad basis {b!r}')
        if (r.get('verified_by') or r.get('verified_on')) and b != 'legal_source': fail(f'{where}: verified_* without legal_source')

    def basis_yaml(e, where):
        kinds = [k for k in ('legal_source', 'author_decision') if k in e] + (['unverified'] if e.get('status') == 'unverified' else [])
        if len(kinds) != 1: fail(f'{where}: needs exactly one basis, has {kinds}'); return
        if kinds == ['unverified']: oq_ok(e.get('open_question', ''), where)
        if kinds == ['author_decision']:
            ad = e['author_decision']
            if not all(ad.get(k) for k in ('reference', 'date', 'by')): fail(f'{where}: author_decision needs reference, date, by')
        if kinds == ['legal_source'] and not all(e['legal_source'].get(k) for k in ('document', 'article', 'date')):
            fail(f'{where}: legal_source needs document, article, date')

    for k, rows in seed_rows.items():
        for r in rows: basis_csv(r, f'{seed_files[k]} {r["code"]}')
    for f_ in manifest.get('legal_forms', []):
        basis_yaml(f_, f'legal form {f_.get("code")}')

    def active(rows, form):
        out = []
        for r in rows:
            c = r['condition']
            if not c: out.append(r); continue
            neg = '!=' in c
            key, val = c.split('!=' if neg else '=')
            if key != 'legal_form' or val not in forms: fail(f'chart {r["code"]}: bad condition {c!r}'); continue
            if (form != val) if neg else (form == val): out.append(r)
        return out

    for form in forms:
        tag = f'[{form}]'
        rows = active(chart, form)
        codes = [r['code'] for r in rows]
        dup = sorted({c for c in codes if codes.count(c) > 1})
        if dup: fail(f'{tag} duplicate codes {dup}')
        by = {r['code']: r for r in rows}
        kids = {}
        for r in rows:
            p = r['parent_code']
            if p:
                if p not in by: fail(f'{tag} {r["code"]}: parent {p} missing')
                kids.setdefault(p, []).append(r['code'])
        for r in rows:   # cycles
            seen, c = set(), r['code']
            while c:
                if c in seen: fail(f'{tag} cycle at {r["code"]}'); break
                seen.add(c); c = by.get(c, {}).get('parent_code', '')
        for r in rows:
            c, sa, where = r['code'], r['system_account'], f'{tag} chart {r["code"]}'
            basis_csv(r, where)
            if r['is_postable'] not in ('true', 'false'): fail(f'{where}: is_postable {r["is_postable"]!r}')
            post = r['is_postable'] == 'true'
            if r['currency']: fail(f'{where}: a template sets no currency')
            if r['cost_behavior'] not in ('', 'variable', 'fixed'): fail(f'{where}: cost_behavior {r["cost_behavior"]!r}')
            if (r['cost_behavior'] or r['condition']) and r['basis'] not in ('unverified', 'author_decision'):
                fail(f'{where}: cost_behavior or condition is a package choice; basis must be unverified or author_decision')
            if post:
                if c in kids: fail(f'{where}: postable account has children {kids[c]}')
                if sa not in SA: fail(f'{where}: unknown system account {sa!r}'); continue
                if SA[sa]['is_postable'] != 'true': fail(f'{where}: maps to inner node {sa}')
                is_prod = under(sa, 'production_cost')
                if r['cost_behavior'] and not is_prod: fail(f'{where}: cost_behavior on a non-production-cost account')
                if is_prod and not r['cost_behavior']: fail(f'{where}: production cost account without cost_behavior (ADR-0035 rule 7)')
            else:
                if sa: fail(f'{where}: non-postable account carries a mapping')
                if c not in kids: fail(f'{where}: node without children')
                if r['cost_behavior']: fail(f'{where}: cost_behavior on a node')
        mapped = {r['system_account'] for r in rows if r['is_postable'] == 'true' and r['system_account'] in SA}
        reached = set()
        for m in mapped: reached |= set(anc(m))
        # Rule 17: every system account the core uses for determination or closing is reached, or stated.
        used = {'income_summary', 'retained_earnings', 'opening_balance_clearing'}
        for t in TK.values(): used |= set(t['required_system_accounts'].split(';'))
        for u in sorted(used):
            if u not in reached and u not in unreached_stated: fail(f'{tag} system account {u} used by the core is unreached and not stated')
        for u in unreached_stated:
            if u in reached: fail(f'{tag} {u} is stated unreached but is reached')
        others = sorted(c for c, s in SA.items() if s['is_postable'] == 'true' and c not in reached and c not in unreached_stated)
        if others: notes.append(f'{tag} other unreached postable system accounts: {others}')
    for u, r in unreached_stated.items():
        if not r.get('reason'): fail(f'unreached {u}: no reason')

    # Determination rows (ADR-0015 rules 4, 9).
    DETS = ['valuation_class', 'warehouse', 'item_group', 'partner_group', 'tax_code', 'currency']
    seen = set()
    for i, d in enumerate(det, 2):
        k = d['transaction_key']; where = f'determination line {i} ({k})'
        basis_csv(d, where)
        if k not in TK: fail(f'{where}: unknown key'); continue
        t = TK[k]; allowed = t['determinants'].split(';') if t['determinants'] else []
        for dn in DETS:
            if d[dn] and dn not in allowed: fail(f'{where}: sets {dn}, which the key does not declare')
            if d[dn] and dn in seeds and d[dn] not in seeds[dn]: fail(f'{where}: {dn} {d[dn]} not seeded')
            if d[dn] and dn in ('warehouse', 'tax_code', 'currency'): fail(f'{where}: a template leaves {dn} empty')
        ident = (k,) + tuple(d[x] for x in DETS)
        if ident in seen: fail(f'{where}: duplicate row')
        seen.add(ident)
        for form in forms:
            by = {r['code']: r for r in active(chart, form)}
            a = by.get(d['account_code'])
            if not a or a['is_postable'] != 'true': fail(f'[{form}] {where}: account {d["account_code"]} missing or not postable'); continue
            sa = a['system_account']; req = t['required_system_accounts'].split(';')
            if sa not in SA: continue
            if not any(under(sa, q) for q in req): fail(f'[{form}] {where}: {d["account_code"]} -> {sa} not under {req}')
            if t['required_control_kind'] and SA[sa]['control_kind'] != t['required_control_kind']:
                fail(f'[{form}] {where}: control kind {SA[sa]["control_kind"]} != {t["required_control_kind"]}')
            if under(sa, 'inventory') and SA[sa]['control_kind'] != 'inventory' and sa not in req:
                fail(f'[{form}] {where}: inventory-node account {sa} without control kind inventory')

    # Resolution (ADR-0015 rules 10, 13). Stock postings always carry a valuation class, and every item has
    # an item group (ADR-0015 rules 6, 7); a posting without a valuation class is possible on keys that do
    # not require control kind inventory or cost_object (e.g. price differences of services).
    def resolve(k, values):
        order = TK[k]['determinants'].split(';') if TK[k]['determinants'] else []
        cands = [d for d in det if d['transaction_key'] == k and all(not d[x] or d[x] == values.get(x) for x in DETS)]
        if not cands: return None
        def rank(d): return tuple(0 if d[x] else 1 for x in order)
        cands.sort(key=rank)
        if len(cands) > 1 and rank(cands[0]) == rank(cands[1]): return 'AMBIGUOUS'
        return cands[0]['account_code']
    combos = 0
    for k, t in TK.items():
        order = t['determinants'].split(';') if t['determinants'] else []
        stock = t['required_control_kind'] in ('inventory', 'cost_object')
        dims = []
        for dn in order:
            if dn == 'valuation_class': dims.append([(dn, v) for v in seeds[dn]] + ([] if stock else [(dn, None)]))
            elif dn == 'item_group': dims.append([(dn, v) for v in seeds[dn]])
            elif dn == 'partner_group': dims.append([(dn, v) for v in seeds[dn]] + [(dn, None)])
            else: dims.append([(dn, None)])
        for combo in (itertools.product(*dims) if dims else [()]):
            combos += 1
            res = resolve(k, dict(combo))
            if res in (None, 'AMBIGUOUS'): fail(f'key {k}: {res or "no row"} for {dict(combo)}')

    # Settings: package level and regime level; one basis each; unique identity; required keys present.
    settings = []
    for p, lvl in ((os.path.join(pkg, 'settings.yaml'), 'package'), (os.path.join(rdir, 'settings.yaml'), regime)):
        if os.path.exists(p):
            for e in yaml.safe_load(open(p, encoding='utf-8')) or []:
                settings.append((lvl, e))
    ids = set()
    for lvl, e in settings:
        ident = (e['key'], str(e['effective_from']))
        if ident in ids: fail(f'setting {ident} defined twice')
        ids.add(ident)
        basis_yaml(e, f'setting {e["key"]} ({lvl})')
    keys = {e['key'] for _, e in settings}
    for m in MT:
        for col in ('value_source', 'costing_role'):
            if m[col] == 'regime' and f'movement_type.{m["code"]}.{col}' not in keys:
                fail(f'required setting movement_type.{m["code"]}.{col} missing')
    cl = os.path.join(rdir, 'close_checklist.yaml')
    if os.path.exists(cl):
        basis_yaml(yaml.safe_load(open(cl, encoding='utf-8')), 'close_checklist.yaml')

    if not quiet:
        print(f'legal forms {forms}; chart rows {len(chart)}; determination rows {len(det)}; combinations resolved {combos}; settings {len(settings)}')
        for n in notes: print('NOTE', n)
        for f_ in fails: print('FAIL', f_)
        print('RESULT', 'PASS' if not fails else f'{len(fails)} failures')
    return fails

def self_test(docs, pkg, regime):
    """Each mutation of a passing package must fail. Returns the number of mutations that wrongly passed."""
    base = run(docs, pkg, regime, quiet=True)
    assert not base, base[:3]
    def edit(fn, old, new):
        def apply(d):
            p = os.path.join(d, 'settings.yaml') if fn == 'package:settings.yaml' else os.path.join(d, 'regimes', regime, fn)
            s = open(p, encoding='utf-8').read(); assert old in s, (fn, old); open(p, 'w', encoding='utf-8').write(s.replace(old, new, 1))
        return apply
    def drop(fn, prefix):
        def apply(d):
            p = os.path.join(d, 'regimes', regime, fn)
            lines = open(p, encoding='utf-8').read().split('\n')
            keep = [x for x in lines if not x.startswith(prefix)]
            assert len(keep) == len(lines) - 1, (fn, prefix)
            open(p, 'w', encoding='utf-8').write('\n'.join(keep))
        return apply
    M = [
        ('inventory account mapped to a receivable', edit('chart_template.csv', ',true,inventory_merchandise,', ',true,receivable_trade,')),
        ('missing revenue row', drop('account_determination.csv', 'revenue_posting,,,service,')),
        ('GR/IR on a payable account', edit('account_determination.csv', 'gr_ir_clearing,,,,,,,33881,', 'gr_ir_clearing,,,,,,,331,')),
        ('mapping to an inner node', edit('chart_template.csv', ',true,revenue_services,', ',true,revenue,')),
        ('no generic price difference row', drop('account_determination.csv', 'price_difference,,,,,,,6324,')),
        ('cost behavior on a legal-source row', edit('chart_template.csv', ',true,production_cost_labor,,,variable,unverified,', ',true,production_cost_labor,,,variable,legal_source,')),
        ('unknown open question', edit('account_determination.csv', '(DS-19) TT99 default account determination', '(DS-19) No such question')),
        ('required movement type setting missing', edit('settings.yaml', 'key: movement_type.purchase_return.costing_role', 'key: movement_type.purchase_return.costing_rolex')),
        ('two bases on one setting', edit('package:settings.yaml', '  status: unverified\n', '  status: unverified\n  legal_source: {document: x, article: y, date: 2026-01-01}\n')),
        ('inventory key on a cost-object account', edit('account_determination.csv', 'inventory_posting,raw_material,,,,,,152,', 'inventory_posting,raw_material,,,,,,154,')),
        ('closed question cited', edit('account_determination.csv', '(DS-19) TT99 default account determination', '"(DS-19, step 1) Who verifies the unverified legal rules"')),
        ('stated unreached account removed', edit('unreached_system_accounts.csv', 'inventory_other,', 'inventory_otherx,')),
    ]
    wrong = 0
    for name, apply in M:
        d = tempfile.mkdtemp()
        try:
            shutil.copytree(pkg, os.path.join(d, 'p'))
            apply(os.path.join(d, 'p'))
            f = run(docs, os.path.join(d, 'p'), regime, quiet=True)
            print(('ok     ' if f else 'MISSED ') + name + (f': {f[0][:110]}' if f else ''))
            wrong += 0 if f else 1
        finally:
            shutil.rmtree(d)
    print('SELF-TEST', 'PASS' if not wrong else f'{wrong} mutations passed')
    return wrong

if __name__ == '__main__':
    flags = [x for x in sys.argv[1:] if x.startswith('--')]
    args = [x for x in sys.argv[1:] if not x.startswith('--')]
    if set(flags) - {'--self-test'} or len(args) != 3:
        sys.exit('usage: check_package.py [--self-test] <docs dir> <package dir> <regime>')
    sys.exit(1 if (self_test(*args) if flags else run(*args)) else 0)
