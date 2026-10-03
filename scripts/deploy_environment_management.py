"""Deploy approved management components with the authenticated Dataverse CLI.

Requires --approved. Reuses existing solution/connection references. Never
publishes a Canvas app, deletes records, purchases or grants privileges.
"""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/"outputs/environment-management-20261003/implementation"
OUT=WORK/"deployment"
URL="https://org3d6ad684.crm7.dynamics.com/"
SOLUTION="Cr62766"

def command(args):
    entry=Path(os.environ["APPDATA"])/"npm/node_modules/@microsoft/dataverse/bin/dataverse.js"
    if not entry.is_file():raise RuntimeError("The installed Microsoft Dataverse CLI entry was not found.")
    result=subprocess.run([shutil.which("node"),str(entry),*args],capture_output=True,text=True,encoding="utf-8",errors="replace",cwd=ROOT)
    if result.returncode:
        # The CLI does not print request bodies. Limit response logs; never print
        # an assembly-content/connection-reference payload ourselves.
        (OUT/"last-error.txt").write_text(result.stderr+result.stdout,encoding="utf-8")
        raise RuntimeError("Dataverse operation failed; inspect the Git-excluded last-error.txt before retrying.")
    try:return json.loads(result.stdout)
    except json.JSONDecodeError:return {"text":result.stdout.strip()}

def query(table,filter,select):
    result=command(["data","query","--table",table,"--filter",filter,"--select",select,"--top","20","--environment",URL,"--json"])
    if isinstance(result,list):return result
    for key in ("value","records","data"):
        if isinstance(result.get(key),list):return result[key]
    raise RuntimeError("Unrecognized query response; do not repeat writes.")

def file(name,body):
    p=OUT/name;p.write_text(json.dumps(body,ensure_ascii=False),encoding="utf-8");return str(p)

def create(table,body,name):
    r=command(["data","create","--table",table,"--data-file",file(name,body),"--solution-unique-name",SOLUTION,"--environment",URL,"--json"])
    if "id" not in r:raise RuntimeError("Unknown create outcome; read back by unique name before continuing.")
    return r["id"]

def request(path,method="GET",body=None,headers=()):
    if not path.startswith("/api/data/"):path="/api/data/v9.2/"+path
    args=["api","request","--target","dataverse","--path",path,"--method",method,"--environment",URL]
    for h in headers:args+= ["--header",h]
    if body is not None:args+= ["--body-file",file("metadata-request.json",body)]
    return command(args)

def label(text):return {"LocalizedLabels":[{"Label":text,"LanguageCode":1041},{"Label":text,"LanguageCode":1033}]}

def deploy_schema():
    manifest=json.loads((WORK/"candidate/management-deployment-manifest.json").read_text(encoding="utf-8"))
    path="EntityDefinitions(LogicalName='cr6cb_evidencedestination')/Attributes?$select=LogicalName,MetadataId&$filter=LogicalName eq 'cr6cb_environmentenabled'"
    metadata=request(path)
    if not metadata.get("value"):
        # Advanced Boolean labels are needed by the approved Japanese Canvas
        # enum; the generic SDK bool helper cannot specify these labels.
        body={"@odata.type":"Microsoft.Dynamics.CRM.BooleanAttributeMetadata","SchemaName":"cr6cb_environmentenabled","DisplayName":label("環境の使用状態"),"RequiredLevel":{"Value":"None"},"DefaultValue":True,"OptionSet":{"@odata.type":"Microsoft.Dynamics.CRM.BooleanOptionSetMetadata","TrueOption":{"Value":1,"Label":label("使用中")},"FalseOption":{"Value":0,"Label":label("使用終了")}}}
        request("EntityDefinitions(LogicalName='cr6cb_evidencedestination')/Attributes","POST",body,("MSCRM.SolutionUniqueName:"+SOLUTION,))
    metadata=request(path)
    if len(metadata.get("value",[]))!=1:raise RuntimeError("Column readback not confirmed.")
    print("Environment state column confirmed.")
    assemblyName=manifest["pluginAssembly"]
    assemblies=query("pluginassemblies",f"name eq '{assemblyName}'","pluginassemblyid,name,version,publickeytoken")
    registration=json.loads((WORK/"build/pluginassembly-create.json").read_text(encoding="utf-8-sig"))
    if not assemblies:
        aid=create("pluginassemblies",registration,"assembly-request.json")
    else:
        if len(assemblies)!=1:raise RuntimeError("Ambiguous assembly name.")
        aid=assemblies[0]["pluginassemblyid"]
        if assemblies[0]["publickeytoken"]!=registration["publickeytoken"]:raise RuntimeError("Assembly public key changed; stop rather than replace it.")
        command(["data","update","--table","pluginassemblies","--id",aid,"--data-file",file("assembly-request.json",{"content":registration["content"]}),"--solution-unique-name",SOLUTION,"--environment",URL,"--json"])
    types=query("plugintypes",f"_pluginassemblyid_value eq {aid} and typename eq '{manifest['pluginType']}'","plugintypeid,typename")
    if not types:
        tid=create("plugintypes",{"typename":manifest["pluginType"],"name":manifest["pluginType"],"friendlyname":"環境・サーバー管理の保存","pluginassemblyid@odata.bind":f"/pluginassemblies({aid})"},"type-request.json")
    elif len(types)==1:tid=types[0]["plugintypeid"]
    else:raise RuntimeError("Ambiguous plugin type.")
    api=manifest["customApi"];apis=query("customapis",f"uniquename eq '{api['uniquename']}'","customapiid,uniquename,_plugintypeid_value")
    if not apis:
        body={k:v for k,v in api.items() if k not in ("request","response")}
        body["description"]="環境・サーバーの登録を同期トランザクション内でまとめて保存し、保存後の一覧を返します。"
        body["displayname"]=api["name"];body["PluginTypeId@odata.bind"]=f"/plugintypes({tid})"
        cid=create("customapis",body,"api-request.json")
    elif len(apis)==1:
        cid=apis[0]["customapiid"]
        if apis[0].get("_plugintypeid_value")!=tid:raise RuntimeError("API plugin binding differs; stop.")
    else:raise RuntimeError("Ambiguous API unique name.")
    for table,pk,part in (("customapirequestparameters","customapirequestparameterid","request"),("customapiresponseproperties","customapiresponsepropertyid","response")):
        p=api[part]
        found=query(table,f"_customapiid_value eq {cid} and uniquename eq '{p['name']}'",pk+",uniquename,type")
        if not found:
            body={"name":api["uniquename"]+"."+p["name"],"uniquename":p["name"],"displayname":p["name"],"type":p["type"],"CustomAPIId@odata.bind":f"/customapis({cid})"}
            body["description"]="操作と更新前の版を含むJSON" if part=="request" else "保存結果と読み戻した登録一覧のJSON"
            if part=="request":body["isoptional"]=False
            create(table,body,part+"-request.json")
        elif len(found)!=1 or found[0]["type"]!=10:raise RuntimeError("API parameter readback differs.")
    state={"assemblyId":aid,"pluginTypeId":tid,"customApiId":cid,"column":metadata["value"][0],"schemaDeployed":True,"canvasSaved":False,"runtimeTested":False}
    (OUT/"schema-state.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Management assembly / API registered; no management or comparison test run.")

