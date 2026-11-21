"""Design-lab check of a localization package regime against the core catalogs (DS-19, ADR-0039 rule 11).

It applies what the package CI will (ADR-0016 rule 15):
- chart template: ADR-0010 rule 11, template analogues of rule 16 (unique codes, parents, no cycles,
  only leaves postable) and rule 17 (reachability, with stated exceptions), per declared legal form;
- default determination: ADR-0015 rules 4, 9, 10 and 13;
- bases: ADR-0016 rule 6 on every template entry and setting; open questions must exist;
- required settings: the `movement_type.<code>.*` keys that movement-types.csv marks `regime`;
- tax files: ADR-0041 rule 20, with the neutral kinds, package kinds and deductibility rules of ADR-0053 rules 2-3.

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
        elif b == 'test_fixture':
            if manifest.get('is_test_package') is not True: fail(f'{where}: basis test_fixture outside a test package (ADR-0053 rule 9)')
        else:
            fail(f'{where}: bad basis {b!r}')
        if (r.get('verified_by') or r.get('verified_on')) and b != 'legal_source': fail(f'{where}: verified_* without legal_source')

    def basis_yaml(e, where):
        kinds = [k for k in ('legal_source', 'author_decision') if k in e] + ([e['status']] if e.get('status') in ('unverified', 'test_fixture') else [])
        if len(kinds) != 1: fail(f'{where}: needs exactly one basis, has {kinds}'); return
        if kinds == ['test_fixture'] and manifest.get('is_test_package') is not True: fail(f'{where}: basis test_fixture outside a test package (ADR-0053 rule 9)')
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
    _tc = os.path.join(pkg, 'tax', 'tax_codes.csv')
    pkg_tax_codes = {r['code'] for r in load(_tc)} if os.path.exists(_tc) else set()
    seen = set()
    for i, d in enumerate(det, 2):
        k = d['transaction_key']; where = f'determination line {i} ({k})'
        basis_csv(d, where)
        if k not in TK: fail(f'{where}: unknown key'); continue
        t = TK[k]; allowed = t['determinants'].split(';') if t['determinants'] else []
        for dn in DETS:
            if d[dn] and dn not in allowed: fail(f'{where}: sets {dn}, which the key does not declare')
            if d[dn] and dn in seeds and d[dn] not in seeds[dn]: fail(f'{where}: {dn} {d[dn]} not seeded')
            if d[dn] and dn in ('warehouse', 'currency'): fail(f'{where}: a template leaves {dn} empty')
            if d[dn] and dn == 'tax_code' and d[dn] not in pkg_tax_codes: fail(f'{where}: tax code {d[dn]} is not a package tax code')
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

    # Tax files (ADR-0041 rule 20), at package level.
    tdir = os.path.join(pkg, 'tax')
    if os.path.isdir(tdir):
        import re as _re
        tcodes_rows = load(os.path.join(tdir, 'tax_codes.csv'))
        tcodes = {r['code']: r for r in tcodes_rows}
        if len(tcodes) != len(tcodes_rows): fail('tax codes: duplicate code')
        trates = load(os.path.join(tdir, 'tax_rates.csv'))
        tmatrix = load(os.path.join(tdir, 'tax_matrix.csv'))
        # ADR-0080 rules 1-2: the matrix's first axis is the tax treatment (column tax_treatment, list tax_treatments.csv).
        # Alias: a package not yet reworked (DS-19) keeps the old column partner_tax_group and file partner_tax_groups.csv,
        # read here as the treatment until its rework (open question, Vietnam rework).
        for m in tmatrix:
            m.setdefault('tax_treatment', m.get('partner_tax_group', ''))
            m['partner_tax_group'] = m['tax_treatment']
        itg = load(os.path.join(tdir, 'item_tax_groups.csv'))
        _tt = os.path.join(tdir, 'tax_treatments.csv')
        ptg = load(_tt if os.path.exists(_tt) else os.path.join(tdir, 'partner_tax_groups.csv'))
        datere = _re.compile(r'^\d{4}-\d{2}-\d{2}$')
        for name, rows, key in (('tax code', tcodes_rows, 'code'), ('rate', trates, 'tax_code'), ('matrix', tmatrix, 'item_tax_group'),
                                ('item tax group', itg, 'code'), ('partner tax group', ptg, 'code')):
            for r in rows: basis_csv(r, f'{name} {r[key]}')
        # Core tax kinds (ADR-0053 rule 2); a package names its own in tax/package_kinds.csv, each under one core kind.
        kinds = {'vat', 'sales_tax', 'excise', 'customs_duty', 'other'}
        _pk = os.path.join(tdir, 'package_kinds.csv')
        pkinds_rows = load(_pk) if os.path.exists(_pk) else []
        pkinds = {r['code']: r for r in pkinds_rows}
        if len(pkinds) != len(pkinds_rows): fail('package kinds: duplicate code')
        for r in pkinds_rows:
            basis_csv(r, f'package kind {r["code"]}')
            if r['tax_kind'] not in kinds: fail(f'package kind {r["code"]}: core kind {r["tax_kind"]!r}')
            if r['code'] in kinds: fail(f'package kind {r["code"]}: shadows a core kind')
        enums = {'tax_kind': kinds, 'direction': {'sale', 'purchase', 'import'}, 'calculation': {'percent', 'none', 'assessed'},
                 'deductibility': {'', 'deductible', 'not_deductible'}, 'import_treatment': {'', 'capitalize', 'recoverable'},
                 'e_invoice_label': {'', '0%', 'KCT', 'KKKNT'}}   # e-invoice add-on data kept in the draft (ADR-0053 rule 12)
        resolved = {d['tax_code'] for d in det if d['transaction_key']} | {''}
        for c, r in tcodes.items():
            for col, ok in enums.items():
                if r[col] not in ok: fail(f'tax code {c}: {col} {r[col]!r}')
            pk_ = r.get('package_kind', '')
            if pk_ and pk_ not in pkinds: fail(f'tax code {c}: undeclared package kind {pk_}')
            elif pk_ and pkinds[pk_]['tax_kind'] != r['tax_kind']: fail(f'tax code {c}: package kind {pk_} belongs to {pkinds[pk_]["tax_kind"]}, not {r["tax_kind"]}')
            if r['transaction_key'] not in TK: fail(f'tax code {c}: unknown transaction key {r["transaction_key"]}')
            elif not any(d['transaction_key'] == r['transaction_key'] and d['tax_code'] in ('', c) for d in det):
                fail(f'tax code {c}: key {r["transaction_key"]} has no determination row (ADR-0015 rule 13)')
            if r['direction'] == 'import' and not r['import_treatment']: fail(f'tax code {c}: import code without import_treatment')
            if r['tax_kind'] == 'vat' and r['direction'] in ('purchase', 'import') and not r['deductibility']: fail(f'tax code {c}: VAT input code without deductibility')
            if r['calculation'] == 'none' and r['direction'] == 'sale' and not r['e_invoice_label']: fail(f'tax code {c}: no e-invoice label')
            if r['calculation'] == 'percent' and r['e_invoice_label']: fail(f'tax code {c}: a percent code prints its rate, no label')
            for k in [x for x in r['base_includes'].split(';') if x]:
                if k not in kinds and k not in pkinds: fail(f'tax code {c}: base_includes unknown kind {k}')
            if r['fixed_asset_code'] and (r['fixed_asset_code'] not in tcodes or tcodes[r['fixed_asset_code']]['direction'] != r['direction']):
                fail(f'tax code {c}: bad fixed_asset_code {r["fixed_asset_code"]}')
        seen_r = set()
        for r in trates:
            if not datere.match(r['effective_from']): fail(f'rate {r["tax_code"]}: date {r["effective_from"]!r}')
            if (r['tax_code'], r['effective_from']) in seen_r: fail(f'rate {r["tax_code"]} {r["effective_from"]}: duplicate')
            seen_r.add((r['tax_code'], r['effective_from']))
            if r['tax_code'] not in tcodes: fail(f'rate for unknown code {r["tax_code"]}')
            elif tcodes[r['tax_code']]['calculation'] != 'percent': fail(f'rate on non-percent code {r["tax_code"]}')
        first = min([r['effective_from'] for r in trates + tmatrix] or ['9999'])
        dates = sorted({first} | {r['effective_from'] for r in trates + tmatrix})
        for c, r in tcodes.items():
            if r['calculation'] == 'percent':
                own = [x['effective_from'] for x in trates if x['tax_code'] == c]
                if not own or min(own) > first: fail(f'tax code {c}: no rate from {first}')
        seen_m = set()
        for m in tmatrix:
            k = (m['direction'], m['partner_tax_group'], m['item_tax_group'], m['effective_from'])
            if k in seen_m: fail(f'tax matrix: duplicate {k}')
            seen_m.add(k)
            if not datere.match(m['effective_from']): fail(f'tax matrix: date {m["effective_from"]!r}')
            for c in m['tax_codes'].split(';'):
                if c not in tcodes: fail(f'tax matrix: unknown code {c}')
                elif tcodes[c]['direction'] != m['direction']: fail(f'tax matrix: {c} direction {tcodes[c]["direction"]} on a {m["direction"]} row')
            if m['partner_tax_group'] not in [g['code'] for g in ptg] or m['item_tax_group'] not in [g['code'] for g in itg]:
                fail(f'tax matrix: unknown group in {m["direction"]}/{m["partner_tax_group"]}/{m["item_tax_group"]}')
        groups_for = {d: [g['code'] for g in ptg if d in g['directions'].split(';')] for d in ('sale', 'purchase')}
        for d, pgs in groups_for.items():
            for pg_, ig in itertools.product(pgs, [g['code'] for g in itg]):
                for day in dates:
                    if not [m for m in tmatrix if (m['direction'], m['partner_tax_group'], m['item_tax_group']) == (d, pg_, ig) and m['effective_from'] <= day]:
                        fail(f'tax matrix: no row for {d}/{pg_}/{ig} on {day}'); break
        rdir_ = os.path.join(tdir, 'returns')
        boxre = _re.compile(r'\[([0-9a-z]+)\]')
        formre = _re.compile(r'^[\s\[\]0-9a-z+\-()]*$')
        for fn in sorted(os.listdir(rdir_)) if os.path.isdir(rdir_) else []:
            rows = load(os.path.join(rdir_, fn)); boxes = [r['box'] for r in rows]
            if len(set(boxes)) != len(boxes): fail(f'return {fn}: duplicate box')
            for r in rows:
                basis_csv(r, f'return {fn} box {r["box"]}')
                for part in r['source'].split(';'):
                    kind, _, arg = part.partition(':')
                    if kind in ('base', 'tax', 'deductible'):
                        if arg not in tcodes: fail(f'return {fn} box {r["box"]}: unknown code in {part!r}')
                        elif kind == 'tax' and tcodes[arg]['calculation'] == 'none': fail(f'return {fn} box {r["box"]}: tax of a code without tax {arg}')
                        elif kind == 'deductible' and not tcodes[arg]['deductibility']: fail(f'return {fn} box {r["box"]}: deductible of a non-input code {arg}')
                    elif kind in ('prior_decrease', 'prior_increase') and not arg:
                        pass
                    elif kind == 'carry':
                        if arg not in boxes: fail(f'return {fn} box {r["box"]}: carry of unknown box {arg}')
                    elif kind == 'formula':
                        expr = arg.replace('pos', '').replace('neg', '')
                        if not formre.match(expr): fail(f'return {fn} box {r["box"]}: bad formula {arg!r}')
                        for b in boxre.findall(arg):
                            if b not in boxes: fail(f'return {fn} box {r["box"]}: formula refers to unknown box {b}')
                    else:
                        fail(f'return {fn} box {r["box"]}: bad source {part!r}')
        # Deductibility conditions (ADR-0053 rule 3): package rules of core condition types, with one basis each.
        dr_path = os.path.join(tdir, 'deductibility_rules.yaml')
        if os.path.exists(dr_path):
            cond_types = {'payment_evidence_threshold': {'threshold', 'aggregation', 'failing_methods', 'lapse', 'exempt_document_kinds'},
                          'none': set()}   # none ends the rule before it (ADR-0053 rule 3 note)
            methods = {'cash', 'bank_transfer', 'card', 'offset', 'third_party'}   # evidence_method values; none never fails
            aggs = {'per_seller_per_day', 'per_document'}
            seen_dr = set()
            dr_dates = {}   # (tax_kind, direction, effective_from) -> codes; the latest entry on or before a date is in force
            for e in yaml.safe_load(open(dr_path, encoding='utf-8')) or []:
                where = f'deductibility rule {e.get("code")}'
                ident = (e.get('code'), str(e.get('effective_from')))
                if ident in seen_dr: fail(f'{where}: defined twice for {ident[1]}')
                seen_dr.add(ident)
                if not datere.match(ident[1]): fail(f'{where}: date {ident[1]!r}')
                basis_yaml(e, where)
                at = e.get('applies_to') or {}
                for dn_ in at.get('directions') or []: dr_dates.setdefault((at.get('tax_kind'), dn_, ident[1]), []).append(e.get('code'))
                if at.get('tax_kind') not in kinds: fail(f'{where}: applies to unknown tax kind {at.get("tax_kind")!r}')
                if not at.get('directions') or set(at['directions']) - {'purchase', 'import'}: fail(f'{where}: directions must be purchase or import')
                ct = e.get('condition_type')
                if ct not in cond_types: fail(f'{where}: unknown condition type {ct!r}'); continue
                p = e.get('parameters') or {}
                if set(p) != cond_types[ct]: fail(f'{where}: parameters {sorted(p)} != {sorted(cond_types[ct])}'); continue
                if ct == 'none': continue
                th = p['threshold'] or {}
                if not (th.get('amount') and th.get('currency') and isinstance(th.get('includes_tax'), bool)): fail(f'{where}: threshold needs amount, currency, includes_tax')
                ag = p['aggregation'] or {}
                if ag.get('default') not in aggs or any(v not in aggs for v in (ag.get('by_document_kind') or {}).values()): fail(f'{where}: bad aggregation')
                if not p['failing_methods'] or set(p['failing_methods']) - methods: fail(f'{where}: bad failing_methods')
                if p['lapse'] not in ('due_date', 'none'): fail(f'{where}: bad lapse')
                if not isinstance(p['exempt_document_kinds'], list): fail(f'{where}: exempt_document_kinds must be a list')
            for (tk_, dn_, ef_), codes_ in sorted(dr_dates.items()):
                if len(codes_) > 1: fail(f'deductibility rules overlap for {tk_}/{dn_} from {ef_}: {sorted(codes_)} (one entry per tax kind, direction and date)')
            notes.append(f'deductibility: {len(seen_dr)} rules')
        # tax.non_cash_payment_threshold is no longer a core key (ADR-0053 rule 3).
        tax_settings = {'tax.rate_date_basis', 'tax.declaration_date_basis', 'tax.rounding_level',
                        'tax.stated_amount_tolerance', 'tax.apportionment', 'tax.return_period'}
        pkg_settings_path = os.path.join(pkg, 'settings.yaml')
        have = {e['key'] for e in (yaml.safe_load(open(pkg_settings_path, encoding='utf-8')) or [])} if os.path.exists(pkg_settings_path) else set()
        for k in sorted(tax_settings - have): fail(f'required tax setting {k} missing')
        notes.append(f'tax: {len(tcodes)} codes, {len(trates)} rates, {len(tmatrix)} matrix rows')

    # Unit names (ADR-0056 rule 18): each row names a core unit of catalogs/units.csv once, with a name and one basis.
    un_path = os.path.join(pkg, 'i18n', 'vi', 'unit_names.csv')
    if os.path.exists(un_path):
        core_units = {r['code'] for r in load(os.path.join(cat, 'units.csv'))}
        seen_u = set()
        for r in load(un_path):
            where = f'unit name {r["code"]}'
            if r['code'] in seen_u: fail(f'{where}: listed twice')
            seen_u.add(r['code'])
            if r['code'] not in core_units: fail(f'{where}: not a core unit of catalogs/units.csv')
            if not r['name_vi'].strip(): fail(f'{where}: empty name')
            basis_csv(r, where)
        for code in sorted(core_units - seen_u): fail(f'unit name {code}: core unit without a name')
        notes.append(f'unit names: {len(seen_u)} of {len(core_units)} core units')
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
    def drop_pkg(d, rel, prefix):
        p = os.path.join(d, rel)
        lines = open(p, encoding='utf-8').read().split('\n')
        keep = [x for x in lines if not x.startswith(prefix)]
        assert len(keep) == len(lines) - 1, (rel, prefix)
        open(p, 'w', encoding='utf-8').write('\n'.join(keep))
    def edit_pkg(d, rel, old, new):
        p = os.path.join(d, rel)
        t = open(p, encoding='utf-8').read(); assert old in t, (rel, old); open(p, 'w', encoding='utf-8').write(t.replace(old, new, 1))
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
        ('tax matrix row missing', lambda d: drop_pkg(d, 'tax/tax_matrix.csv', 'sale,export,reduced,')),
        ('tax rate missing', lambda d: drop_pkg(d, 'tax/tax_rates.csv', 'vat_out_5,')),
        ('unknown code in the tax matrix', lambda d: edit_pkg(d, 'tax/tax_matrix.csv', ',vat_out_5,', ',vat_out_7,')),
        ('direction mismatch in the tax matrix', lambda d: edit_pkg(d, 'tax/tax_matrix.csv', 'purchase,domestic,reduced,2026-01-01,vat_in_5,', 'purchase,domestic,reduced,2026-01-01,vat_out_5,')),
        ('bad return source', lambda d: edit_pkg(d, 'tax/returns/01_gtgt.csv', 'formula:[35]-[25]', 'formula:[35]-[99]')),
        ('tax code without basis', lambda d: edit_pkg(d, 'tax/tax_codes.csv', ',unverified,"(DS-23) Vietnamese tax codes, matrix and 01/GTGT boxes",', ',,,')),
        ('stated unreached account removed', edit('unreached_system_accounts.csv', 'inventory_other,', 'inventory_otherx,')),
        ('package kind under another tax kind', lambda d: edit_pkg(d, 'tax/tax_codes.csv', ',customs_duty,import_duty,import,', ',excise,import_duty,import,')),
        ('undeclared kind in a VAT base', lambda d: edit_pkg(d, 'tax/tax_codes.csv', ',special_consumption;environmental_protection,', ',special_consumption;environmental,')),
        ('unknown deductibility condition type', lambda d: edit_pkg(d, 'tax/deductibility_rules.yaml', 'condition_type: payment_evidence_threshold', 'condition_type: no_such_condition')),
        ('deductibility rule without basis', lambda d: edit_pkg(d, 'tax/deductibility_rules.yaml', '  status: unverified\n', '')),
        ('two deductibility rules for one kind, direction and date', lambda d: edit_pkg(d, 'tax/deductibility_rules.yaml', '- code: non_cash_payment_threshold\n', '- code: second_rule\n  condition_type: payment_evidence_threshold\n  applies_to: {tax_kind: vat, directions: [purchase]}\n  parameters:\n    threshold: {amount: "1", currency: VND, includes_tax: true}\n    aggregation: {default: per_document}\n    failing_methods: [cash]\n    lapse: none\n    exempt_document_kinds: []\n  effective_from: 2026-01-01\n  status: unverified\n  open_question: "(DS-23) Input VAT and non-cash payment"\n- code: non_cash_payment_threshold\n')),
        ('a none deductibility rule with parameters', lambda d: edit_pkg(d, 'tax/deductibility_rules.yaml', 'condition_type: payment_evidence_threshold', 'condition_type: none')),
        ('unit name of a unit that is not a core unit', lambda d: edit_pkg(d, 'i18n/vi/unit_names.csv', '\nKGM,', '\nKGMX,')),
        ('core unit without a name', lambda d: drop_pkg(d, 'i18n/vi/unit_names.csv', 'MLT,')),
        ('unit name without basis', lambda d: edit_pkg(d, 'i18n/vi/unit_names.csv', '\nGRM,g,Gam,unverified,', '\nGRM,g,Gam,,')),
        ('test_fixture basis outside a test package', edit('account_determination.csv', ',unverified,(DS-19) TT99 default account determination,', ',test_fixture,,')),
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
