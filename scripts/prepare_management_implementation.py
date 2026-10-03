"""Build local management flow / deployment input from saved readback.

No network access. Live identifiers stay under the ignored outputs directory.
"""
import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/environment-management-20261003/implementation/baseline"
OUT = BASE.parent / "candidate"

def load(name):
    record = json.loads((BASE / name).read_text(encoding="utf-8-sig"))
    return record, json.loads(record["clientdata"])

def connector(api, operation, parameters, after=None):
    return {"type":"OpenApiConnection", "inputs":{
        "host":{"apiId":f"/providers/Microsoft.PowerApps/apis/{api}","connectionName":api,"operationId":operation},
        "parameters":parameters,"authentication":"@parameters('$authentication')","retryPolicy":{"type":"none"}},
        "runAfter":after or {}}

def response(value, after):
    return {"type":"Response", "kind":"PowerApp", "inputs":{
        "statusCode":200,"body":{"result":value},"schema":{"type":"object","properties":{"result":{"type":"string","title":"result","x-ms-dynamically-added":True}},"required":["result"]}},
        "runAfter":after}

def build():
    _, main = load("main-workflow.json")
    _, archive = load("archive-workflow.json")
    definition = main["properties"]["definition"]
    request_expr = "@json(triggerBody()?['text'])"
    actions = {
        "Parse_request":{"type":"Compose","inputs":request_expr,"runAfter":{}},
        "Initialize_request":{"type":"InitializeVariable","inputs":{"variables":[{"name":"ManagementRequest","type":"object","value":"@outputs('Parse_request')"}]},"runAfter":{"Parse_request":["Succeeded"]}},
        "Manage":{"type":"Scope","actions":{},"runAfter":{"Initialize_request":["Succeeded"]}}
    }
    scope = actions["Manage"]["actions"]
    scope["Check_add"]={"type":"If","expression":{"or":[{"equals":["@outputs('Parse_request')?['operation']","addEnvironment"]},{"equals":["@outputs('Parse_request')?['operation']","addServer"]}]},"actions":{},"else":{"actions":{}},"runAfter":{}}
    add=scope["Check_add"]["actions"]
    dv="shared_commondataserviceforapps"
    od="shared_onedriveforbusiness"
    sp="shared_sharepointonline"
    add["Read_storage_anchor"]=connector(dv,"ListRecords",{"entityName":"cr6cb_evidencedestinations","$select":"cr6cb_evidencedestinationid,versionnumber,cr6cb_driveid,cr6cb_folderid","$orderby":"cr6cb_evidencedestinationid asc","$top":1})
    add["Check_anchor"]={"type":"If","expression":{"equals":["@length(outputs('Read_storage_anchor')?['body/value'])",1]},"actions":{},"else":{"actions":{"Reject_anchor":{"type":"SetVariable","inputs":{"name":"ManagementRequest","value":"@setProperty(outputs('Parse_request'),'storage',json('{\"checked\":false}'))"}}}},"runAfter":{"Read_storage_anchor":["Succeeded"]}}
    checks=add["Check_anchor"]["actions"]
    # Existing connector access only; no temporary uploads or additional data.
    checks["Check_OneDrive_folder"]=connector(od,"GetFileMetadata",{"id":"@first(outputs('Read_storage_anchor')?['body/value'])?['cr6cb_folderid']"})
    checks["Check_SharePoint_folder"]=connector(sp,"GetFolderMetadataByPath",{"dataset":"https://fujimasa13.sharepoint.com/sites/msteams_fcec5c","path":"/Shared Documents/General/MQ照合証跡"},{"Check_OneDrive_folder":["Succeeded"]})
    checks["Attach_storage_proof"]={"type":"SetVariable","inputs":{"name":"ManagementRequest","value":"@setProperty(outputs('Parse_request'),'storage',addProperty(addProperty(addProperty(addProperty(addProperty(json('{}'),'id',string(first(outputs('Read_storage_anchor')?['body/value'])?['cr6cb_evidencedestinationid'])),'version',string(first(outputs('Read_storage_anchor')?['body/value'])?['versionnumber'])),'driveId',first(outputs('Read_storage_anchor')?['body/value'])?['cr6cb_driveid']),'folderId',first(outputs('Read_storage_anchor')?['body/value'])?['cr6cb_folderid']),'checked',true))"},"runAfter":{"Check_SharePoint_folder":["Succeeded"]}}
    scope["Save_registration"]=connector(dv,"PerformUnboundAction",{"actionName":"cr6cb_ManageEvidenceDestinations","item/RequestJson":"@string(variables('ManagementRequest'))"},{"Check_add":["Succeeded"]})
    actions["Return_result"]=response("@outputs('Save_registration')?['body/ResultJson']",{"Manage":["Succeeded"]})
    # Do not automatically replay a request after timeout / uncertain outcome.
    stale="登録内容が変更されています。読み直してから操作してください。"
    storage="保存先の利用を確認できません。登録は保存していません。"
    unknown="保存結果を確認できません。読み直してから登録内容を確認してください。"
    failure="登録内容を保存できませんでした。読み直してから状態を確認してください。"
    reason=f"if(contains(string(result('Manage')),'{stale}'),'{stale}',if(or(equals(actions('Save_registration')?['status'],'TimedOut'),equals(actions('Manage')?['status'],'TimedOut')),'{unknown}',if(not(equals(actions('Check_add')?['status'],'Succeeded')),'{storage}','{failure}')))"
    actions["Return_error"]=response("@string(setProperty(json('{\"ok\":false,\"rows\":[]}'),'reason',"+reason+"))",{"Manage":["Failed","TimedOut"]})
    flow={"properties":{"definition":{"$schema":definition["$schema"],"contentVersion":"1.0.0.0","parameters":copy.deepcopy(definition.get("parameters",{})),"triggers":{"manual":{"type":"Request","kind":"PowerAppV2","inputs":{"schema":{"type":"object","properties":{"text":{"title":"requestJson","type":"string","x-ms-dynamically-added":True,"description":"操作と更新前の登録内容"}},"required":["text"]}}}},"actions":actions},"connectionReferences":copy.deepcopy(archive["properties"]["connectionReferences"])},"schemaVersion":"1.0.0.0"}
    # Connector and storage identifiers are from the approved existing archive.
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"management-clientdata.json").write_text(json.dumps(flow,ensure_ascii=False,indent=2),encoding="utf-8")
    manifest={"solution":"Cr62766","table":"cr6cb_evidencedestination","column":{"SchemaName":"cr6cb_environmentenabled","DisplayName":"環境の使用状態","type":"Boolean","required":False,"default":True,"trueLabel":"使用中","falseLabel":"使用終了"},"pluginAssembly":"PowerappsGas.EnvironmentManagement","pluginType":"PowerappsGas.EnvironmentManagement.EnvironmentManagementPlugin","customApi":{"uniquename":"cr6cb_ManageEvidenceDestinations","name":"環境・サーバー管理の保存","bindingtype":0,"isfunction":False,"isprivate":False,"allowedcustomprocessingsteptype":0,"workflowsdkstepenabled":True,"request":{"name":"RequestJson","type":10,"isoptional":False},"response":{"name":"ResultJson","type":10}},"workflow":{"name":"架空ログ証跡_環境サーバー管理","category":5,"type":1},"deployed":False}
    (OUT/"management-deployment-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Prepared management flow and manifest locally. No cloud writes.")

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--inspect",action="store_true");args=parser.parse_args()
    if args.inspect:
        _,c=load("main-workflow.json")
        def walk(actions):
            for name,a in actions.items():
                if name.startswith("Filter_active_destinations"): print(name,json.dumps(a,ensure_ascii=False))
                walk(a.get("actions",{}));walk(a.get("else",{}).get("actions",{}))
        walk(c["properties"]["definition"]["actions"])
        print(json.dumps(c["properties"]["definition"]["triggers"],ensure_ascii=False))
    else:build()
