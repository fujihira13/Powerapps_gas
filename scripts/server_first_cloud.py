"""Preserve/update only approved existing server-first components. No publish."""
import argparse
import copy
import json
from pathlib import Path
import deploy_environment_management as dv

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'outputs/environment-management-20261003/server-first'
dv.OUT = WORK / 'operations'
dv.OUT.mkdir(parents=True, exist_ok=True)
ASSEMBLY = 'bb1aa034-b8be-f111-b377-7ced8d3141aa'
MANAGER = '923d43a8-b8be-f111-b377-7ced8d3141aa'
MAIN = 'ef881fbc-dcb8-f111-b377-7ced8d3141aa'
COLS = 'cr6cb_evidencedestinationid,cr6cb_environment,cr6cb_server,cr6cb_isactive,cr6cb_environmentenabled,cr6cb_driveid,cr6cb_folderid,cr6cb_destinationlabel,versionnumber'

def save(name, value):
    path = WORK / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def settings():
    result = dv.request('cr6cb_evidencedestinations?$select=' + COLS + '&$top=100')
    if '@odata.nextLink' in result: raise RuntimeError('Unexpected settings count; snapshot needs paging.')
    return result['value']

def audit(stage):
    rows=settings(); save('settings-'+stage+'.json', rows)
    original=json.loads((WORK/'cloud-baseline/settings.json').read_text(encoding='utf-8'))
    key='cr6cb_evidencedestinationid'
    attrs=COLS.split(',');attrs.remove('versionnumber')
    current={x[key]:x for x in rows}
    for before in original:
        after=current.get(before[key])
        if after is None or any(before.get(a)!=after.get(a) for a in attrs): raise RuntimeError('Existing registration values changed.')
    new=[x for x in rows if x[key] not in {y[key] for y in original}]
    if len(new)!=2: raise RuntimeError('Expected exactly two approved new settings rows.')
    print('Existing 12 setting values preserved; new rows:',len(new))
    print(json.dumps([{a:x.get(a) for a in (key,'cr6cb_environment','cr6cb_server','cr6cb_isactive','cr6cb_environmentenabled')} for x in new],ensure_ascii=True))
    return rows,new

def guards():
    rows,new=audit('before-guards')
    target=new[0]; group=[r for r in rows if r['cr6cb_server']==target['cr6cb_server']]
    proof=[{'id':r['cr6cb_evidencedestinationid'],'version':str(r['versionnumber'])} for r in group]
    base={'managementModel':'server-first-v1','operation':'renameEnvironment','targetId':target['cr6cb_evidencedestinationid'],'expectedRows':proof,'environment':target['cr6cb_environment'],'server':target['cr6cb_server']}
    cases=[]
    old=copy.deepcopy(base);old.pop('managementModel');cases.append(('old-screen',old,'画面を開き直して'))
    stale=copy.deepcopy(base);stale['expectedRows'][0]['version']='0';cases.append(('stale',stale,'登録内容が変更'))
    duplicate=copy.deepcopy(base);duplicate['environment']=new[1]['cr6cb_environment'];cases.append(('duplicate-environment',duplicate,'同じ環境名'))
    duplicate_server=copy.deepcopy(base);duplicate_server['operation']='renameServer';duplicate_server['server']=next(r['cr6cb_server'] for r in rows if r['cr6cb_evidencedestinationid'] not in {x['cr6cb_evidencedestinationid'] for x in new});cases.append(('duplicate-server',duplicate_server,'同じサーバー名'))
    output=[]
    for name,payload,reason in cases:
        reply=dv.request('cr6cb_ManageEvidenceDestinations','POST',{'RequestJson':json.dumps(payload,ensure_ascii=False)})
        result=json.loads(reply['ResultJson'])
        if result['ok'] or reason not in result['reason']: raise RuntimeError('Unexpected guard result: '+name)
        output.append({'name':name,'result':result})
        print('PASS rejection:',name)
    save('guard-results.json',output)
    after=settings()
    if rows!=after: raise RuntimeError('Rejected requests changed settings.')
    print('Rejected requests made no row changes, including versions.')

