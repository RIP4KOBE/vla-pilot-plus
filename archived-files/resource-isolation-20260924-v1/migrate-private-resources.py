#!/usr/bin/env python3
"""One-time authorized resource split. No GPU, episode, model or process launcher.

Execution requires an independently held old runner lease and a reviewed script
SHA. A partial failure keeps that lease held and leaves a write-ahead record;
there is deliberately no automatic rollback, rerun, activation or lease release.
"""
import argparse
import collections
import copy
import datetime
from decimal import Decimal
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import uuid
import yaml

W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
X = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
A = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
AX = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z')
D = A / 'resource-isolation-20260924-v1'
AUTH_SHA = '4026c141ff9bd06f31734c0a43122327b359c35bd847670f641961df9ce81f47'
N1W_SHA = '445306c7023e0cba6a5affeaf2afab5af91bb393b9b39bf64341ba17b2c11258'
HEADS = {'W': 'f6a9ab04c0f184bbe2f8c837b33492835bc8fec9', 'X': 'c75ff0f4eb4c8ae23dfc41b5f7449e99c06ff9ee'}
PLANS = {'W': (A/'continuation_20260923/n4-dev-v1/plan.frozen.json', '8f9c058cd0e87da1ba8a108c1d778b6da445bba5a87b5c212351d7145770c5ed'),
         'X': (X/'data/qd-ed-n1w-approved-plan.json', 'fa3408e75f49385178987db533b9d00d4fefb8f1dfa24647fd245cf9fe5980c2')}
JOURNALS = ('attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl', 'gpu-hour-reservation-ledger.jsonl')
LOCKS = ('qd-ed-state.lock', 'qd-ed-runner.lock')
BUCKETS = ('baseline', 'development', 'validation', 'formal', 'recovery')
CAPS = {'W': dict(zip(BUCKETS, (20,100,60,40,20))), 'X': dict(zip(BUCKETS, (13,125,60,40,12)))}
DYNAMIC = ('dispatched','aborted','valid','invalid','completed','running','gpu_hours_consumed')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    with Path(path).open('rb') as stream:
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def unique_pairs(items):
    value = {}
    for key,item in items:
        require(key not in value, 'duplicate JSON field')
        value[key] = item
    return value


def parse(data):
    return json.loads(data, object_pairs_hook=unique_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(RuntimeError('nonfinite JSON constant')))


