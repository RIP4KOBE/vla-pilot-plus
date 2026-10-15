"""Finite, role-bound metadata reads; nested references never imply permission."""
import hashlib
import json
from pathlib import Path

MAX_FILES=512
MAX_FILE=16*1024*1024
MAX_TOTAL=128*1024*1024
ROLES={'plan','source','runtime','result','status','journal','current_journal','resources',
 'controller','release','precheck','proof','proof_plan','proof_report','proof_process','proof_terminal',
 'context','command','process','audit_start','receipt','audit','metrics','compute','terminal','eligibility',
 'recovery_attestation','cleanup_attestation','source_review','source_bridge','proof_authority','proof_review'}
ABSENT={'result','status','process','audit_start','receipt','audit','metrics','compute','context','command','terminal'}
FORBIDDEN={'attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl','stage_events.jsonl','events.jsonl'}

class MetadataError(ValueError):pass
def need(ok,message):
    if not ok:raise MetadataError(message)
def digest(b):return hashlib.sha256(b).hexdigest()
def canonical(value):return digest(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def unique(pairs):
    result={}
    for k,v in pairs:
        need(k not in result,'duplicate JSON key');result[k]=v
    return result
def decode(blob):
    return json.loads(blob,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(MetadataError('nonfinite JSON')))
def load_bound(path,cap=MAX_FILE):
    p=Path(path)
    need(p.is_file() and not p.is_symlink(),'metadata missing or symlink')
    size=p.stat().st_size;need(0<=size<=cap,'metadata per-file bound')
    with p.open('rb') as f:b=f.read(cap+1)
    need(len(b)==size and len(b)<=cap,'metadata changed/grew while reading')
    return b
def ref(path):
    p=Path(path).resolve();return {'path':str(p),'sha256':digest(load_bound(p))}
def is_ref(x):
    return isinstance(x,dict) and set(x)=={'path','sha256'} and Path(x['path']).is_absolute() and isinstance(x['sha256'],str) and len(x['sha256'])==64
def same_ref(a,b):
    return is_ref(a) and is_ref(b) and Path(a['path']).resolve()==Path(b['path']).resolve() and a['sha256']==b['sha256']
class Reader:
    def __init__(self,records):
        need(isinstance(records,list) and len(records)<=MAX_FILES,'metadata file count')
        self.records={};self.cache={};self.bytes_read=0
        declared=0
        for row in records:
            need(set(row)=={'role','path','present','sha256','bytes'} and row['role'] in ROLES,'metadata role/schema')
            p=Path(row['path']);key=str(p.resolve())
            need(p.is_absolute() and p.name not in FORBIDDEN and 'decision_evidence' not in p.parts
                 and p.suffix in {'.json','.jsonl'} and not p.is_symlink(),'forbidden payload path')
            need(key not in self.records,'duplicate/aliased metadata input')
            need(type(row['present']) is bool,'presence must be typed')
            if row['present']:
                need(type(row['bytes']) is int and 0<=row['bytes']<=MAX_FILE
                     and is_ref({'path':row['path'],'sha256':row['sha256']}),'metadata size/hash declaration')
                declared+=row['bytes']
            else:
                need(row['role'] in ABSENT and row['sha256'] is None and row['bytes']==0,'invalid absence')
            self.records[key]=row
        need(declared<=MAX_TOTAL,'metadata total declaration')
    def get(self,reference,role):
        need(isinstance(reference,dict) and set(reference)=={'path','sha256'},'reference shape')
        key=str(Path(reference['path']).resolve());need(key in self.records,'undeclared metadata read')
        row=self.records[key];need(row['role']==role and row['sha256']==reference['sha256'],'role/hash mismatch')
        if not row['present']:
            need(not Path(row['path']).exists() and not Path(row['path']).is_symlink(),'recorded absence changed')
            return None
        if key not in self.cache:
            need(self.bytes_read+row['bytes']<=MAX_TOTAL,'distinct-byte cap')
            blob=load_bound(row['path'])
            need(len(blob)==row['bytes'] and digest(blob)==row['sha256'],'metadata bytes drift')
            self.bytes_read+=len(blob)
            self.cache[key]=([decode(v) for v in blob.splitlines() if v.strip()]
                             if Path(row['path']).suffix=='.jsonl' else decode(blob))
        return self.cache[key]
    def reference(self,path,role):
        key=str(Path(path).resolve());need(key in self.records and self.records[key]['role']==role,'missing typed inventory reference')
        row=self.records[key];return {'path':row['path'],'sha256':row['sha256']}
    def at(self,path,role):return self.get(self.reference(path,role),role)

