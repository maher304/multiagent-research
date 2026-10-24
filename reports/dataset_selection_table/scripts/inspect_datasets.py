import argparse, csv, json, re, statistics, zipfile, hashlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

def find_repo_root(start=None):
    """Locate the repository root by walking up to the directory holding ``datasets/``."""
    here = Path(start).resolve() if start else Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / 'datasets').is_dir():
            return candidate
    return Path(__file__).resolve().parents[3]

ROOT = find_repo_root()
OUT = ROOT / 'reports' / 'dataset_selection_table'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','rel':'http://schemas.openxmlformats.org/package/2006/relationships'}
CSV_DELIMITERS=',;\t|'


class ExplicitCsvDialect(csv.Dialect):
    """CSV dialect with an explicit, validated quote policy.

    ``csv.Sniffer`` can infer ``doublequote=False`` on files that encode a
    literal quote as ``""`` inside a quoted field (the Olist review comments
    do). That misreads record boundaries. We use the sniffer only to choose
    the delimiter and always parse with RFC-4180 doubled-quote semantics.
    """

    delimiter = ','
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = '\r\n'
    quoting = csv.QUOTE_MINIMAL


def resolve_csv_dialect(sample):
    dialect = ExplicitCsvDialect()
    try:
        dialect.delimiter = csv.Sniffer().sniff(sample, delimiters=CSV_DELIMITERS).delimiter
    except csv.Error:
        dialect.delimiter = ','
    return dialect


def read_csv_records(path):
    """Read a CSV with explicit quoting and report raw/parsed/rejected counts.

    Malformed records are *not* silently skipped: any record whose field count
    differs from the header is returned in ``rejected`` with its physical line
    number so the caller can report it.
    """
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        sample = handle.read(8192)
        handle.seek(0)
        dialect = resolve_csv_dialect(sample)
        reader = csv.reader(handle, dialect=dialect)
        try:
            headers = next(reader)
        except StopIteration:
            return [], [], {'delimiter': repr(dialect.delimiter), 'doublequote': dialect.doublequote,
                            'raw_records': 0, 'parsed_records': 0, 'rejected_records': 0, 'rejected_examples': []}
        parsed = []
        rejected = []
        raw_records = 0
        for values in reader:
            raw_records += 1
            if len(values) != len(headers):
                rejected.append({'physical_line': reader.line_num, 'expected_fields': len(headers),
                                 'observed_fields': len(values)})
                continue
            parsed.append(dict(zip(headers, values)))
    stats = {'delimiter': repr(dialect.delimiter), 'doublequote': dialect.doublequote,
             'raw_records': raw_records, 'parsed_records': len(parsed),
             'rejected_records': len(rejected), 'rejected_examples': rejected[:5]}
    return headers, parsed, stats

def xlsx_rows(path):
    with zipfile.ZipFile(path) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            for _,el in ET.iterparse(z.open('xl/sharedStrings.xml'),events=('end',)):
                if el.tag.endswith('}si'):
                    shared.append(''.join(t.text or '' for t in el.iter() if t.tag.endswith('}t'))); el.clear()
        wb=ET.fromstring(z.read('xl/workbook.xml')); rel=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        targets={x.attrib['Id']:x.attrib['Target'] for x in rel}
        sheets=[]
        for sh in wb.find('m:sheets',NS):
            target=targets[sh.attrib['{'+NS['r']+'}id']].lstrip('/')
            if not target.startswith('xl/'): target='xl/'+target
            sheets.append((sh.attrib['name'],target))
        for sheet_name,target in sheets:
            with z.open(target) as f:
                first=True; headers=[]
                for _,row in ET.iterparse(f,events=('end',)):
                    if not row.tag.endswith('}row'): continue
                    vals=[]
                    for c in row.findall('m:c',NS):
                        ref=c.attrib.get('r',''); idx=0
                        for ch in re.match(r'[A-Z]+',ref).group(0): idx=idx*26+ord(ch)-64
                        idx-=1
                        v=c.find('m:v',NS); inline=c.find('m:is',NS)
                        if v is not None and c.attrib.get('t')=='s': val=shared[int(v.text)]
                        elif v is not None: val=v.text
                        elif inline is not None: val=''.join(t.text or '' for t in inline.iter() if t.tag.endswith('}t'))
                        else: val=''
                        while len(vals)<=idx: vals.append('')
                        vals[idx]=val
                    if first:
                        headers=vals; first=False; yield sheet_name,headers,None
                    elif any(vals):
                        vals += ['']*max(0,len(headers)-len(vals)); yield sheet_name,headers,dict(zip(headers,vals[:len(headers)]))
                    row.clear()

