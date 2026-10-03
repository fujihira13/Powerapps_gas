"""Generate approved server-parent management; preserve fresh other definitions.

The legacy builder supplies shared layout/transaction UI scaffolding only.
This entry point is the current generator. Its output is not a saved app.
"""
import argparse
import re
import shutil
from pathlib import Path
import yaml
from prepare_environment_management_canvas import manage_screen, FLOW, nodes
from prepare_server_list_navigation import add_scroll_focus, find, MultilineDumper

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'outputs/environment-management-20261003/server-first'

def reverse_roles(value):
    mapping = {'Environment':'Server', 'Server':'Env', 'Env':'Server',
               'environment':'server', 'server':'environment', '環境':'サーバー', 'サーバー':'環境',
               'srvM05':'envM05','envM05':'srvM05', 'ViewServers':'ViewEnvironments'}
    for prefix in ('add','rename','end','reactivate'):
        mapping[prefix+'Server']=prefix+'Environment'
        mapping[prefix+'Environment']=prefix+'Server'
    mapping[FLOW]=FLOW
    mapping['環境・サーバーの管理']='環境・サーバーの管理'
    pattern=re.compile('|'.join(re.escape(x) for x in sorted(mapping,key=len,reverse=True)))
    def transform(obj):
        if isinstance(obj,str): return pattern.sub(lambda m:mapping[m.group()],obj).replace('M05','M06')
        if isinstance(obj,dict): return {transform(k):transform(v) for k,v in obj.items()}
        if isinstance(obj,list): return [transform(x) for x in obj]
        return obj
    return transform(value)

def manage_server_first_screen():
    doc=reverse_roles(add_scroll_focus(manage_screen()))
    screen=doc['Screens']['Screen5']; n=nodes(screen)
    # Parent server tab text is longer than the legacy environment tab text.
    n['srvM06TabActive']['Properties']['Width']='=148'
    n['srvM06TabEnded']['Properties'].update(Width='=180', X='=If(Parent.Width < 390, 18, 178)')
    heading=n['lblM06ServerContext']['Properties']
    heading.update(Text='=If(IsBlank(varM06Server), "環境", varM06Server & "の環境")',
                   Height='=42', Width='=envM06Panel.Width - 180', Size='=20', FontWeight='=FontWeight.Bold',
                   Y='=conM06Center.Y + pnlM06Lists.Y + envM06Panel.Y + 18')
    panel=n['envM06Panel']
    panel['Children']=[child for child in panel['Children'] if 'envM06Title' not in child]
    for name, base in [('envM06TabActive',74),('envM06TabEnded',74),('envM06List',132)]:
        extra=' + If(Parent.Width < 390, 48, 0)' if name!='envM06TabActive' else ''
        n[name]['Properties']['Y']=f'={base}{extra} + Max(0, lblM06ServerContext.Height - 42)'
    n['lblM06EnvInput']['Properties']['Text']='="対象の環境名"'
    n['txtM06Env']['Properties']['AccessibleLabel']='="対象の環境名"'
    n['lblM06DialogTitle']['Properties']['Text']=n['lblM06DialogTitle']['Properties']['Text'].replace('"addEnvironment", "環境を追加"', '"addEnvironment", varM06OldServer & "に環境を追加"')
    n['lblM06ConfirmBody']['Properties']['Text']='''=Switch(varM06Op,
"renameServer", "このサーバー内のすべての環境に適用されます。" & Char(10) & "ログに書かれているサーバー名も「" & varM06NewServer & "」になっていることを確認してください。",
"renameEnvironment", "ログに書かれている環境名も「" & varM06NewEnv & "」になっていることを確認してください。",
"endServer", varM06OldServer & "を使用終了にしますか？ このサーバー内のすべての環境が使用できなくなります。",
"endEnvironment", varM06OldEnv & "を使用終了にしますか？ このサーバーでは、この環境が使用できなくなります。",
"reactivateServer", varM06OldServer & "を再び使用しますか？",
"reactivateEnvironment", varM06OldEnv & "を再び使用しますか？", "")'''
    commit=n['btnM06Commit']['Properties']
    commit['OnSelect']=commit['OnSelect'].replace('{operation: varM06Op,', '{managementModel: "server-first-v1", operation: varM06Op,')
    # Unknown outcomes and an old cached screen must read again before another write.
    for obj in n.values():
        p=obj.get('Properties',{})
        for prop,value in list(p.items()):
            if isinstance(value,str):
                p[prop]=value.replace('"読み直して" in varM06Error', '("読み直して" in varM06Error || "画面を開き直して" in varM06Error)')
    serialized=yaml.dump(doc,Dumper=MultilineDumper,allow_unicode=True,sort_keys=False,width=10000)
    assert FLOW in serialized and 'server-first-v1' in serialized
    assert 'ThisItem.Environment' not in serialized and 'M05' not in serialized
    return doc

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--baseline', type=Path, default=WORK/'canvas-baseline'); parser.add_argument('--output',type=Path,default=WORK/'canvas-candidate'); args=parser.parse_args()
    sources=list(args.baseline.glob('*.pa.yaml'))
    if len(sources)!=7: raise RuntimeError('Fresh seven-file baseline required.')
    args.output.mkdir(parents=True,exist_ok=True)
    for path in sources: shutil.copy2(path,args.output/path.name)
    doc=manage_server_first_screen()
    path=args.output/'Screen5.pa.yaml'
    path.write_text(yaml.dump(doc,Dumper=MultilineDumper,allow_unicode=True,sort_keys=False,width=10000),encoding='utf-8')
    assert yaml.safe_load(path.read_text(encoding='utf-8'))==doc
    for source in sources:
        if source.name!='Screen5.pa.yaml': assert source.read_bytes()==(args.output/source.name).read_bytes()
    print('Prepared Screen5 server-first-v1; other six definitions copied byte-for-byte.')

if __name__=='__main__': main()
