"""Compare two complete audited cohorts without modifying any original receipt."""
from pathlib import Path
import argparse,copy,hashlib,json,math
import yaml
MODES=('eds','vls','eds_qd')
LOW_SHA='a67ee5e13f7563b86ea8fadd9e55dd5d5b80f53601cdd1e65f1af72a2c2402eb'

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def strip_paths(config):
    c=copy.deepcopy(config)
    c['hydra']['run']['dir']=None;c['main']['eds_eval']['job_id']=None
    return c

def compare(low_path,ultra_path):
    if digest(low_path)!=LOW_SHA:raise ValueError('Previous sealed low report hash mismatch')
    low=json.loads(Path(low_path).read_text());ultra=json.loads(Path(ultra_path).read_text())
    if not low['all_cohorts_valid'] or not ultra['all_cohorts_valid']:raise ValueError('Comparison requires complete valid cohorts')
    report={'schema':'steering_low_ultra_paired_comparison_v1','low_report_sha256':digest(low_path),'ultra_report_sha256':digest(ultra_path),'low_commit':low['common_commit'],'ultra_commit':ultra['common_commit'],'modes':{},'limits':['One fixed seed per task; online responses and service date vary.','Differences describe this effort setting change, not general ability or proven causality.','Reported worker elapsed and service latency are wall time, not active GPU hours.']}
    for mode in MODES:
        l,u=low['runs'][mode],ultra['runs'][mode]
        lc=strip_paths(yaml.safe_load((Path(l['run_dir'])/'resolved-config.yaml').read_text()));uc=strip_paths(yaml.safe_load((Path(u['run_dir'])/'resolved-config.yaml').read_text()))
        for role in ('gemini','vlm_agent'):
            assert lc['perception'][role]['reasoning_effort']=='low'
            assert uc['perception'][role]['reasoning_effort']=='ultra'
            uc['perception'][role]['reasoning_effort']='low'
        if lc!=uc:raise ValueError('Unexpected scientific configuration difference for '+mode)
        assert len(l['tasks'])==len(u['tasks'])==10 and l['accepted'] and u['accepted']
        paired=[];gains=[];losses=[];both=[];neither=[]
        for a,b in zip(l['tasks'],u['tasks']):
            assert a['task_id']==b['task_id'] and a['seed']==b['seed'] and a['accepted'] and b['accepted']
            assert type(a['success']) is bool and type(b['success']) is bool
            t=a['task_id'];category='both_success' if a['success'] and b['success'] else ('gain' if b['success'] else ('loss' if a['success'] else 'both_failure'))
            {'gain':gains,'loss':losses,'both_success':both,'both_failure':neither}[category].append(t)
            paired.append({'task_id':t,'seed':a['seed'],'low':a['success'],'ultra':b['success'],'change':category,'low_actions':a['executed_action_rows'],'ultra_actions':b['executed_action_rows'],'low_video':a['videos'],'ultra_video':b['videos']})
        assert sum(x['low'] for x in paired)==l['final_successes'] and sum(x['ultra'] for x in paired)==u['final_successes']
        n=len(gains)+len(losses);p=min(1.,2*sum(math.comb(n,k) for k in range(min(len(gains),len(losses))+1))/2**n) if n else 1.
        report['modes'][mode]={'low':l['final_successes'],'ultra':u['final_successes'],'denominator':10,'change_percentage_points':10*(u['final_successes']-l['final_successes']),'gains':gains,'losses':losses,'both_success':both,'both_failure':neither,'exact_paired_mcnemar_p_two_sided':p,'scientific_config_equal_except_two_effort_fields':True,'gpu_unchanged':l['physical_gpu']==u['physical_gpu'] and l['egl_device_id']==u['egl_device_id'],'tasks':paired,'low_stage':l['stage'],'ultra_stage':u['stage'],'low_worker_seconds':l['timing']['elapsed_s'],'ultra_worker_seconds':u['timing']['elapsed_s'],'low_compute':l['compute_completed_episode_totals'],'ultra_compute':u['compute_completed_episode_totals']}
    return report

def markdown(r):
    lines=['# Low / ultra 完整在线对照','','| 方法 | low | ultra | 变化 | 新增成功任务 | 丢失成功任务 |','|---|---:|---:|---:|---|---|']
    for m,x in r['modes'].items():lines.append(f"| {m} | {x['low']}/10 | {x['ultra']}/10 | {x['change_percentage_points']:+d} pp | {x['gains']} | {x['losses']} |")
    lines+=['','| Task | Seed | EDS low→ultra | VLS low→ultra | EDS+QD low→ultra |','|---|---:|---|---|---|']
    for i in range(10):
        row=r['modes']['eds']['tasks'][i];cells=[]
        for m in MODES:
            a=r['modes'][m]['tasks'][i];cells.append(('成功' if a['low'] else '失败')+' → '+('成功' if a['ultra'] else '失败'))
        lines.append(f"| {row['task_id']} | {row['seed']} | "+' | '.join(cells)+' |')
    lines+=['','所有回合须完整审计有效。每任务一个固定seed；两组均为重新生成reward和在线Stage，日期和回复波动未被隔离，因此该结果不等同于普遍能力或严格因果证明。','',f"Low受测：`{r['low_commit']}`；ultra受测：`{r['ultra_commit']}`。",'']
    return '\n'.join(lines)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--low',type=Path,required=True);a.add_argument('--ultra',type=Path,required=True);a.add_argument('--output-prefix',type=Path,required=True);args=a.parse_args()
    outputs=[args.output_prefix.with_suffix(s) for s in ('.json','.md')]
    if any(p.exists() for p in outputs):raise FileExistsError('Comparison output already exists; preserve previous reports')
    result=compare(args.low,args.ultra);outputs[0].write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');outputs[1].write_text(markdown(result));print({m:{k:x[k] for k in ('low','ultra','gains','losses')} for m,x in result['modes'].items()})
