"""OWB03 task-specific evidence and effect boundary. No model calls or hidden task data."""
from __future__ import annotations
import ast
import copy
import re
import uuid
from datetime import date,datetime,timedelta
from decimal import Decimal,InvalidOperation
from typing import Literal
from pydantic import Field
from contracts import Strict,OPERATORS
from core import digest,encode


class GateDenied(ValueError):
    pass


class Share(Strict):
    name: str
    email: str
    amount: float = Field(gt=0)
    line_quote: str


class ReconciliationProposal(Strict):
    note_id: int
    event_day: str
    event_label: str = Field(min_length=3)
    shares: list[Share] = Field(min_length=1)
    transaction_ids: list[int]


def cents(value):
    try:
        number=Decimal(str(value))
        if not number.is_finite() or number<0 or number!=number.quantize(Decimal('.01')):
            raise ValueError()
        return int(number*100)
    except (InvalidOperation,ValueError,TypeError):
        raise GateDenied('Currency must be a nonnegative finite amount with at most two decimal places')


def norm(value):
    return ' '.join(str(value).casefold().split())


def native_day(value):
    text=str(value)
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        try:
            return datetime.strptime(text,'%A, %B %d, %Y').date()
        except ValueError as exc:
            raise GateDenied('Unsupported native current-date format; gate adapter must be repaired') from exc


def check_actor_code(code):
    """Bound the supported REPL interface. Not a general adversarial Python sandbox."""
    tree=ast.parse(code)
    banned={'requester','getattr','setattr','delattr','globals','locals','vars','eval','exec','compile','open','input','type','object','__import__'}
    modules={'datetime','json','re','decimal','math','collections','itertools'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Name) and (node.id in banned or node.id.startswith('_')):
            raise GateDenied('Use public apis and ontology methods; private execution capabilities are unavailable')
        if isinstance(node,ast.Attribute) and (node.attr.startswith('_') or node.attr in {'requester','client','request','shell','models'}):
            raise GateDenied('Direct transport/internal access is outside the supported interface')
        if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)):
            raise GateDenied('Frozen ontology functions cannot be replaced; write ordinary procedural code')
        if isinstance(node,ast.Import):
            if any(n.name.split('.')[0] not in modules for n in node.names):
                raise GateDenied('Only ordinary data-processing standard-library imports are available')
        if isinstance(node,ast.ImportFrom) and (node.module or '').split('.')[0] not in modules:
            raise GateDenied('Import outside the supported standard-library surface')


def validate_function_outputs(candidate):
    """Independent not-a-model fixtures, not native answers or substitute model outputs."""
    namespace={}
    exec(OPERATORS,namespace)
    for f in candidate.functions:
        exec(f.code,namespace)
    facts=[{'type':'Share','properties':{'email':'a@example.invalid','name':'A','amount':30}},
           {'type':'Share','properties':{'email':'b@example.invalid','name':'B','amount':45}},
           {'type':'Share','properties':{'email':'c@example.invalid','name':'C','amount':12}},
           {'type':'Payment','properties':{'transaction_id':1,'email':'a@example.invalid','amount':10}},
           {'type':'Payment','properties':{'transaction_id':2,'email':'b@example.invalid','amount':50}}]
    reconciled=namespace['onto_reconcile'](copy.deepcopy(facts))
    expected=[{'email':'a@example.invalid','share_amount':30,'paid_amount':10,'outstanding':20},
              {'email':'b@example.invalid','share_amount':45,'paid_amount':50,'outstanding':0},
              {'email':'c@example.invalid','share_amount':12,'paid_amount':0,'outstanding':12}]
    if reconciled!=expected:
        raise GateDenied('onto_reconcile failed partial, overpaid or unmatched-payment arithmetic fixtures')
    fractional=[{'type':'Share','properties':{'email':'d@example.invalid','name':'D','amount':1.25}},
        {'type':'Payment','properties':{'transaction_id':3,'email':'d@example.invalid','amount':.1}},
        {'type':'Payment','properties':{'transaction_id':4,'email':'d@example.invalid','amount':.2}},
        {'type':'Payment','properties':{'transaction_id':5,'email':'other@example.invalid','amount':100}}]
    if namespace['onto_reconcile'](fractional)!=[{'email':'d@example.invalid','share_amount':1.25,'paid_amount':.3,'outstanding':.95}]:
        raise GateDenied('Reconciliation must round currency and exclude unrelated payer identities')
    wrapped=[{'type':'ReconciledShare','properties':r} for r in reconciled]
    outstanding=namespace['onto_outstanding_shares'](wrapped)
    if outstanding!=[expected[0],expected[2]]:
        raise GateDenied('onto_outstanding_shares must exclude zero balances')
    plan=namespace['onto_request_plan']([{'type':'OutstandingShare','properties':r} for r in outstanding],'Fixture description')
    if plan!=[{'user_email':'a@example.invalid','amount':20,'description':'Fixture description'},
             {'user_email':'c@example.invalid','amount':12,'description':'Fixture description'}]:
        raise GateDenied('onto_request_plan must preserve exact email, outstanding amount and supplied description')
    for name in ['onto_reconcile','onto_outstanding_shares']:
        if namespace[name]([])!=[]:
            raise GateDenied('Empty graph must yield empty rows')
    if namespace['onto_request_plan']([],'Fixture description')!=[]:
        raise GateDenied('Empty outstanding graph must yield empty plan')
    return namespace


