#!/usr/bin/env python3
"""One durable official-CLI coordinator, separately leased; never dispatches GPU itself."""
import argparse,datetime as dt,fcntl,hashlib,json,os,re,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CLI=Path('/home/hynx/.codex/packages/standalone/releases/0.155.1-x86_64-unknown-linux-musl/bin/codex')
UNTIL='2026-10-11T11:13:13Z'
MODEL='gpt-6-astra'
BACKOFF=(60,120,300,600,1800,3600)
MAX_JSON=8*1024*1024

def require(ok,message):
    if not ok:raise ValueError(message)

def utc():return dt.datetime.now(dt.timezone.utc)
def parse_time(value):return dt.datetime.fromisoformat(value.replace('Z','+00:00'))
def stamp():return utc().isoformat()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}
def load(path):
    p=Path(path);require(p.is_file() and not p.is_symlink() and p.stat().st_size<=MAX_JSON,'bounded JSON path')
    with p.open('rb') as f:data=f.read(MAX_JSON+1)
    require(len(data)<=MAX_JSON,'JSON cap');return json.loads(data)
def bound(reference):
    require(set(reference)=={'path','sha256'} and Path(reference['path']).is_absolute(),'exact absolute ref')
    require(sha(reference['path'])==reference['sha256'],'ref drift');return load(reference['path'])