def deploy_flow():
    name="架空ログ証跡_環境サーバー管理"
    found=query("workflows",f"name eq '{name}'","workflowid,name,statecode")
    c=json.loads((WORK/"candidate/management-clientdata.json").read_text(encoding="utf-8"))
    if not found:
        wid=create("workflows",{"name":name,"category":5,"type":1,"primaryentity":"none","clientdata":json.dumps(c,ensure_ascii=False,separators=(",",":"))},"flow-request.json")
    elif len(found)==1:wid=found[0]["workflowid"]
    else:raise RuntimeError("Ambiguous management flow.")
    # Registration/readback first. Activation is a separate explicit stage.
    r=command(["data","get","--table","workflows","--id",wid,"--select","workflowid,name,statecode,clientdata","--environment",URL,"--json"])
    if json.loads(r["clientdata"])!=c:
        if r["statecode"]==1:raise RuntimeError("Active management flow differs; stop before replacing it.")
        command(["data","update","--table","workflows","--id",wid,"--data-file",file("flow-definition.json",{"clientdata":json.dumps(c,ensure_ascii=False,separators=(",",":"))}),"--solution-unique-name",SOLUTION,"--environment",URL,"--json"])
        r=command(["data","get","--table","workflows","--id",wid,"--select","workflowid,name,statecode,clientdata","--environment",URL,"--json"])
        if json.loads(r["clientdata"])!=c:raise RuntimeError("Management flow readback differs; do not activate.")
    if r["statecode"]!=1:
        command(["data","update","--table","workflows","--id",wid,"--data-file",file("flow-activate.json",{"statecode":1,"statuscode":2}),"--solution-unique-name",SOLUTION,"--environment",URL,"--json"])
        r=command(["data","get","--table","workflows","--id",wid,"--select","workflowid,name,statecode,clientdata","--environment",URL,"--json"])
    if r["statecode"]!=1 or json.loads(r["clientdata"])!=c:raise RuntimeError("Management flow activation/readback not confirmed.")
    (OUT/"management-flow-readback.json").write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Management flow registered / read back: "+wid)

def deploy_main():
    before=json.loads((WORK/"baseline/main-workflow.json").read_text(encoding="utf-8-sig"))
    wid=before["workflowid"]
    current=command(["data","get","--table","workflows","--id",wid,"--select","workflowid,name,statecode,clientdata","--environment",URL,"--json"])
    candidate=json.loads((WORK/"candidate/main-candidate-clientdata.json").read_text(encoding="utf-8"))
    if json.loads(current["clientdata"])==candidate:
        print("Main flow already matches candidate; no replay.");return
    if json.loads(current["clientdata"])!=json.loads(before["clientdata"]):raise RuntimeError("Main flow changed after baseline; stop before overwriting.")
    request(f"workflows({wid})","PATCH",{"clientdata":json.dumps(candidate,ensure_ascii=False,separators=(",",":"))},("If-Match:"+current["@odata.etag"],"MSCRM.SolutionUniqueName:"+SOLUTION))
    saved=command(["data","get","--table","workflows","--id",wid,"--select","workflowid,name,statecode,clientdata","--environment",URL,"--json"])
    if json.loads(saved["clientdata"])!=candidate or saved["statecode"]!=1:raise RuntimeError("Main flow readback differs or is inactive.")
    (OUT/"main-flow-readback.json").write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Main flow: approved 8-node candidate saved and read back; active.")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("stage",choices=("schema","flow","main"));p.add_argument("--approved",action="store_true");a=p.parse_args()
    if not a.approved:raise SystemExit("External deployment requires the recorded execution approval.")
    OUT.mkdir(parents=True,exist_ok=True)
    if a.stage=="schema":deploy_schema()
    elif a.stage=="flow":deploy_flow()
    else:deploy_main()