class ReconciliationGate:
    def __init__(self,records,session,candidate,candidate_id,owner_email,description,accept_receipt_envelope=False):
        self.records,self.session,self.candidate,self.candidate_id=records,session,candidate,candidate_id
        self.owner_email=owner_email.casefold()
        self.description=description
        self.accept_receipt_envelope=accept_receipt_envelope
        self.functions=validate_function_outputs(candidate)
        self.observations=[]
        self.receipts={}
        self.current_plan=None
        self.permit=None
        self.step=0
        self.origin='model-action'
        self.effect_keys=set()
        self.native=None
        self.graph={'facts':[],'edges':[]}

    def event(self,kind,payload):
        return self.records.add(self.session,kind,{'step':self.step,'candidate_id':self.candidate_id,
            'model_output':'not-a-model','origin':self.origin,**payload})

    def deny(self,reason,**details):
        self.event('gate_denied',{'reason':reason,**details})
        raise GateDenied('RECONCILIATION GATE: '+reason)

    def observe(self,app,api,arguments,result):
        if (app,api) not in {('phone','get_current_date_and_time'),('phone','search_contacts'),
            ('venmo','search_users'),('venmo','show_transactions'),('simple_note','show_note'),('api_docs','show_api_doc')}:
            return
        clean={k:v for k,v in arguments.items() if k not in {'access_token','password','client','track','show','raise_on_failure'}}
        payload={'app':app,'api':api,'arguments':copy.deepcopy(clean),'result':copy.deepcopy(result)}
        ident=self.event('native_evidence',payload)
        self.observations.append({'id':ident,**payload})

    def evidence_digest(self):
        return digest([o for o in self.observations if o['app']!='api_docs'])

    def completed_queries(self,app,api):
        groups={}
        for o in self.observations:
            if (o['app'],o['api'])!=(app,api) or not isinstance(o['result'],list):
                continue
            args={k:v for k,v in o['arguments'].items() if k!='page_index'}
            key=digest(args)
            group=groups.setdefault(key,{'arguments':args,'pages':{},'conflict':False})
            page=o['arguments'].get('page_index',0)
            if page in group['pages'] and group['pages'][page]['result']!=o['result']:
                group['conflict']=True
            group['pages'][page]=o
        done=[]
        for group in groups.values():
            empties=[p for p,o in group['pages'].items() if not o['result']]
            if not empties or group['conflict']:
                continue
            end=min(empties)
            if set(range(end+1))<=set(group['pages']):
                done.append({'arguments':group['arguments'],
                    'rows':[r for p in range(end) for r in group['pages'][p]['result']],
                    'source_ids':[group['pages'][p]['id'] for p in range(end+1)]})
        return done

    def verified_facts(self,proposal):
        times=[o for o in self.observations if (o['app'],o['api'])==('phone','get_current_date_and_time')]
        if not times:
            self.deny('Retrieve native current date/time first')
        today=native_day(times[-1]['result']['date'])
        day=today-timedelta(days=1)
        if proposal.event_day!=day.isoformat():
            self.deny('Event day must be yesterday relative to observed native time')
        notes=[o for o in self.observations if o['app']=='simple_note' and o['api']=='show_note'
               and o['result'].get('note_id')==proposal.note_id]
        if not notes:
            self.deny('Selected note was not retrieved from the native API')
        note=notes[-1]
        if norm(proposal.event_label) not in norm(note['result']['title']):
            self.deny('Event label must be an observed substring of the note title')
        money_lines=[line.strip() for line in note['result']['content'].splitlines() if re.search(r'\$\s*\d',line)]
        if not money_lines or sorted(s.line_quote.strip() for s in proposal.shares)!=sorted(money_lines):
            self.deny('Every currency row in the selected note must have exactly one cited share')
        emails=[s.email.casefold() for s in proposal.shares]
        if len(emails)!=len(set(emails)):
            self.deny('Share email identities must be unique')
        contacts=self.completed_queries('phone','search_contacts')
        users=self.completed_queries('venmo','search_users')
        if not contacts or not users:
            self.deny('Complete phone and Venmo identity searches through an empty page')
        source_ids=[times[-1]['id'],note['id']]
        shares=[]
        for s in proposal.shares:
            amounts=re.findall(r'\$\s*(\d+(?:\.\d{1,2})?)',s.line_quote)
            if len(amounts)!=1 or cents(amounts[0])!=cents(s.amount) or norm(s.name) not in norm(s.line_quote):
                self.deny('Share name/amount must match its actual note row',name=s.name)
            matches={r['email'].casefold():r for q in contacts for r in q['rows']
                if norm(s.name) in {norm(r['first_name']),norm(r['first_name']+' '+r['last_name'])}}
            if len(matches)!=1 or s.email.casefold() not in matches:
                self.deny('Share identity must resolve uniquely to an observed phone contact',name=s.name)
            native_users=[r for q in users for r in q['rows'] if r['email'].casefold()==s.email.casefold()]
            if not native_users:
                self.deny('Share email must have a native Venmo identity',name=s.name)
            shares.append({'email':s.email.casefold(),'name':s.name,'amount':s.amount})
        histories=[]
        for q in self.completed_queries('venmo','show_transactions'):
            a=q['arguments']
            low=str(a.get('min_created_at','1500-01-01'))[:10]
            high=str(a.get('max_created_at','3000-01-01'))[:10]
            restricted=any(a.get(k) not in (None,'',0,0.01,False) for k in ['query','user_email','min_like_count'])
            restricted=restricted or a.get('private') is not None or a.get('min_amount',.01)>.01
            restricted=restricted or a.get('max_amount',1e18)<1e15 or a.get('max_like_count',2**63-1)<2**60
            if not restricted and a.get('direction')=='received' and low<=day.isoformat()<=high:
                # Date-only native API bounds include their full calendar day.
                upper=str(a.get('max_created_at',''))
                lower=str(a.get('min_created_at',''))
                if high==day.isoformat() and len(upper)>10 and upper[11:19]<'23:59:59':
                    continue
                if low==day.isoformat() and len(lower)>10 and lower[11:19]>'00:00:00':
                    continue
                histories.append(q)
        if not histories:
            self.deny('Complete an unfiltered received-transaction search covering the whole event day through an empty page')
        history=histories[-1]
        source_ids+=history['source_ids']+[i for q in contacts+users for i in q['source_ids']]
        eligible={}
        for tx in history['rows']:
            if tx['sender']['email'].casefold() not in emails or str(tx['created_at'])[:10]!=day.isoformat():
                continue
            if tx['receiver']['email'].casefold()!=self.owner_email:
                self.deny('Received transaction owner mismatch')
            if norm(proposal.event_label) not in norm(tx['description']):
                # A different meal/payment in this day could be ambiguous. Do not silently discard it.
                self.deny('Ambiguous payment from a listed coworker: event label does not match its description',transaction_id=tx['transaction_id'])
            if cents(tx['amount'])<=0:
                self.deny('Received payment amount must be positive')
            eligible[tx['transaction_id']]=tx
        if len(proposal.transaction_ids)!=len(set(proposal.transaction_ids)) or set(proposal.transaction_ids)!=set(eligible):
            self.deny('Selected payment IDs must account for every observed eligible incoming payment',
                      observed_eligible_ids=sorted(eligible),selected_ids=proposal.transaction_ids)
        payments=[{'transaction_id':i,'email':tx['sender']['email'].casefold(),'amount':tx['amount']} for i,tx in sorted(eligible.items())]
        facts=[{'id':'share:'+s['email'],'type':'Share','properties':s,
                'sources':[{'source_id':note['id'],'quote':next(p.line_quote for p in proposal.shares if p.email.casefold()==s['email'])}]} for s in shares]
        for p in payments:
            row=eligible[p['transaction_id']]
            actual=next(o for o in self.observations if o['id'] in history['source_ids'] and row in o['result'])
            facts.append({'id':'payment:'+str(p['transaction_id']),'type':'Payment','properties':p,
                'sources':[{'source_id':actual['id'],'quote':encode(row)}]})
        self.event('reconciliation_evidence_verified',{'proposal':proposal.model_dump(),'source_ids':sorted(set(source_ids)),
            'share_count':len(shares),'matched_payment_ids':sorted(eligible),'history_complete':True,
            'event_relevance_limit':'Chosen label matched native note title and incoming descriptions; ambiguous coworker payments fail closed'})
        return facts,shares,payments

    def call_function(self,name,facts,*args):
        output=self.functions[name](copy.deepcopy(facts),*args)
        ident=self.event('function_called',{'name':name,'args':[facts,*args],'kwargs':{},'result':output,
            'capture':'host-bound frozen function execution','code_sha256':digest(next(f.code for f in self.candidate.functions if f.name==name))})
        return output,ident

    def receipt(self,kind,data,source_ids):
        ident=uuid.uuid4().hex
        self.receipts[ident]={'kind':kind,'data':copy.deepcopy(data),'sources':source_ids,'evidence_digest':self.evidence_digest()}
        self.event('gate_receipt',{'receipt_id':ident,'kind':kind,'data':data,'source_event_ids':source_ids})
        return {'receipt_id':ident,'kind':kind,'result':copy.deepcopy(data)}

    def get(self,ident,kind):
        if self.accept_receipt_envelope and isinstance(ident,dict):
            supplied=ident
            if set(supplied)!={'receipt_id','kind','result'}:
                self.deny('Use the exact host-issued receipt envelope, without added or removed fields')
            ident=supplied.get('receipt_id')
            if not isinstance(ident,str) or ident not in self.receipts:
                self.deny('A receipt envelope must contain a real host-issued receipt_id; raw rows are not receipts')
            stored=self.receipts[ident]
            if supplied.get('kind')!=stored['kind'] or supplied.get('result')!=stored['data']:
                self.deny('Receipt envelope was modified; use the exact issued envelope or its receipt_id')
        if not isinstance(ident,str):
            self.deny('Pass the host-issued receipt_id string, not raw result rows')
        r=self.receipts.get(ident)
        if not r or r['kind']!=kind:
            self.deny('Missing required '+kind+' function receipt')
        if r['evidence_digest']!=self.evidence_digest():
            self.deny('Evidence changed after this receipt; rebuild the reconciliation chain')
        return r

    def onto_reconcile(self,proposal):
        try:
            p=ReconciliationProposal.model_validate(proposal)
        except ValueError as exc:
            self.deny('Invalid reconciliation proposal: '+str(exc)[:500])
        facts,shares,payments=self.verified_facts(p)
        output,event=self.call_function('onto_reconcile',facts)
        expected=[{'email':s['email'],'share_amount':s['amount'],
            'paid_amount':sum(cents(t['amount']) for t in payments if t['email']==s['email'])/100,
            'outstanding':max(0,cents(s['amount'])-sum(cents(t['amount']) for t in payments if t['email']==s['email']))/100} for s in shares]
        if output!=expected:
            self.deny('Generated reconciliation output failed independent arithmetic postconditions')
        self.graph={'facts':facts+[{'id':'reconciled:'+r['email'],'type':'ReconciledShare','properties':r,'sources':[]} for r in output],'edges':[]}
        return self.receipt('reconciled',output,[event])

    def onto_outstanding_shares(self,reconciliation_receipt):
        r=self.get(reconciliation_receipt,'reconciled')
        facts=[{'type':'ReconciledShare','properties':row} for row in r['data']]
        output,event=self.call_function('onto_outstanding_shares',facts)
        if output!=[row for row in r['data'] if cents(row['outstanding'])>0]:
            self.deny('Outstanding function result failed independent positive-balance filter')
        return self.receipt('outstanding',output,[*r['sources'],event])

    def onto_request_plan(self,outstanding_receipt):
        r=self.get(outstanding_receipt,'outstanding')
        facts=[{'type':'OutstandingShare','properties':row} for row in r['data']]
        output,event=self.call_function('onto_request_plan',facts,self.description)
        expected=[{'user_email':row['email'],'amount':row['outstanding'],'description':self.description} for row in r['data']]
        if output!=expected:
            self.deny('Request plan changed an identity, amount or task description')
        receipt=self.receipt('plan',output,[*r['sources'],event])
        self.current_plan=receipt['receipt_id']
        self.receipts[self.current_plan]['committed']=False
        return receipt

    def commit(self,plan_receipt,access_token):
        r=self.get(plan_receipt,'plan')
        if isinstance(plan_receipt,dict):
            plan_receipt=plan_receipt['receipt_id']
        if self.current_plan!=plan_receipt or r.get('commit_started'):
            self.deny('Plan is not current or has already been committed')
        r['commit_started']=True
        self.event('plan_commit_started',{'plan_receipt':plan_receipt})
        receipts=[]
        for row in r['data']:
            key=digest(row)
            if key in self.effect_keys:
                self.deny('Duplicate or uncertain prior effect requires reconciliation, not automatic retry')
            self.effect_keys.add(key)
            self.permit=copy.deepcopy(row)
            try:
                result=self.native('venmo','create_payment_request',access_token=access_token,**row)
            finally:
                self.permit=None
            if not isinstance(result,dict) or 'payment_request_id' not in result:
                self.deny('Native effect returned no receipt; do not retry an uncertain effect')
            receipts.append(result)
            self.event('effect_committed',{'plan_receipt':plan_receipt,'arguments':row,'native_receipt':result})
        r['committed']=True
        self.event('plan_committed',{'plan_receipt':plan_receipt,'effect_count':len(receipts)})
        return {'committed':True,'native_receipts':receipts}

    def before(self,app,api,data,method):
        if (app,api)==('venmo','create_payment_request'):
            clean={k:v for k,v in data.items() if k!='access_token'}
            if self.permit is None or clean!=self.permit:
                self.deny('Raw payment requests are blocked. Use the required ontology receipt chain and ontology.commit().',app=app,api=api)
            self.event('gate_allowed',{'app':app,'api':api,'arguments':clean,'plan_receipt':self.current_plan})
        elif (app,api)==('supervisor','complete_task'):
            if data.get('status')!='fail':
                if not self.current_plan or not self.receipts[self.current_plan].get('committed'):
                    self.deny('Successful completion requires a fully committed ontology plan')
        elif method not in {'GET'} and api not in {'login','logout'}:
            self.deny('Unrelated write capability is outside this task',app=app,api=api)

    def status(self):
        return {'evidence_calls':len(self.observations),'complete_contact_queries':len(self.completed_queries('phone','search_contacts')),
            'complete_user_queries':len(self.completed_queries('venmo','search_users')),
            'complete_transaction_queries':len(self.completed_queries('venmo','show_transactions')),
            'current_plan':self.current_plan,'committed':bool(self.current_plan and self.receipts[self.current_plan].get('committed')),
            'required_chain':['ontology.onto_reconcile(proposal)','ontology.onto_outstanding_shares(reconciliation_receipt)',
                'ontology.onto_request_plan(outstanding_receipt)','ontology.commit(plan_receipt, access_token)']}