def snapshot():
    directory = WORK / 'cloud-baseline'
    if directory.exists() and any(directory.iterdir()): raise RuntimeError('Baseline already exists; preserve it.')
    directory.mkdir(exist_ok=True)
    components = {
        'settings': settings(),
        'assembly': dv.request(f'pluginassemblies({ASSEMBLY})?$select=pluginassemblyid,name,version,publickeytoken,content'),
        'manager': dv.request(f'workflows({MANAGER})?$select=workflowid,name,clientdata,statecode,statuscode'),
        'comparison': dv.request(f'workflows({MAIN})?$select=workflowid,name,clientdata,statecode,statuscode'),
        'api': dv.request("customapis?$select=customapiid,uniquename,_plugintypeid_value&$filter=uniquename eq 'cr6cb_ManageEvidenceDestinations'"),
    }
    for name, value in components.items():
        (directory / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Preserved settings:', len(components['settings']))
    print('Preserved existing assembly, manager flow, comparison flow and API binding.')

def deploy():
    baseline=WORK/'cloud-baseline'
    assembly=json.loads((baseline/'assembly.json').read_text(encoding='utf-8'))
    manager=json.loads((baseline/'manager.json').read_text(encoding='utf-8'))
    registration=json.loads((ROOT/'outputs/environment-management-20261003/implementation/build/pluginassembly-create.json').read_text(encoding='utf-8-sig'))
    if registration['publickeytoken']!=assembly['publickeytoken'] or registration['version']!=assembly['version']:
        raise RuntimeError('Assembly identity differs; stop.')
    current=dv.request(f'pluginassemblies({ASSEMBLY})?$select=pluginassemblyid,name,version,publickeytoken,content')
    if current['content']!=assembly['content']: raise RuntimeError('Assembly changed since snapshot.')
    fresh=dv.request(f'workflows({MANAGER})?$select=workflowid,name,clientdata,statecode,statuscode')
    if fresh['clientdata']!=manager['clientdata']: raise RuntimeError('Manager flow changed since snapshot.')
    definition=json.loads(fresh['clientdata'])
    changed=copy.deepcopy(definition)
    reasons=['登録内容が変更されています。読み直してから操作してください。',
             '管理画面が更新されています。画面を開き直してから操作してください。',
             '同じサーバー名が登録されています。', 'このサーバーに同じ環境名が登録されています。',
             'このサーバーは使用終了です。サーバーを再び使用してから操作してください。',
             'サーバーの使用状態が揃っていません。登録内容を確認してください。',
             '共通保存先の設定が揃っていません。登録は保存していません。']
    expr="if(or(equals(actions('Save_registration')?['status'],'TimedOut'),equals(actions('Manage')?['status'],'TimedOut')),'保存結果を確認できません。読み直してから登録内容を確認してください。',if(not(equals(actions('Check_add')?['status'],'Succeeded')),'保存先の利用を確認できません。登録は保存していません。','登録内容を保存できませんでした。読み直してから状態を確認してください。'))"
    for reason in reversed(reasons): expr=f"if(contains(string(result('Manage')),'{reason}'),'{reason}',{expr})"
    changed['properties']['definition']['actions']['Return_error']['inputs']['body']['result']="@string(setProperty(json('{\"ok\":false,\"rows\":[]}'),'reason',"+expr+'))'
    save('manager-candidate.json',changed)
    # Only the existing assembly content and manager error response are updated.
    dv.request(f'pluginassemblies({ASSEMBLY})','PATCH',{'content':registration['content']},('If-Match:'+current['@odata.etag'],'MSCRM.SolutionUniqueName:'+dv.SOLUTION))
    readback=dv.request(f'pluginassemblies({ASSEMBLY})?$select=content,publickeytoken,version')
    if readback['content']!=registration['content']: raise RuntimeError('Assembly readback mismatch.')
    print('Existing signed assembly updated and read back.')
    dv.request(f'workflows({MANAGER})','PATCH',{'clientdata':json.dumps(changed,ensure_ascii=False,separators=(',',':'))},('If-Match:'+fresh['@odata.etag'],'MSCRM.SolutionUniqueName:'+dv.SOLUTION))
    readback=dv.request(f'workflows({MANAGER})?$select=clientdata,statecode,statuscode')
    if json.loads(readback['clientdata'])!=changed: raise RuntimeError('Manager flow readback mismatch.')
    save('manager-readback.json',readback)
    main=dv.request(f'workflows({MAIN})?$select=clientdata')
    old=json.loads((baseline/'comparison.json').read_text(encoding='utf-8'))
    if main['clientdata']!=old['clientdata']: raise RuntimeError('Comparison flow differs from baseline.')
    print('Manager error response updated and read back; comparison flow unchanged.')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('action', choices=['snapshot','deploy','audit','guards']); parser.add_argument('--approved',action='store_true'); parser.add_argument('--stage',default='readback'); args=parser.parse_args()
    if args.action=='snapshot': snapshot()
    elif args.action=='audit': audit(args.stage)
    elif args.action=='guards' and args.approved: guards()
    elif args.approved: deploy()
    else: raise RuntimeError('Specific Developer write scope must be approved.')

if __name__ == '__main__': main()