def read_json(path):
    return parse(Path(path).read_bytes())


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def durable_new(path, data):
    """Publish a complete owner-only file without exposing partial bytes."""
    path = Path(path)
    require(not path.exists() and not path.is_symlink(), 'new artifact already exists: '+str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        # Hard-link is atomic and refuses an unexpectedly existing destination.
        os.link(temp, path); temp.unlink(); fsync_dir(path.parent)
    finally:
        if temp.exists(): temp.unlink()


def owner_of(output, artifacts):
    require(isinstance(output,str) and Path(output).is_absolute(), 'missing/relative group output_dir')
    path = Path(output).resolve()
    matches = [key for key,root in artifacts.items() if path.is_relative_to(Path(root).resolve())]
    require(len(matches)==1, 'ambiguous or unowned historical output_dir')
    return matches[0]


def partition(data, *, health=False, artifacts=None):
    """Keep whole groups and each original line byte-for-byte in global line order."""
    artifacts = artifacts or {'W':A, 'X':AX}
    idkey = 'resource_id' if health else 'attempt_id'
    terminal = {'completed','aborted'} if health else {'valid','aborted'}
    rows=[]; groups=collections.OrderedDict()
    for line_number,line in enumerate(data.splitlines(keepends=True),1):
        require(line.endswith(b'\n') and line.strip(), 'blank/truncated journal line')
        event=parse(line)
        require(isinstance(event,dict) and isinstance(event.get(idkey),str), 'invalid event identifier')
        identifier=event[idkey]; rows.append((identifier,line))
        groups.setdefault(identifier,[]).append((line_number,line,event))
    owners={}; manifest=[]
    for identifier,items in groups.items():
        events=[item[2] for item in items]; first=events[0]; last=events[-1]
        phases=[e.get('event') for e in events]
        allowed=[['reserved','aborted'], ['reserved','dispatched','aborted'],
                 ['reserved','dispatched','completed' if health else 'valid']]
        require(phases in allowed and last.get('event') in terminal, 'unfinished/illegal event group')
        require(all(e.get('output_dir')==first.get('output_dir') for e in events), 'group output_dir changed')
        require(all(e.get('retry_of')==first.get('retry_of') for e in events), 'group retry_of changed')
        if not health:
            require(first.get('budget_bucket') in BUCKETS and all(e.get('budget_bucket')==first['budget_bucket'] for e in events), 'group budget bucket changed')
        seconds=last.get('gpu_process_wall_seconds')
        require(type(seconds) in (int,float) and math.isfinite(seconds) and seconds>=0, 'terminal duration missing/invalid')
        owner=owner_of(first.get('output_dir'),artifacts); owners[identifier]=owner
        manifest.append({'id':identifier,'owner':owner,'output_dir':first['output_dir'],
            'source_line_numbers':[item[0] for item in items],
            'source_line_sha256':[digest_bytes(item[1]) for item in items],
            'group_sha256':digest_bytes(b''.join(item[1] for item in items)),
            'event_count':len(items),'dispatched':'dispatched' in phases,
            'budget_bucket':None if health else first['budget_bucket'],
            'gpu_process_wall_seconds':seconds,'retry_of':first.get('retry_of')})
    output={key:b''.join(line for identifier,line in rows if owners[identifier]==key) for key in artifacts}
    require(sum(len(blob) for blob in output.values())==len(data), 'partition byte conservation failed')
    require(sum(len(blob.splitlines()) for blob in output.values())==len(rows), 'partition event conservation failed')
    cross=[]
    for item in manifest:
        parent=item['retry_of']
        if parent is not None:
            require(parent in owners, 'historical retry predecessor absent from original shared snapshot')
            if owners[parent]!=item['owner']:
                parent_record=next(m for m in manifest if m['id']==parent)
                cross.append({'child_id':item['id'],'child_owner':item['owner'],'parent_id':parent,
                    'parent_owner':owners[parent],'parent_group_sha256':parent_record['group_sha256'],
                    'parent_source_line_numbers':parent_record['source_line_numbers'],
                    'scope':'lineage-only reference into immutable original archive; not a second charge'})
    return output,manifest,cross


def conservation(original, manifests, partitions):
    """Resource-only proof: exact bytes, event/group/dispatch counts and Decimal costs."""
    all_ids=[m['id'] for m in manifests]
    require(len(all_ids)==len(set(all_ids)), 'duplicate resource group')
    total=sum((Decimal(str(m['gpu_process_wall_seconds'])) for m in manifests),Decimal(0))
    owners={}
    for owner,data in partitions.items():
        group=[m for m in manifests if m['owner']==owner]
        owners[owner]={'groups':len(group),'events':len(data.splitlines()),'bytes':len(data),
            'dispatched':sum(m['dispatched'] for m in group),
            'seconds_decimal':str(sum((Decimal(str(m['gpu_process_wall_seconds'])) for m in group),Decimal(0))),
            'sha256':digest_bytes(data)}
    require(sum(Decimal(v['seconds_decimal']) for v in owners.values())==total, 'GPU cost conservation failed')
    return {'original_sha256':digest_bytes(original),'original_bytes':len(original),
        'original_groups':len(manifests),'original_events':len(original.splitlines()),
        'original_dispatched':sum(m['dispatched'] for m in manifests),
        'original_seconds_decimal':str(total),'partitions':owners,'exact_once':True}


def snapshot(episode_data, health_data):
    # Same dynamic accounting as both frozen runners; no authority/cap mutation.
    result={'dispatched':0,'aborted':0,'valid':0,'invalid':0,'completed':0,'running':0,
        'gpu_hours_consumed':0.,'by_bucket':dict.fromkeys(BUCKETS,0),'reserved_attempts':0,
        'gpu_hours_by_bucket':dict.fromkeys(BUCKETS,0.),'gpu_healthcheck_hours':0.,'gpu_healthcheck_inflight':0}
    for data,health in ((episode_data,False),(health_data,True)):
        groups=collections.OrderedDict()
        for line in data.splitlines():
            e=parse(line);groups.setdefault(e['resource_id' if health else 'attempt_id'],[]).append(e)
        for group in groups.values():
            final=group[-1]
            require(final['event'] in ({'completed','aborted'} if health else {'valid','aborted'}), 'unsettled private snapshot')
            seconds=final['gpu_process_wall_seconds']
            if health: result['gpu_healthcheck_hours']+=seconds/3600;continue
            result['reserved_attempts']+=1
            dispatched=next((e for e in group if e['event']=='dispatched'),None)
            if dispatched:
                result['dispatched']+=1;result['by_bucket'][dispatched['budget_bucket']]+=1
            if final['event']=='valid':
                result['completed']+=1;result['valid' if final.get('outcome_valid') is True else 'invalid']+=1
            else: result['aborted']+=1
            result['gpu_hours_consumed']+=seconds/3600
            result['gpu_hours_by_bucket'][final['budget_bucket']]+=seconds/3600
    result['gpu_hours_consumed']+=result['gpu_healthcheck_hours']
    result['gpu_hours_by_bucket']['recovery']+=result['gpu_healthcheck_hours']
    return result


def new_state(original, owner, stats, *, auth_ref, worktree, archive_ref):
    require(owner in {'W','X'}, 'unknown state owner')
    require(original.get('run_name')==W.name and Path(original.get('artifacts','')).resolve()==(A if owner=='W' else AX), 'state run/artifact owner identity differs')
    s=copy.deepcopy(original); budget=s['budget']
    require(s.get('resource_isolation',{}).get('status')=='DRAINING_FOR_USER_AUTHORIZED_ISOLATION'
        and s['resource_isolation'].get('authorization')==auth_ref, 'state not authorized/draining')
    require(budget.get('gpu_hour_reservations')=={'validation':14.,'formal':10.}, 'protected hours changed')
    if owner=='X':
        require(budget.get('n1w_authorization',{}).get('sha256')==N1W_SHA and budget.get('n1v_authorization') is None,
                'X exact N1W authority missing/conflicting')
        require(budget.get('reserved')==CAPS['X'] and budget.get('max_episode_attempts')==250 and budget.get('max_gpu_hours')==48,
                'X current approved caps differ')
    else:
        for k in ('n1v_authorization','n1w_authorization'):
            budget.pop(k,None)  # Full original state bytes are archived, never destroyed.
    if owner=='W':
        budget.pop('attempt_reallocation',None)
    elif 'attempt_reallocation' in budget:
        budget['attempt_reallocation']={**budget['attempt_reallocation'],
            'scope':'Historical approved allocation retained for this owning study only; no cross-study priority or authority',
            'cross_study_authority':False,'superseded_by':auth_ref}
    budget['resource_isolation_authorization']=copy.deepcopy(auth_ref)
    budget.update(max_episode_attempts=240 if owner=='W' else 250,max_gpu_hours=48.,reserved=copy.deepcopy(CAPS[owner]))
    for key in DYNAMIC: budget[key]=stats[key]
    s['runner']={key:stats[key] for key in ('by_bucket','reserved_attempts','gpu_hours_by_bucket','gpu_healthcheck_hours','gpu_healthcheck_inflight')}
    s['runner'].update(last_attempt_id=stats.get('last_attempt_id'),last_event=stats.get('last_event'))
    gpu=3 if owner=='W' else 2;s['gpu_pool']=[gpu];s['max_concurrent_gpu_workers']=1
    policy=copy.deepcopy(s.get('authorized_gpu_selection',{}))
    policy.update(candidate_indices=[gpu],selected_physical_gpu=gpu,single_exclusive_worker=True,rescan_if_unavailable=True)
    s['authorized_gpu_selection']=policy
    for key,value in list(s.items()):
        if isinstance(value,dict) and (('priority' in key and not key.endswith('_superseded_by')) or key=='external_resource_hold'):
            value.update(active=False,superseded_by=auth_ref)
            if key=='external_resource_hold': value['do_not_auto_resume']=False
    if isinstance(s.get('shared_budget_reconciliation'),dict):
        s['shared_budget_reconciliation'].update(active=False,superseded_by=auth_ref)
    s['external_resource_hold']={'active':False,'do_not_auto_resume':False,'superseded_by':auth_ref,
        'reason':'Latest explicit user authority ends cross-study holds and priority; each study owns its private budget/locks. Previous hold details remain in the original state archive.',
        'historical_state_archive':archive_ref}
    if owner=='X':
        migration=s.setdefault('execution_migration',{})
        old=copy.deepcopy(migration)
        migration.clear();migration.update(same_study_budget=False,
            current_private_journal_root=str(Path(worktree)/'data'),superseded_by=auth_ref,
            historical_shared_migration={'original':old,'active':False,'archived_state':archive_ref})
    s['resource_isolation']={**s['resource_isolation'],'status':'MIGRATED_PENDING_VALIDATION',
        'authorization':auth_ref,'owning_worktree_after_migration':str(worktree),
        'write_scope':'Only the owning study writes its state/journals/locks; no peer mutation or preemption',
        'historical_state_archive':archive_ref,'private_budget':True,'max_owned_gpu_workers':1}
    require(stats['dispatched']<=budget['max_episode_attempts'] and stats['gpu_hours_consumed']<=48
        and all(stats['by_bucket'][k]<=budget['reserved'][k] for k in BUCKETS), 'private historical costs exceed approved caps')
    return s


def proc_metadata(pid):
    root=Path('/proc')/str(pid)
    fields=(root/'stat').read_text().rsplit(')',1)[1].split()
    return {'pid':pid,'state':fields[0],'ppid':int(fields[1]),'pgid':int(fields[2]),
        'session_id':int(fields[3]),'proc_start_ticks':fields[19],
        'uid':root.stat().st_uid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def verify_lease(directory=D, root=W, *, expected_process=None):
    lease=read_json(directory/'migration-lease.json'); lock=root/'data/qd-ed-runner.lock'
    require(lease.get('schema')=='two-study-migration-lease-v1' and lease.get('status')=='OLD_SHARED_RUNNER_LEASE_HELD_FOR_MIGRATION'
        and lease.get('lock_path')==str(lock) and not lock.is_symlink(), 'migration lease schema/path differs')
    process=proc_metadata(lease['pid']); st=lock.stat()
    require(process['pid']!=os.getpid() and process['state'] not in {'Z','X'} and process['uid']==os.getuid()
        and process['boot_id']==lease['boot_id'] and st.st_ino==lease['lock_inode'], 'lease process/boot/inode differs')
    if expected_process: require(process['proc_start_ticks']==expected_process['proc_start_ticks'] and process['pid']==expected_process['pid'], 'lease PID reused')
    # Only the public executable basename is inspected; no environment is read or stored.
    argv=(Path('/proc')/str(process['pid'])/'cmdline').read_bytes().split(b'\0')
    require(any(Path(x.decode()).name=='drain-and-hold-v2.py' for x in argv if x), 'lease is not the reviewed drain helper')
    identity=f'{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}'
    lines=[line.split() for line in Path('/proc/locks').read_text().splitlines()]
    require(any(len(parts)>6 and parts[1:4]==['FLOCK','ADVISORY','WRITE'] and parts[4]==str(process['pid']) and parts[5]==identity for parts in lines), 'helper does not hold actual old runner flock')
    with lock.open('rb') as stream:
        try: fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: pass
        else:
            fcntl.flock(stream,fcntl.LOCK_UN);raise RuntimeError('old runner flock unexpectedly obtainable')
    drain=read_json(directory/'drain-result.json')
    require(digest(directory/'drain-result.json')==lease['drain_result_sha256'] and drain['authorization_sha256']==AUTH_SHA
        and drain['inflight_attempts']==drain['inflight_healthchecks']==[] and drain['active_episode_interrupted'] is False
        and drain['latest_terminal_artifact_matches_journal'] is True, 'drain boundary evidence differs')
    old=Path('/proc')/str(drain['supervisor_pid'])
    require(not old.exists() or proc_metadata(drain['supervisor_pid'])['state'] in {'Z','X'}, 'old supervisor still live')
    return {'lease':lease,'helper':process,'lock_device':st.st_dev,'lock_inode':st.st_ino,'lock_identity':identity,
        'drain_result_sha256':lease['drain_result_sha256']}


def immutable_inventory(states):
    files={}; heads={}
    for owner,root in (('W',W),('X',X)):
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
        require(head==HEADS[owner], 'frozen source HEAD changed: '+owner);heads[owner]=head
        path,sha=PLANS[owner];require(digest(path)==sha, 'frozen plan changed: '+owner)
        plan=read_json(path)
        require(plan['source_commit']==head and Path(plan['worktree']).resolve()==root and plan.get('frozen') is True,'frozen plan identity differs')
        require(Path(plan['artifact_root']).resolve()==(A if owner=='W' else AX), 'plan artifact ownership differs')
        files[str(path)]=sha
        for entry in plan['code_files']:
            relative=Path(entry['path']); require(not relative.is_absolute() and (root/relative).resolve().is_relative_to(root),'unsafe code path')
            source=root/relative;require(digest(source)==entry['sha256'],'frozen source bytes differ: '+str(relative));files[str(source)]=entry['sha256']
        for prefix in ('profiles','runtime_manifest','runtime_inventory','seed_plan'):
            source=Path(plan[prefix+'_path']);sha=plan[prefix+'_sha256']
            require(digest(source)==sha,'frozen '+prefix+' differs');files[str(source)]=sha
        for ref in plan.get('candidate_profiles',{}).values():
            source=Path(ref['path']);source=source if source.is_absolute() else root/source
            require(source.resolve().is_relative_to(root) and digest(source)==ref['sha256'],'candidate profile changed');files[str(source)]=ref['sha256']
    pointer=W/'data/qd-ed-shared-resource-active.json'
    require(digest(pointer)=='0fc8c4f4e086bfa8bc5573264d2f21680709f7764beeab380d72efdd8df76af5','N4 resource pointer changed')
    files[str(pointer)]=digest(pointer)
    ref=read_json(pointer)['active_contract']
    require(ref['sha256']=='26972958be5372d8dffd304abcba844259e882588ca86a20c3b703e9446768b5' and digest(ref['path'])==ref['sha256'],'N4 resource contract changed')
    files[ref['path']]=ref['sha256']
    ref=states['X']['budget']['n1w_authorization']
    require(ref['sha256']==N1W_SHA and digest(ref['path'])==N1W_SHA,'N1W authority bytes differ');files[ref['path']]=ref['sha256']
    return {'heads':heads,'files':[{'path':p,'sha256':s} for p,s in sorted(files.items())]}


def verify_immutable(inventory):
    for owner,root in (('W',W),('X',X)):
        require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==inventory['heads'][owner], 'source HEAD changed during migration')
    require(all(digest(f['path'])==f['sha256'] for f in inventory['files']), 'immutable source/plan/runtime/authority changed during migration')


def migrate():
    require(Path(__file__).resolve()==D/'migrate-private-resources.py','execute only the reviewed installed artifact')
    authority=D/'authorization.json';require(digest(authority)==AUTH_SHA,'explicit user authorization differs')
    auth=read_json(authority);auth_ref={'path':str(authority),'sha256':AUTH_SHA}
    require(auth['schema']=='explicit-user-two-study-resource-isolation-v1' and auth['max_owned_workers_combined']==2
        and auth['max_owned_workers_per_study']==1,'authorization schema/worker allowance differs')
    for owner,index,root,artifact,gpu in [('W',0,W,A,3),('X',1,X,AX,2)]:
        study=auth['studies'][index]
        require(study['worktree']==str(root) and study['artifact_root']==str(artifact) and study['physical_gpu']==gpu
            and study['max_episode_attempts']==(240 if owner=='W' else 250) and study['max_gpu_hours']==48
            and study['bucket_caps']==CAPS[owner],'independent study authority differs')
    require(not any((D/name).exists() for name in ('archive','migration-prepared.json','migration.json','migration-partial.json')), 'migration already prepared; manual review required, never automatic rerun')
    lease=verify_lease(); old_state_lock=W/'data/qd-ed-state.lock'
    require(not old_state_lock.is_symlink(),'W state lock must remain original local file')
    with old_state_lock.open('rb') as held_state:
        fcntl.flock(held_state,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old_lock_identity=(old_state_lock.stat().st_dev,old_state_lock.stat().st_ino)
        lease=verify_lease(expected_process=lease['helper'])
        states_raw={owner:(root/'research-state.yaml').read_bytes() for owner,root in [('W',W),('X',X)]}
        states={owner:yaml.safe_load(data) for owner,data in states_raw.items()}
        inventory=immutable_inventory(states)
        shared={name:(W/'data'/name).read_bytes() for name in JOURNALS}
        require(shared[JOURNALS[2]]==b'','nonempty reservation ledger requires explicit separate schema review')
        links=[]
        for name in JOURNALS+LOCKS:
            target=W/'data'/name;p=X/'data'/name
            require(p.is_symlink() and p.resolve()==target.resolve() and not target.is_symlink(),'expected five shared links differ')
            for q in (target,p.parent,W/'research-state.yaml',X/'research-state.yaml'):
                require(q.stat().st_uid==os.getuid(),'migration current user does not own resource path')
            st=p.stat();links.append({'path':str(p),'readlink':os.readlink(p),'resolved':str(p.resolve()),
                'device':st.st_dev,'inode':st.st_ino,'mode':stat.S_IMODE(st.st_mode),'uid':st.st_uid})
        private={owner:{JOURNALS[2]:b''} for owner in ('W','X')};group_manifests={};proofs={};cross=[]
        for name,health in ((JOURNALS[0],False),(JOURNALS[1],True)):
            parts,groups,references=partition(shared[name],health=health)
            group_manifests[name]=groups;proofs[name]=conservation(shared[name],groups,parts)
            cross.extend({**item,'source_archive':str(D/'archive/shared'/name)} for item in references)
            for owner in private:private[owner][name]=parts[owner]
        # Required current engineering proof events must remain in their owner ledger.
        for owner in ('W','X'):
            plan=read_json(PLANS[owner][0]);runtime=read_json(plan['runtime_manifest_path'])
            ids={m['id'] for m in group_manifests[JOURNALS[1]] if m['owner']==owner}
            required={runtime['cuda_egl_probe']['resource_id']}
            if owner=='W': required|={h['resource_id'] for h in plan['n4_cohort']['health_resources']}
            require(required<=ids,'partition would lose an existing readiness proof or N4 cost reference')
        stats={};prepared_states={}
        for owner,root in [('W',W),('X',X)]:
            stats[owner]=snapshot(private[owner][JOURNALS[0]],private[owner][JOURNALS[1]])
            final=parse(private[owner][JOURNALS[0]].splitlines()[-1]) if private[owner][JOURNALS[0]] else {}
            stats[owner].update(last_attempt_id=final.get('attempt_id'),last_event=final.get('event'))
            archive_ref={'path':str(D/'archive'/('state-'+owner+'.yaml')),'sha256':digest_bytes(states_raw[owner])}
            prepared_states[owner]=new_state(states[owner],owner,stats[owner],auth_ref=auth_ref,worktree=root,archive_ref=archive_ref)
        archive=D/'archive'; archive.mkdir(mode=0o700)
        for name,data in shared.items():durable_new(archive/'shared'/name,data)
        for owner,data in states_raw.items():durable_new(archive/('state-'+owner+'.yaml'),data)
        durable_new(archive/'original-links-and-lease.json',json_bytes({'links':links,'lease':lease}))
        archives=[{'path':str(p),'sha256':digest(p)} for p in sorted(archive.rglob('*')) if p.is_file()]
        stages=[]
        for owner,root in [('W',W),('X',X)]:
            for name in JOURNALS:
                destination=root/'data'/name;temp=destination.with_name('.'+name+'.private-migration-staged')
                durable_new(temp,private[owner][name]);stages.append({'owner':owner,'staged':str(temp),'destination':str(destination),'sha256':digest(temp),'kind':'journal'})
            if owner=='X':
                for name in LOCKS:
                    destination=root/'data'/name;temp=destination.with_name('.'+name+'.private-migration-staged')
                    durable_new(temp,b'');stages.append({'owner':owner,'staged':str(temp),'destination':str(destination),'sha256':digest(temp),'kind':'lock'})
            destination=root/'research-state.yaml';temp=root/'research-state.yaml.private-migration-staged'
            durable_new(temp,yaml.safe_dump(prepared_states[owner],sort_keys=False).encode())
            stages.append({'owner':owner,'staged':str(temp),'destination':str(destination),'sha256':digest(temp),'kind':'state'})
        prepared={'schema':'two-study-resource-migration-v1','status':'PREPARED_NOT_ACTIVATED','utc':now(),
            'authorization':auth_ref,'script_sha256':digest(__file__),'lease':lease,'archive':archives,
            'group_owner_manifest':group_manifests,'cross_owner_retry_references':cross,'partition_conservation':proofs,
            'immutable_identities':inventory,'private_resource_statistics':stats,'replacements':stages,
            'authority_scope':'Latest explicit user authorization prospectively replaces shared budget/lease semantics only. Original frozen N4 shared-named contract remains immutable numerical/scientific provenance; it did not originally authorize independent budgets.',
            'scientific_task_results_interpreted_or_reclassified':False,'worker_activation_authorized_by_this_record':False,
            'old_W_locks_preserved':{'runner_device':lease['lock_device'],'runner_inode':lease['lock_inode'],'state_device':old_lock_identity[0],'state_inode':old_lock_identity[1]}}
        durable_new(D/'migration-prepared.json',json_bytes(prepared));applied=[]
        try:
            verify_immutable(inventory)
            require(all((W/'data'/n).read_bytes()==data for n,data in shared.items()),'shared journal changed after preparation')
            require(all((root/'research-state.yaml').read_bytes()==states_raw[o] for o,root in [('W',W),('X',X)]),'state changed after preparation')
            for item in stages:
                verify_lease(expected_process=lease['helper'])
                require(digest(item['staged'])==item['sha256'],'staged bytes changed')
                os.replace(item['staged'],item['destination']);fsync_dir(Path(item['destination']).parent)
                applied.append(item['destination'])
                durable_new(D/('migration-progress-%02d.json'%len(applied)),json_bytes({'schema':'two-study-migration-progress-v1','applied':list(applied),'authorization_sha256':AUTH_SHA}))
            verify_immutable(inventory);verify_lease(expected_process=lease['helper'])
            require((old_state_lock.stat().st_dev,old_state_lock.stat().st_ino)==old_lock_identity,'W state lock inode changed')
            for item in stages:
                p=Path(item['destination'])
                require(not p.is_symlink() and digest(p)==item['sha256'] and p.stat().st_uid==os.getuid(),'private destination differs')
            for name in LOCKS:
                require((W/'data'/name).stat().st_ino!=(X/'data'/name).stat().st_ino,'locks still share inode')
            final={**prepared,'status':'MIGRATED_PENDING_VALIDATION','completed_utc':now(),
                'source_plan_runtime_pointer_contract_unchanged':True,'exact_owner_partition_verified':True,
                'old_runner_lease_still_held':True,'activation_or_release_performed':False}
            durable_new(D/'migration.json',json_bytes(final))
            print(json.dumps({'status':final['status'],'migration_path':str(D/'migration.json'),
                'migration_sha256':digest(D/'migration.json'),'resource_statistics':{o:{k:stats[o][k] for k in ('dispatched','gpu_hours_consumed','by_bucket','gpu_healthcheck_inflight')} for o in stats}},sort_keys=True))
        except BaseException as exc:
            durable_new(D/'migration-partial.json',json_bytes({'status':'MIGRATION_PARTIAL_REQUIRES_ROOT_REVIEW','applied':applied,
                'error_type':type(exc).__name__,'authorization':auth_ref,'do_not_release_old_lease':True,'automatic_retry_or_rollback':False}))
            raise
        finally:fcntl.flock(held_state,fcntl.LOCK_UN)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute-reviewed',action='store_true');p.add_argument('--expected-script-sha256',required=True)
    args=p.parse_args();require(args.execute_reviewed and args.expected_script_sha256==digest(__file__),'explicit reviewed script identity required')
    migrate()


if __name__=='__main__':main()