class OntologyCapability:
    """Only supported calls are exposed to the native REPL; internal gate state stays host-owned."""
    __slots__=('_gate',)
    def __init__(self,gate):
        self._gate=gate
    def onto_reconcile(self,proposal):
        return self._gate.onto_reconcile(proposal)
    def onto_outstanding_shares(self,reconciliation_receipt):
        return self._gate.onto_outstanding_shares(reconciliation_receipt)
    def onto_request_plan(self,outstanding_receipt):
        return self._gate.onto_request_plan(outstanding_receipt)
    def commit(self,plan_receipt,access_token):
        return self._gate.commit(plan_receipt,access_token)
    def status(self):
        return copy.deepcopy(self._gate.status())


def install_boundary(world,gate,docs):
    native=world.requester._request
    def boundary(_app_name,_api_name,client=None,raise_on_failure=None,track=True,**data):
        method=docs[_app_name][_api_name]['method']
        gate.before(_app_name,_api_name,data,method)
        response=native(_app_name,_api_name,client=client,raise_on_failure=raise_on_failure,track=track,**data)
        if response.status_code==200:
            gate.observe(_app_name,_api_name,data,world.requester.response_to_json(response))
        return response
    world.requester._request=boundary
    gate.native=world.requester.request
    world.shell.user_ns['ontology']=OntologyCapability(gate)
