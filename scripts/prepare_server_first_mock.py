"""Build the approved server-first UI prototype with local fixtures only."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'canvas/mock/environment-server-management.html'
BACKUP = ROOT / 'outputs/environment-management-20261003/server-first'

def main():
    BACKUP.mkdir(parents=True, exist_ok=True)
    previous = PAGE.read_text(encoding='utf-8-sig')
    baseline = BACKUP / 'management-mock-before.html'
    if not baseline.exists():
        shutil.copy2(PAGE, baseline)
    head = previous.split('<nav>', 1)[0]
    head = head.replace('  #selectedEnvironment {margin:0 0 16px;font-size:17px;font-weight:600;word-break:break-word}',
        '  #environmentHeading {overflow-wrap:anywhere} .heading h2 {min-width:0;flex:1} .heading button {flex-shrink:0}')
    PAGE.write_text(head + BODY, encoding='utf-8')
    print('Updated local HTML prototype; no cloud operation.')

BODY = r'''<nav><button id="back">進捗一覧に戻る</button></nav>
<main>
  <h1>環境・サーバーの管理</h1>
  <div class="columns">
    <section aria-labelledby="serverHeading">
      <div class="heading"><h2 id="serverHeading">サーバー</h2><button id="addServer" class="primary">サーバーを追加</button></div>
      <div class="tabs" aria-label="表示するサーバー"><button id="serverActive" aria-pressed="true">使用中のサーバー</button><button id="serverInactive" aria-pressed="false">使用終了したサーバー</button></div>
      <div id="servers" class="list" aria-label="サーバー一覧"></div>
    </section>
    <section aria-labelledby="environmentHeading">
      <div class="heading"><h2 id="environmentHeading" tabindex="-1">サーバーAの環境</h2><button id="addEnvironment" class="primary">環境を追加</button></div>
      <div class="tabs" aria-label="表示する環境"><button id="envActive" aria-pressed="true">使用中の環境</button><button id="envInactive" aria-pressed="false">使用終了した環境</button></div>
      <div id="environments" class="list" aria-label="サーバー内の環境一覧"></div>
    </section>
  </div>
</main>
<dialog id="editDialog" aria-labelledby="editTitle">
  <h2 id="editTitle"></h2>
  <form id="editForm" novalidate>
    <div id="serverField"><label for="serverName">サーバー名</label><input id="serverName" autocomplete="off"><p class="error" id="serverError"></p></div>
    <div id="environmentField"><label id="environmentLabel" for="environmentName">対象の環境名</label><input id="environmentName" autocomplete="off"><p class="error" id="environmentError"></p></div>
    <div class="dialog-actions"><button type="button" id="cancelEdit">キャンセル</button><button type="submit" id="saveEdit" class="primary">変更を保存</button></div>
  </form>
</dialog>
<dialog id="confirmDialog" aria-labelledby="confirmTitle">
  <h2 id="confirmTitle">確認</h2><div id="confirmText"></div>
  <div class="dialog-actions"><button id="cancelConfirm">キャンセル</button><button id="confirmSave" class="primary">変更する</button></div>
</dialog>
<script>
  // Local prototype only. No network or persistent storage calls.
  let rows=[
    {id:'a1',server:'サーバーA',environment:'環境A',serverEnabled:true,environmentEnabled:true},
    {id:'a2',server:'サーバーA',environment:'環境B',serverEnabled:true,environmentEnabled:true},
    {id:'b1',server:'サーバーB',environment:'環境C',serverEnabled:true,environmentEnabled:true},
    {id:'b2',server:'サーバーB',environment:'環境D',serverEnabled:true,environmentEnabled:false}
  ];
  let selectedServer='サーバーA',serverFilter=true,envFilter=true,mode='',targetId='',pending=null,busy=false;
  const el=id=>document.getElementById(id),same=(a,b)=>a.trim().toLocaleLowerCase()===b.trim().toLocaleLowerCase();
  const serverRows=()=>rows.filter(r=>same(r.server,selectedServer));
  function rowCard(label,view,rename,toggle,enabled,canReactivate=true){
    let card=document.createElement('div');card.className='item';card.setAttribute('role','group');card.setAttribute('aria-label',label);
    let header=document.createElement('div');header.className='item-header';
    let name=document.createElement('span');name.className='item-name';name.textContent=label;header.append(name);
    if(view){let button=document.createElement('button');button.textContent='環境を見る';button.onclick=view;button.disabled=busy;header.append(button);}
    let actions=document.createElement('div');actions.className='row-actions';
    let renameButton=document.createElement('button');renameButton.textContent='名称を変更';renameButton.onclick=rename;renameButton.disabled=busy;
    let toggleButton=document.createElement('button');toggleButton.textContent=enabled?'使用を終了':'再び使用する';toggleButton.onclick=toggle;toggleButton.disabled=busy||(!enabled&&!canReactivate);
    actions.append(renameButton,toggleButton);card.append(header,actions);return card;
  }
  function selectServer(name,focus=false){selectedServer=name;envFilter=true;render();if(focus){el('environmentHeading').focus();el('environmentHeading').scrollIntoView({block:'nearest'});}}
  function empty(list,text){let p=document.createElement('p');p.className='empty';p.textContent=text;list.append(p);}
  function render(){
    let servers=[...new Set(rows.filter(r=>r.serverEnabled===serverFilter).map(r=>r.server))].sort((a,b)=>a.localeCompare(b,'ja'));
    if(!servers.includes(selectedServer))selectedServer=servers[0]||'';
    el('servers').replaceChildren(...servers.map(n=>rowCard(n,()=>selectServer(n,true),()=>{selectServer(n);openEdit('renameServer');},()=>toggleServer(n),serverFilter)));
    if(!servers.length)empty(el('servers'),'該当するサーバーはありません。');
    let environments=serverRows().filter(r=>r.environmentEnabled===envFilter).sort((a,b)=>a.environment.localeCompare(b.environment,'ja'));
    el('environments').replaceChildren(...environments.map(r=>rowCard(r.environment,null,()=>openEdit('renameEnvironment',r.id),()=>toggleEnvironment(r.id),r.environmentEnabled,!!serverRows()[0]?.serverEnabled)));
    if(!environments.length)empty(el('environments'),'該当する環境はありません。');
    el('environmentHeading').textContent=selectedServer?selectedServer+'の環境':'環境';
    for(let [id,v] of [['serverActive',serverFilter],['serverInactive',!serverFilter],['envActive',envFilter],['envInactive',!envFilter]])el(id).setAttribute('aria-pressed',String(v));
    for(let id of ['serverActive','serverInactive','envActive','envInactive','addServer'])el(id).disabled=busy;
    el('addEnvironment').disabled=busy||!serverRows()[0]?.serverEnabled;
  }
  function openEdit(next,id=''){
    mode=next;targetId=id;let row=rows.find(r=>r.id===id);
    el('serverField').hidden=!(next==='addServer'||next==='renameServer');
    el('environmentField').hidden=next==='renameServer';
    el('environmentLabel').textContent='対象の環境名';
    el('serverName').value=next==='renameServer'?selectedServer:'';
    el('environmentName').value=next==='renameEnvironment'?row.environment:'';
    el('editTitle').textContent=({addServer:'サーバーを追加',addEnvironment:selectedServer+'に環境を追加',renameServer:'サーバー名を変更',renameEnvironment:'環境名を変更'})[next];
    el('saveEdit').textContent=next.startsWith('add')?'追加する':'変更を保存';
    validate();el('editDialog').showModal();
  }
  function validate(){
    let sn=el('serverName').value.trim(),en=el('environmentName').value.trim(),se='',ee='';
    if(mode==='addServer'||mode==='renameServer'){
      if(!sn)se='サーバー名を入力してください。';else if(sn.length>100)se='サーバー名は100文字以内で入力してください。';
      else if(rows.some(r=>same(r.server,sn)&&(mode==='addServer'||!same(r.server,selectedServer))))se='同じサーバー名が登録されています。';
    }
    if(mode!=='renameServer'){
      if(!en)ee='環境名を入力してください。';else if(en.length>100)ee='環境名は100文字以内で入力してください。';
      else if(mode!=='addServer'&&serverRows().some(r=>same(r.environment,en)&&(mode!=='renameEnvironment'||r.id!==targetId)))ee='このサーバーに同じ環境名が登録されています。';
    }
    el('serverError').textContent=se;el('environmentError').textContent=ee;el('saveEdit').disabled=busy||!!se||!!ee;return !se&&!ee;
  }
  function confirm(text,action,label,title='確認'){pending=action;el('confirmTitle').textContent=title;el('confirmText').textContent=text;el('confirmSave').textContent=label;el('confirmDialog').showModal();}
  function save(action){if(busy)return;busy=true;action();busy=false;el('editDialog').close();el('confirmDialog').close();pending=null;render();}
  el('editForm').onsubmit=e=>{
    e.preventDefault();if(busy||!validate())return;
    let sn=el('serverName').value.trim(),en=el('environmentName').value.trim(),oldServer=selectedServer,oldId=targetId;
    let action=()=>{
      if(mode==='addServer'){rows.push({id:crypto.randomUUID(),server:sn,environment:en,serverEnabled:true,environmentEnabled:true});serverFilter=true;envFilter=true;selectedServer=sn;}
      else if(mode==='addEnvironment'){rows.push({id:crypto.randomUUID(),server:oldServer,environment:en,serverEnabled:true,environmentEnabled:true});envFilter=true;}
      else if(mode==='renameServer'){rows.filter(r=>same(r.server,oldServer)).forEach(r=>r.server=sn);selectedServer=sn;}
      else rows.find(r=>r.id===oldId).environment=en;
    };
    if(mode.startsWith('rename')){
      let server=mode==='renameServer',kind=server?'サーバー名':'環境名',oldName=server?oldServer:rows.find(r=>r.id===oldId).environment,newName=server?sn:en;
      confirm((server?'このサーバー内のすべての環境に適用されます。\n':'')+'ログに書かれている'+kind+'も「'+newName+'」になっていることを確認してください。',()=>save(action),'変更する',kind+'を「'+oldName+'」から「'+newName+'」に変更しますか？');
    }else save(action);
  };
  function toggleServer(name){
    let group=rows.filter(r=>same(r.server,name)),enabled=group[0].serverEnabled;
    let action=()=>save(()=>{group.forEach(r=>r.serverEnabled=!enabled);serverFilter=!enabled;selectedServer=name;});
    if(enabled)confirm(name+'を使用終了にしますか？ このサーバー内のすべての環境が使用できなくなります。',action,'使用を終了');else action();
  }
  function toggleEnvironment(id){
    let r=rows.find(r=>r.id===id),enabled=r.environmentEnabled;if(!enabled&&!r.serverEnabled)return;
    let action=()=>save(()=>{r.environmentEnabled=!enabled;envFilter=!enabled;});
    if(enabled)confirm(r.environment+'を使用終了にしますか？ このサーバーでは、この環境が使用できなくなります。',action,'使用を終了');else action();
  }
  el('addServer').onclick=()=>openEdit('addServer');el('addEnvironment').onclick=()=>openEdit('addEnvironment');
  el('serverName').oninput=validate;el('environmentName').oninput=validate;
  el('serverActive').onclick=()=>{serverFilter=true;render();};el('serverInactive').onclick=()=>{serverFilter=false;render();};
  el('envActive').onclick=()=>{envFilter=true;render();};el('envInactive').onclick=()=>{envFilter=false;render();};
  el('cancelEdit').onclick=()=>el('editDialog').close();
  el('cancelConfirm').onclick=()=>{pending=null;el('confirmDialog').close();};
  el('confirmSave').onclick=()=>{if(pending)pending();};
  for(let dialog of ['editDialog','confirmDialog'])el(dialog).addEventListener('cancel',()=>{pending=null;});
  el('back').onclick=()=>{if(history.length>1)history.back();};
  render();
</script>
</html>
'''

if __name__ == '__main__':
    main()
