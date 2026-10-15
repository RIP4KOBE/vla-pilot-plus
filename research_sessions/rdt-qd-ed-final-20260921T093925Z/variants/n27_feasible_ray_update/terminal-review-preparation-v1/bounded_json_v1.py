"""Finite explicit JSON inventory. No transitive reference following or collector."""
import hashlib
import json
import os
import stat
from pathlib import Path

MAX_FILE=16*1024*1024
MAX_TOTAL=128*1024*1024
MAX_FILES=120
class MetadataError(ValueError):pass
def need(ok,message):
    if not ok:raise MetadataError(message)
def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def digest(blob):return hashlib.sha256(blob).hexdigest()
def is_ref(v):return isinstance(v,dict) and set(v)=={'path','sha256'} and isinstance(v['path'],str) and Path(v['path']).is_absolute() and isinstance(v['sha256'],str) and len(v['sha256'])==64 and all(c in '0123456789abcdef' for c in v['sha256'])
def same_ref(a,b):return is_ref(a) and is_ref(b) and a==b

def parse(blob):
    def pairs(items):
        result={}
        for k,v in items:need(k not in result,'duplicate JSON key');result[k]=v
        return result
    return json.loads(blob,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(MetadataError('nonfinite JSON')))

def bounded_bytes(path,limit):
    # O_NOFOLLOW plus inode/stat stability; checking parent symlinks is explicit.
    p=Path(path);need(p.is_absolute(),'absolute path required')
    need(all(not q.is_symlink() for q in (p,*p.parents)),'symlink metadata path')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and 0<=before.st_size<=limit,'metadata byte cap/type')
        with os.fdopen(fd,'rb',closefd=False) as f:blob=f.read(limit+1)
        after=os.fstat(fd)
        need(len(blob)==before.st_size<=limit and (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'metadata changed during read')
        return blob
    finally:os.close(fd)

class Reader:
    def __init__(self,inventory):
        need(isinstance(inventory,list) and len(inventory)<=MAX_FILES,'file count cap')
        self.entries={};self.cache={};self.bytes=0
        planned=0
        for x in inventory:
            need(set(x)=={'role','path','sha256','present','bytes'} and isinstance(x['role'],str),'inventory record')
            p=Path(x['path']);need(p.is_absolute() and p.suffix=='.json' and '..' not in p.parts,'JSON metadata only')
            need(not any(v in p.parts for v in ('decision_evidence','protected','validation','formal')),'forbidden raw/protected path')
            need(p.name not in {'stage_events.json','eds_metrics.json','episode_compute.json'},'forbidden payload role')
            need(type(x['present']) is bool and type(x['bytes']) is int and 0<=x['bytes']<=MAX_FILE,'declared byte cap')
            need(is_ref({'path':x['path'],'sha256':x['sha256']}) if x['present'] else x['sha256'] is None and x['bytes']==0,'presence/hash declaration')
            key=(x['role'],x['path']);need(key not in self.entries,'duplicate role/path');self.entries[key]=x;planned+=x['bytes']
        need(planned<=MAX_TOTAL and len({v['path'] for v in inventory})==len(inventory),'total cap/duplicate physical path')
    def get(self,reference,role):
        need(isinstance(reference,dict) and set(reference)=={'path','sha256'},'reference shape')
        key=(role,reference['path']);need(key in self.entries,'reference outside explicit role inventory')
        ent=self.entries[key];need(ent['sha256']==reference['sha256'],'reference hash differs')
        if key in self.cache:return self.cache[key]
        p=Path(ent['path'])
        if not ent['present']:
            need(not p.exists() and not p.is_symlink(),'declared absence became present');value=None
        else:
            need(self.bytes+ent['bytes']<=MAX_TOTAL,'cumulative cap')
            blob=bounded_bytes(p,min(MAX_FILE,MAX_TOTAL-self.bytes));self.bytes+=len(blob)
            need(len(blob)==ent['bytes'] and digest(blob)==ent['sha256'],'metadata size/hash differs');value=parse(blob)
        self.cache[key]=value;return value
    def require_consumed(self):
        need(set(self.cache)==set(self.entries),'unused or unsolicited inventory entry')