def atomic(path,value):
    p=Path(path);tmp=p.with_name(p.name+'.tmp-'+str(os.getpid()))
    with tmp.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
    fd=os.open(p.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
def emit(kind,**values):
    with (ROOT/'driver-events.jsonl').open('a') as f:
        f.write(json.dumps({'time':stamp(),'event':kind,**values},allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

def identity(pid):
    try:
        raw=Path(f'/proc/{pid}/stat').read_text();parts=raw[raw.rfind(')')+2:].split()
        return {'pid':int(pid),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'start_ticks':int(parts[19]),'state':parts[0]}
    except (OSError,ValueError,IndexError):return None

def same_alive(record):
    current=identity(record['pid'])
    return bool(current and current['state'] not in {'Z','X'} and all(current[k]==record[k] for k in ('pid','boot_id','start_ticks')))

class Lease:
    def __init__(self,path):self.path=Path(path);self.file=None
    def acquire(self):
        self.file=self.path.open('a+')
        try:fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB);return True
        except BlockingIOError:self.file.close();self.file=None;return False
    def close(self):
        if self.file is not None:self.file.close();self.file=None

def validate_release(path):
    release=load(path)
    require(release.get('schema')=='autonomy-seven-day-release-v1' and release.get('released') is True,'root release absent')
    require(release.get('until')==UNTIL and release.get('model')==MODEL and release.get('cli')==str(CLI),'fixed CLI/model/deadline')
    require(release.get('coordinator_lease')==str(ROOT/'coordinator.lease'),'shared coordinator lease')
    for key,path0 in (('driver',Path(__file__).resolve()),('prompt',ROOT/'coordinator-prompt-v1.md')):
        require(release[key]==ref(path0),'released source differs')
    handoff=bound(release['handoff']);authorization=bound(release['authorization'])
    require(handoff.get('schema')=='autonomy-seven-day-handoff-v1' and handoff.get('ready') is True
            and handoff.get('until')==UNTIL and handoff.get('authorization')==release['authorization'],'handoff not ready/bound')
    owning=Path(handoff['owning_worktree'])
    require(owning.resolve()==(ROOT.parent/'study_worktree').resolve(),'owning study mismatch')
    require(authorization.get('schema')=='autonomy-user-authorization-v1'
            and authorization.get('exact_text')=='批准预算 继续完成任务 后续所有的预算都批准 不要再问我 我要你七天自己不间断且不需要批准的连续执行'
            and authorization.get('until')==UNTIL,'exact user authority differs')
    require(release.get('completion_contract')==handoff.get('completion_contract') and release.get('completion_contract') is not None,'completion contract unbound')
    contract=bound(release['completion_contract'])
    require(contract.get('schema')=='autonomy-original-goal-completion-contract-v1' and contract.get('validation_n')==20 and contract.get('formal_n')==10,'completion requirements absent')
    return release,handoff,contract

def file_bound(reference):
    require(set(reference)=={'path','sha256'} and Path(reference['path']).is_absolute(),'exact evidence ref')
    path=Path(reference['path']);require(path.is_file() and not path.is_symlink() and path.stat().st_size<=MAX_JSON,'bounded completion evidence')
    require(sha(path)==reference['sha256'],'completion evidence drift')

def completion_ok(path,contract):
    """Narrow future normalized goal proof; absence/schema mismatch means continue."""
    if not Path(path).exists():return False
    try:
        result=load(path)
        require(contract=={'schema':'autonomy-original-goal-completion-contract-v1','goal_spec':contract['goal_spec'],
                           'review_schema':'autonomy-original-goal-review-v1','validation_n':20,'validation_min':10,
                           'formal_n':10,'formal_min':5,'checks':['substantive_qd_ed','matched_ablations','cost','validity','reproducibility']},'frozen original goal contract')
        require(result.get('schema')=='autonomy-original-goal-completion-v1'
                and result.get('goal_contract')==ref(ROOT/'completion-contract-v1.json'),'completion contract identity')
        review=bound(result['goal_review']);require(review['schema']==contract['review_schema'] and review['decision']=='ACCEPT_ORIGINAL_GOAL','goal review')
        require(review['goal_spec']==contract['goal_spec'],'original goal spec');file_bound(review['goal_spec'])
        source=review['candidate_source'];candidate=review['candidate_profile']
        require(re.fullmatch('[0-9a-f]{40}',source) and candidate not in {'C0','Q0'},'candidate source/profile')
        file_bound(review['runtime']);file_bound(review['task_protocol'])
        for phase,n,minimum in [('validation',20,10),('formal',10,5)]:
            result=bound(review[phase]);require(result['schema']=='autonomy-normalized-phase-evidence-v1' and result['phase']==phase,'phase evidence schema')
            require(result['candidate_source']==source and result['runtime']==review['runtime'] and result['task_protocol']==review['task_protocol'],'same frozen source/runtime/protocol')
            original=bound(result['original_result']);require(isinstance(original,dict) and original,'actual original phase result')
            require(result['all_outcomes_valid'] is True and result['no_tuning_after_freeze'] is True,'phase validity/freeze')
            cells=result['cells'];require(len(cells)==3*n,'full phase denominators');seen=set();wins={a:0 for a in (candidate,'C0','Q0')};identities={a:set() for a in wins}
            for cell in cells:
                arm=cell['arm'];require(arm in wins and type(cell['success']) is bool and cell['outcome_valid'] is True,'typed cell outcome')
                final=bound(cell['attempt_result']);require(final.get('event')=='valid' and final.get('outcome_valid') is True
                    and final.get('required_cost_telemetry_complete') is True and final.get('success') is cell['success']
                    and final.get('source_commit')==source and final.get('identity',{}).get('profile')==arm
                    and final.get('identity',{}).get('split')==phase,'bound original valid attempt')
                require(final['attempt_id'] not in seen,'duplicate outcome');seen.add(final['attempt_id'])
                identity=json.dumps({k:v for k,v in final['identity'].items() if k not in {'profile','iteration'}},sort_keys=True)
                require(identity not in identities[arm],'duplicate task/seed identity');identities[arm].add(identity)
                require(final.get('n23_worker_receipt')==cell['worker_receipt'],'original receipt linkage');receipt=bound(cell['worker_receipt'])
                audit_ref=receipt
                for key in cell['receipt_audit_path']:audit_ref=audit_ref[key]
                require(audit_ref==cell['audit'],'receipt audit linkage');audit=bound(cell['audit']);require(audit.get('accepted') is True,'actual native audit')
                original_cell=original
                for key in cell['original_result_cell_path']:original_cell=original_cell[key]
                require(original_cell.get('attempt_id')==final['attempt_id'] and original_cell.get('success') is cell['success'],'original phase result cell linkage')
                wins[arm]+=int(cell['success'])
            require(all(len(v)==n for v in identities.values()) and identities[candidate]==identities['C0']==identities['Q0'],'matched complete identities')
            require(result['counts']=={a:{'audited':n,'success':wins[a]} for a in wins}
                and all(type(result['counts'][a][k]) is int for a in wins for k in ('audited','success')),'actual integer counts')
            require(wins[candidate]>=minimum and wins[candidate]>=max(wins['C0'],wins['Q0']),'original success gate')
        require(set(review['checks'])==set(contract['checks']),'all original mechanism/ablation/cost/validity/reproduction checks')
        for name in contract['checks']:
            check=bound(review['checks'][name]);require(check['schema']=='autonomy-goal-component-review-v1'
                and check['component']==name and check['decision']=='PASS' and check['candidate_source']==source
                and check['runtime']==review['runtime'] and check['task_protocol']==review['task_protocol']
                and isinstance(check['evidence'],list) and check['evidence'],'bound substantive checks')
            for evidence in check['evidence']:file_bound(evidence)
        return True
    except (OSError,ValueError,KeyError,TypeError,IndexError):return False

def child_environment():
    env=dict(os.environ)
    for key in list(env):
        if key in {'OPENAI_API_KEY','OPENAI_BASE_URL','OPENAI_ORG_ID','OPENAI_ORGANIZATION','OPENAI_PROJECT_ID',
                   'OPENAI_API_TYPE','OPENAI_API_VERSION','CODEX_API_KEY','CODEX_ACCESS_TOKEN','CODEX_MODEL_PROVIDER',
                   'CHATGPT_BASE_URL','GOOGLE_API_KEY','GEMINI_API_KEY','POE_API_KEY','POE_TOKEN'} or key.startswith('AZURE_OPENAI_'):
            env.pop(key,None)
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):env[key]='2'
    # Managed saved auth stays in inherited HOME/CODEX_HOME, unopened and unmodified.
    return env

def command(owning,folder):
    return [str(CLI),'exec','--ignore-user-config','--json','--color','never','-C',str(owning),
            '-s','danger-full-access','-m',MODEL,'-c','model_provider="openai"','-c','approval_policy="never"',
            '--output-last-message',str(folder/'last-message.txt'),'-']

def classify(folder,exitcode):
    if exitcode==0:return 'completed_turn'
    # Bounded tail only; model/transport content is retained in the original logs, not copied into status.
    data=b''
    for name in ('events.jsonl','stderr.log'):
        p=folder/name
        if p.exists():
            with p.open('rb') as f:f.seek(max(0,p.stat().st_size-65536));data+=f.read(65536)
    text=data.decode(errors='replace').lower()
    if any(s in text for s in ('quota','rate limit','429','usage limit')):return 'official_quota_or_rate_limit'
    if any(s in text for s in ('network','connection','timed out','timeout','stream disconnected')):return 'network_or_transport_failure'
    return 'coordinator_exit_failure'

def session_ids(path):
    ids=set()
    if not path.exists():return []
    with path.open('rb') as f:
        while True:
            line=f.readline(MAX_JSON+1)
            if not line:break
            if len(line)>MAX_JSON:continue
            try:event=json.loads(line)
            except ValueError:continue
            for key in ('thread_id','session_id'):
                value=event.get(key)
                if isinstance(value,str):ids.add(value)
    return sorted(ids)

def source_commit(owning):
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=owning,text=True,timeout=10).strip()