def typ(v):
    if v is None or v=='': return 'missing'
    try:
        float(v); return 'numeric'
    except (TypeError, ValueError):
        pass
    for f in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M','%d/%m/%Y %H:%M','%m/%d/%Y %H:%M'):
        try: datetime.strptime(v,f); return 'datetime'
        except (TypeError, ValueError): pass
    return 'text'

def pct(n,d): return round(100*n/d,4) if d else None

def type_hint(column):
    c=column.lower().replace(' ','_')
    if 'date' in c or 'timestamp' in c or c.endswith('_at'): return 'datetime/text timestamp'
    if c.endswith('_id') or c in ('invoice','invoice_no','stockcode','order_id','customer_id','product_id','seller_id'): return 'identifier/text'
    if any(k in c for k in ('quantity','price','freight','payment_value','weight','length','height','width','photos_qty','installments','score','lat','lng','sequential')): return 'numeric measure'
    return 'categorical/text'

def main():
    ap=argparse.ArgumentParser(description='Inspect local Olist CSV and Online Retail II XLSX without modifying source files.')
    ap.add_argument('--root',default=str(ROOT)); ap.add_argument('--output',default=str(OUT)); args=ap.parse_args()
    root=Path(args.root); out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    files=[]; quality=[]; summary={'project_root':str(root),'datasets':{},'limitations':['Standard-library XLSX reader; formula cells are not evaluated.','Field type inference is value-based and descriptive, not a formal schema.']}
    # each CSV/XLSX under dataset folders only
    paths=sorted(p for p in (root/'datasets').rglob('*') if p.is_file() and p.suffix.lower() in ('.csv','.xlsx','.xls','.json'))
    records={};
    for p in paths:
        rel=str(p.relative_to(root)); ds='olist' if 'olist' in p.parts[-2].lower() or 'olist_' in p.name.lower() or 'product_category' in p.name.lower() else 'online_retail_ii'
        entry={'dataset':ds,'path':rel,'filename':p.name,'format':p.suffix.lower().lstrip('.'),'bytes':p.stat().st_size,'sheets':[]}
        if p.suffix.lower()=='.csv':
            headers, parsed_rows, parse_stats = read_csv_records(p)
            cnt=0; null=Counter(); dup=0; seen=set(); distinct={h:set() for h in headers}; num={h:[] for h in headers}; dates=defaultdict(list); composite_fields={'olist_order_items_dataset.csv':['order_id','order_item_id'],'olist_order_payments_dataset.csv':['order_id','payment_sequential']}.get(p.name); composite_seen=set(); composite_duplicates=0
            for row in parsed_rows:
                cnt+=1; tup=hashlib.sha256('x1f'.join(row.get(h,'') or '' for h in headers).encode('utf-8')).digest()
                if composite_fields:
                    pair=tuple((row.get(h) or '').strip() for h in composite_fields); composite_duplicates+=pair in composite_seen; composite_seen.add(pair)
                if tup in seen: dup+=1
                else: seen.add(tup)
                for h in headers:
                    v=(row.get(h) or '').strip()
                    if not v: null[h]+=1; continue
                    distinct[h].add(v); t=typ(v)
                    if t=='numeric':
                        x=float(v); num[h].append(x)
                    elif t=='datetime':
                        try: dates[h].append(datetime.fromisoformat(v.replace('Z','')))
                        except ValueError: pass
            entry.update(rows=cnt,columns=len(headers),column_names=headers,delimiter=parse_stats['delimiter'],
                         duplicate_rows=dup,encoding='utf-8-sig (decoded)',sheets=[],parse=parse_stats)
            records[p.name]={'rows':cnt,'headers':headers,'null':null,'distinct':distinct,'num':num,'dates':dates,'duplicates':dup,
                             'parse':parse_stats,'composite_key_check':{'fields':composite_fields,'distinct_keys':len(composite_seen),'duplicate_excess_rows':composite_duplicates} if composite_fields else None}
            for h in headers:
                quality.append({'dataset':ds,'file':p.name,'column':h,'inferred_type':type_hint(h),'missing_count':null[h],'missing_percent':pct(null[h],cnt),'distinct_nonmissing':len(distinct[h]),'min_numeric':min(num[h]) if num[h] else '', 'max_numeric':max(num[h]) if num[h] else ''})
        elif p.suffix.lower()=='.xlsx':
            sheet_stats={}; cur=None
            for sn,headers,row in xlsx_rows(p):
                if row is None:
                    cur={'rows':0,'headers':headers,'null':Counter(),'distinct':{h:set() for h in headers},'num':defaultdict(list),'dates':defaultdict(list),'duplicates':0,'seen':set(),'negative_quantity':0,'zero_quantity':0,'negative_price':0,'zero_price':0,'cancellation_rows':0,'cancellation_invoices':set(),'date_min':None,'date_max':None}; sheet_stats[sn]=cur; continue
                cur['rows']+=1; tup=hashlib.sha256('x1f'.join(row.get(h,'') or '' for h in cur['headers']).encode('utf-8')).digest(); cur['duplicates']+=tup in cur['seen']; cur['seen'].add(tup)
                try:
                    q=float(row.get('Quantity','')); cur['negative_quantity']+=q<0; cur['zero_quantity']+=q==0
                except (TypeError, ValueError): pass
                try:
                    price=float(row.get('Price','')); cur['negative_price']+=price<0; cur['zero_price']+=price==0
                except (TypeError, ValueError): pass
                invoice=(row.get('Invoice') or '').strip()
                if invoice.upper().startswith('C'):
                    cur['cancellation_rows']+=1; cur['cancellation_invoices'].add(invoice)
                try:
                    serial=float(row.get('InvoiceDate','')); dt=datetime(1899,12,30)+timedelta(days=serial)
                    cur['date_min']=dt if cur['date_min'] is None or dt<cur['date_min'] else cur['date_min']
                    cur['date_max']=dt if cur['date_max'] is None or dt>cur['date_max'] else cur['date_max']
                except (TypeError, ValueError): pass
                for h in cur['headers']:
                    v=(row.get(h) or '').strip()
                    if not v: cur['null'][h]+=1; continue
                    cur['distinct'][h].add(v)
                    if typ(v)=='numeric': cur['num'][h].append(float(v))
                    elif typ(v)=='datetime':
                        for fmt in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M','%d/%m/%Y %H:%M'):
                            try: cur['dates'][h].append(datetime.strptime(v,fmt)); break
                            except (TypeError, ValueError): pass
            entry['sheets']=[]
            allheaders=[]; total=0
            for sn,s in sheet_stats.items():
                entry['sheets'].append({'name':sn,'rows':s['rows'],'columns':len(s['headers']),'column_names':s['headers'],'duplicate_rows':s['duplicates']}); total+=s['rows']; allheaders=s['headers']
                for h in s['headers']:
                    quality.append({'dataset':ds,'file':p.name+' / '+sn,'column':h,'inferred_type':type_hint(h),'missing_count':s['null'][h],'missing_percent':pct(s['null'][h],s['rows']),'distinct_nonmissing':len(s['distinct'][h]),'min_numeric':min(s['num'][h]) if s['num'][h] else '', 'max_numeric':max(s['num'][h]) if s['num'][h] else ''})
            entry.update(rows=total,columns=len(allheaders),column_names=allheaders,duplicate_rows=sum(s['duplicates'] for s in sheet_stats.values()),encoding='OOXML/UTF-8',delimiter='not applicable')
            records[p.name]=sheet_stats
        else: entry.update(rows=None,columns=None,column_names=[],duplicate_rows=None)
        files.append(entry)
    # summarize key Olist joins
    def vals(fn,col): return records.get(fn,{}).get('distinct',{}).get(col,set())
    joins=[]
    rels=[('olist_order_items_dataset.csv','order_id','olist_orders_dataset.csv','order_id'),('olist_order_payments_dataset.csv','order_id','olist_orders_dataset.csv','order_id'),('olist_order_reviews_dataset.csv','order_id','olist_orders_dataset.csv','order_id'),('olist_orders_dataset.csv','customer_id','olist_customers_dataset.csv','customer_id'),('olist_order_items_dataset.csv','product_id','olist_products_dataset.csv','product_id'),('olist_order_items_dataset.csv','seller_id','olist_sellers_dataset.csv','seller_id')]
    for child,ck,parent,pk in rels:
        cs=vals(child,ck); ps=vals(parent,pk); joins.append({'child_file':child,'child_key':ck,'parent_file':parent,'parent_key':pk,'distinct_child_keys':len(cs),'distinct_parent_keys':len(ps),'unmatched_distinct_child_keys':len(cs-ps),'relationship':'observed key containment; does not prove semantic completeness'})
    summary['files']=files; summary['olist_relationship_checks']=joins; summary['field_quality']=quality
    summary['csv_parse_report']={name:rec['parse'] for name,rec in records.items() if isinstance(rec,dict) and 'parse' in rec}
    key_rows=[]
    key_candidates={'olist_customers_dataset.csv':['customer_id'],'olist_orders_dataset.csv':['order_id'],'olist_products_dataset.csv':['product_id'],'olist_sellers_dataset.csv':['seller_id'],'olist_order_items_dataset.csv':['order_id','product_id','seller_id'],'olist_order_payments_dataset.csv':['order_id']}
    for filename,cols in key_candidates.items():
        data=records.get(filename,{})
        if 'rows' not in data: continue
        for col in cols:
            unique=len(data['distinct'].get(col,set())); missing=data['null'].get(col,0); excess=data['rows']-missing-unique
            key_rows.append({'dataset':'olist','file':filename,'candidate_key':col,'rows':data['rows'],'distinct_nonmissing':unique,'missing_key_rows':missing,'duplicate_excess_rows':excess,'unique_nonmissing_key':missing==0 and excess==0})
        if data.get('composite_key_check'):
            ck=data['composite_key_check']; key_rows.append({'dataset':'olist','file':filename,'candidate_key':'+'.join(ck['fields']),'rows':data['rows'],'distinct_nonmissing':ck['distinct_keys'],'missing_key_rows':0,'duplicate_excess_rows':ck['duplicate_excess_rows'],'unique_nonmissing_key':ck['distinct_keys']==data['rows'] and ck['duplicate_excess_rows']==0})
    summary['primary_key_checks']=key_rows
    summary['date_ranges']={}
    for filename,data in records.items():
        if isinstance(data,dict) and 'dates' in data:
            ranges={}
            for col,values in data['dates'].items():
                if values: ranges[col]={'min':min(values).isoformat(sep=' '),'max':max(values).isoformat(sep=' '),'nonmissing_parsed':len(values)}
            if ranges: summary['date_ranges'][filename]=ranges
    xlsx_detail={}
    for filename,sheets in records.items():
        if not isinstance(sheets,dict) or not sheets or not all(isinstance(v,dict) and 'headers' in v for v in sheets.values()): continue
        xlsx_detail[filename]={'sheets':{},'all_sheets_total_rows':sum(v['rows'] for v in sheets.values()),'all_sheets_exact_duplicate_rows':sum(v['duplicates'] for v in sheets.values())}
        for sn,v in sheets.items():
            xlsx_detail[filename]['sheets'][sn]={'rows':v['rows'],'negative_quantity_rows':v['negative_quantity'],'zero_quantity_rows':v['zero_quantity'],'negative_price_rows':v['negative_price'],'zero_price_rows':v['zero_price'],'cancellation_rows':v['cancellation_rows'],'distinct_cancellation_invoices':len(v['cancellation_invoices']),'invoice_date_min':str(v['date_min']),'invoice_date_max':str(v['date_max'])}
    summary['transaction_field_checks']=xlsx_detail
    for ds in ('olist','online_retail_ii'):
        summary['datasets'][ds]={'files':[f for f in files if f['dataset']==ds],'available':any(f['dataset']==ds for f in files)}
    # artifacts
    with (out/'dataset_inventory.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['dataset','path','filename','format','bytes','rows','columns','column_names','delimiter','encoding','duplicate_rows','raw_records','parsed_records','rejected_records','sheets']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for x in files:
            parse=x.get('parse') or {}
            row={k:v for k,v in x.items() if k in fields}
            row.update({'column_names':json.dumps(x.get('column_names',[]),ensure_ascii=False),'sheets':json.dumps(x.get('sheets',[]),ensure_ascii=False),
                        'raw_records':parse.get('raw_records',''),'parsed_records':parse.get('parsed_records',''),'rejected_records':parse.get('rejected_records','')})
            w.writerow(row)
    with (out/'data_quality_summary.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['dataset','file','column','inferred_type','missing_count','missing_percent','distinct_nonmissing','min_numeric','max_numeric']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(quality)
    with (out/'primary_key_checks.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['dataset','file','candidate_key','rows','distinct_nonmissing','missing_key_rows','duplicate_excess_rows','unique_nonmissing_key']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(key_rows)
    comp=[{'criterion':'Local availability','olist':'High' if summary['datasets']['olist']['available'] else 'Low','online_retail_ii':'High' if summary['datasets']['online_retail_ii']['available'] else 'Low','basis':'Observed files in workspace; rating is local availability only.'},{'criterion':'Workflow coverage','olist':'High','online_retail_ii':'Medium','basis':'Olist has linked order/customer/payment/product/seller files; Retail II is line-level invoice-product data.'},{'criterion':'Inventory history','olist':'Low','online_retail_ii':'Low','basis':'Neither observed file set supplies stock-on-hand history or complete movements.'},{'criterion':'Accounting ledger','olist':'Low','online_retail_ii':'Low','basis':'Transaction evidence only; no chart of accounts or complete general ledger.'},{'criterion':'Fraud labels','olist':'Low','online_retail_ii':'Low','basis':'No verified fraud outcome label found in inspected source fields.'},{'criterion':'Licensing verification','olist':'Unknown / Not verified','online_retail_ii':'High','basis':'UCI verifies CC BY 4.0, permitting sharing/adaptation with attribution; Olist source terms need direct verification.'}]
    with (out/'dataset_comparison.csv').open('w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=comp[0]);w.writeheader();w.writerows(comp)
    rows=[
      {'agent':'Orchestrator','olist_suitability':'Medium','online_retail_ii_suitability':'Low','available_evidence':'Olist offers linked orders, items, payments, customers, products, sellers, and reviews for replay; Retail II has invoice lines only.','missing_information':'Neither source records agent messages, coordination states, or decisions.','proposed_implementation_or_simulation':'Implement replay workflows, agent state transitions, and coordination logs in the prototype.'},
      {'agent':'E-Commerce','olist_suitability':'High','online_retail_ii_suitability':'High','available_evidence':'Olist order IDs/status/timestamps/customers/payments; Retail II invoice, item, date, quantity, price, country fields.','missing_information':'Retail II has no full order lifecycle status or payment method; neither dataset supplies live events.','proposed_implementation_or_simulation':'Build source-specific order and invoice adapters; replay historical records.'},
      {'agent':'Inventory','olist_suitability':'Medium','online_retail_ii_suitability':'Medium','available_evidence':'Olist product IDs and order-item quantities; Retail II stock codes and line quantities.','missing_information':'External stock-on-hand snapshots, receipts, transfers, reservations, and complete inventory movements.','proposed_implementation_or_simulation':'Derive observed sold/return-like quantities; simulate inventory balances with declared assumptions.'},
      {'agent':'Accounting','olist_suitability':'Medium','online_retail_ii_suitability':'Medium','available_evidence':'Olist item prices, freight, payment values/types/installments; Retail II quantity and unit price.','missing_information':'Neither provides a complete general ledger, chart of accounts, tax/fee rules, or full settlement evidence; Retail II lacks payment records.','proposed_implementation_or_simulation':'Create analytical transaction summaries and reconciliation checks; label simulated postings.'},
      {'agent':'Risk and Anomaly Detection','olist_suitability':'Medium','online_retail_ii_suitability':'Medium','available_evidence':'Amounts, status/timing, quantities, missingness, duplicate rows, and key consistency can drive derived flags.','missing_information':'No verified fraud outcome labels or adjudicated risk context.','proposed_implementation_or_simulation':'Apply transparent review rules; treat flags as anomalies for investigation, not fraud findings.'},
      {'agent':'Governance','olist_suitability':'Medium','online_retail_ii_suitability':'Medium','available_evidence':'Fields support explicit completeness, value-range, and relationship checks.','missing_information':'Policies, approval authority, access controls, and retention rules are external to both datasets.','proposed_implementation_or_simulation':'Version explicit prototype policies and record rule outcomes.'},
      {'agent':'Audit','olist_suitability':'Medium','online_retail_ii_suitability':'Medium','available_evidence':'Stable source identifiers and repeatable file/table checks enable traceable derived reports.','missing_information':'Native chain-of-custody records and agent action logs are absent.','proposed_implementation_or_simulation':'Preserve source keys, input manifests, run IDs, validation results, and agent decision traces.'}
    ]
    with (out/'agent_suitability_matrix.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    (out/'inspection_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(f'Inspected {len(files)} data files; wrote artifacts to {out}')
    for f in files: print(f"{f['dataset']}: {f['path']} rows={f.get('rows')} columns={f.get('columns')} bytes={f['bytes']}")
if __name__=='__main__': main()