class Driver:
    def __init__(self,release_path,*,sleep=time.sleep,now=utc,make_command=command,poll_seconds=5):
        self.release_path=Path(release_path);self.sleep=sleep;self.now=now;self.make_command=make_command;self.poll=poll_seconds;self.stopping=False
    def stop_reason(self,contract):
        if self.stopping or (ROOT/'STOP').exists():return 'manual_stop'
        if self.now()>=parse_time(UNTIL):return 'authorization_deadline'
        if completion_ok(ROOT/'completion-v1.json',contract):return 'bound_original_goal_complete'
        return None
    def status(self,**values):atomic(ROOT/'driver-status.json',{'schema':'autonomy-driver-status-v1','at':stamp(),'driver':identity(os.getpid()),**values})
    def pause(self,seconds,contract):
        # Small sleeps make STOP responsive; no tool polling or model busy loop.
        end=time.monotonic()+seconds
        while time.monotonic()<end and not self.stop_reason(contract):self.sleep(min(self.poll,max(0,end-time.monotonic())))
    def run_turn(self,release,handoff,number,*,lease_fd):
        folder=ROOT/'turns'/f'{number:06d}';folder.mkdir(parents=True,exist_ok=False)
        owning=Path(handoff['owning_worktree']);before=source_commit(owning)
        prompt=(ROOT/'coordinator-prompt-v1.md').read_text()+ '\n\nBound handoff: '+json.dumps(release['handoff'])+'\nExact authority: '+json.dumps(release['authorization'])+'\nLocal driver status: '+str(ROOT/'driver-status.json')+'\nPrior turn records: '+str(ROOT/'turns')+'\n'
        (folder/'prompt.txt').write_text(prompt);argv=self.make_command(owning,folder)
        start=time.monotonic();rec={'schema':'autonomy-coordinator-turn-v1','number':number,'started_at':stamp(),'source_before':before,
            'argv':argv,'cwd':str(owning),'driver_source':release['driver'],'prompt_source':release['prompt'],'handoff':release['handoff'],
            'authorization':release['authorization'],'process':None,'exit':None,'status':'launching'}
        atomic(folder/'receipt.json',rec)
        with (folder/'events.jsonl').open('xb') as out,(folder/'stderr.log').open('xb') as err:
            child=subprocess.Popen(argv,cwd=owning,stdin=subprocess.PIPE,stdout=out,stderr=err,env=child_environment(),start_new_session=True,pass_fds=(lease_fd,))
            rec['process']=identity(child.pid);require(rec['process'] is not None,'child identity unavailable')
            rec['status']='running';atomic(folder/'receipt.json',rec);atomic(ROOT/'active-turn.json',{'receipt':ref(folder/'receipt.json'),'process':rec['process'],'folder':str(folder)})
            child.stdin.write(prompt.encode());child.stdin.close()
            warned=False
            while child.poll() is None:
                # A soft timer is advisory. Never terminate a process group that could own a GPU cohort.
                if time.monotonic()-start>3600 and not warned:
                    warned=True;rec['soft_timeout_observed']=True;rec['status']='long_running_no_restart';atomic(folder/'receipt.json',rec)
                    emit('soft_timeout_no_signal',number=number,process=rec['process'])
                self.status(phase='draining' if self.stopping or (ROOT/'STOP').exists() or self.now()>=parse_time(UNTIL) else 'coordinator_running',turn=number,process=rec['process'])
                self.sleep(self.poll)
            rec.update(exit=child.wait(),finished_at=stamp(),elapsed_wall_seconds=time.monotonic()-start,source_after=source_commit(owning))
        rec['session_ids']=session_ids(folder/'events.jsonl');rec['status']=classify(folder,rec['exit']);atomic(folder/'receipt.json',rec)
        atomic(ROOT/'active-turn.json',{'receipt':ref(folder/'receipt.json'),'process':rec['process'],'folder':str(folder),'closed':True})
        emit('turn_exited',number=number,exit=rec['exit'],status=rec['status'],sessions=rec['session_ids']);return rec
    def run(self):
        singleton=Lease(ROOT/'driver.lock')
        if not singleton.acquire():return 3
        lease=Lease(ROOT/'coordinator.lease')
        try:
            release,handoff,contract=validate_release(self.release_path)
            self.status(phase='waiting_for_root_handoff')
            while not lease.acquire():
                if self.stop_reason(contract):return 0
                self.sleep(self.poll)
            # Recheck after root drops the shared lease; no launch under a changing handoff.
            release,handoff,contract=validate_release(self.release_path)
            active=ROOT/'active-turn.json'
            if active.exists():
                previous=load(active)
                while not previous.get('closed') and same_alive(previous['process']):
                    self.status(phase='waiting_existing_coordinator_no_restart',process=previous['process'])
                    self.sleep(self.poll)
                if not previous.get('closed'):
                    emit('prior_coordinator_exited_without_receipt',process=previous['process'])
            turns=ROOT/'turns';turns.mkdir(exist_ok=True)
            number=max([int(p.name) for p in turns.iterdir() if p.is_dir() and p.name.isdigit()]+[0])+1;failures=0
            while not self.stop_reason(contract):
                release,handoff,contract=validate_release(self.release_path)
                rec=self.run_turn(release,handoff,number,lease_fd=lease.file.fileno());number+=1
                failures=failures+1 if rec['exit'] else 0
                delay=BACKOFF[min(failures-1,len(BACKOFF)-1)] if failures else 60
                self.status(phase='backoff' if failures else 'between_turns',next_delay_seconds=delay,consecutive_failures=failures)
                self.pause(delay,contract)
            self.status(phase='stopped',reason=self.stop_reason(contract),gpu_cohort_signaled=False);return 0
        finally:lease.close();singleton.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--release',type=Path,required=True);args=parser.parse_args()
    os.sched_setaffinity(0,{0,1})
    driver=Driver(args.release)
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:setattr(driver,'stopping',True))
    try:return driver.run()
    except Exception as exc:
        emit('driver_exception',type=type(exc).__name__,message=str(exc));return 1
if __name__=='__main__':sys.exit(main())
