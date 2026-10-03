using System;
using System.Collections.Generic;
using System.Linq;
using Microsoft.Xrm.Sdk;
using PowerappsGas.EnvironmentManagement;
class Program
{
    static int failures;
    static void Main() {
        Run("server rename updates all its environments",()=>{var r=Rows();var q=Request("renameServer",r);q.Server="renamed";var p=ManagementPlanner.Prepare(q,r);Check(p.Updates.Count==2&&p.Updates.All(x=>x.GetAttributeValue<string>(ManagementPlanner.Server)=="renamed"&&!x.Contains(ManagementPlanner.Env)));});
        Run("environment rename updates only its pair",()=>{var r=Rows();var q=Request("renameEnvironment",r);q.Environment="renamed";var p=ManagementPlanner.Prepare(q,r);Check(p.Updates.Count==1&&p.Updates[0].Id==r[0].Id&&p.Updates[0].GetAttributeValue<string>(ManagementPlanner.Env)=="renamed");});
        Run("ended environment names reject within server",()=>{var r=Rows();r[1][ManagementPlanner.EnvEnabled]=false;var q=Request("renameEnvironment",r);q.Environment="env-B";Reject(()=>ManagementPlanner.Prepare(q,r),"同じ環境名");});
        Run("same environment name is allowed on another server",()=>{var r=Rows();var q=Request("renameEnvironment",r);q.Environment="env-C";Check(ManagementPlanner.Prepare(q,r).Updates.Count==1);});
        Run("ended server names reject globally",()=>{var r=Rows();r[2][ManagementPlanner.ServerEnabled]=false;var q=Request("renameServer",r);q.Server="server-B";Reject(()=>ManagementPlanner.Prepare(q,r),"同じサーバー名");});
        Run("stale and incomplete versions reject",()=>{var r=Rows();var q=Request("renameEnvironment",r);q.Environment="changed";q.ExpectedRows[1].Version="old";Reject(()=>ManagementPlanner.Prepare(q,r),ManagementPlanner.Stale);q.ExpectedRows.RemoveAt(1);Reject(()=>ManagementPlanner.Prepare(q,r),ManagementPlanner.Stale);});
        Run("reactivating server preserves ended environments",()=>{var r=Rows();r[0][ManagementPlanner.ServerEnabled]=false;r[1][ManagementPlanner.ServerEnabled]=false;r[1][ManagementPlanner.EnvEnabled]=false;var p=ManagementPlanner.Prepare(Request("reactivateServer",r),r);Check(p.Updates.Count==2&&p.Updates.All(x=>x.GetAttributeValue<bool>(ManagementPlanner.ServerEnabled)&&!x.Contains(ManagementPlanner.EnvEnabled)));});
        Run("ending environment affects one pair only",()=>{var r=Rows();var p=ManagementPlanner.Prepare(Request("endEnvironment",r),r);Check(p.Updates.Count==1&&p.Updates[0].Id==r[0].Id&&!p.Updates[0].GetAttributeValue<bool>(ManagementPlanner.EnvEnabled)&&!p.Updates[0].Contains(ManagementPlanner.ServerEnabled));});
        Run("ended server blocks environment add and reactivation",()=>{var r=Rows();r[0][ManagementPlanner.ServerEnabled]=false;r[1][ManagementPlanner.ServerEnabled]=false;var q=Request("addEnvironment",r);q.Environment="new-env";Reject(()=>ManagementPlanner.Prepare(q,r),"使用終了");q.Operation="reactivateEnvironment";Reject(()=>ManagementPlanner.Prepare(q,r),"使用終了");});
        Run("new server inherits checked storage and exact names",()=>{var r=Rows();var q=Request("addServer",r);q.Environment="Real env";q.Server="Real server";q.ExpectedRows=Proofs(r);q.Storage=Storage(r[0]);var p=ManagementPlanner.Prepare(q,r);Check(p.Create.GetAttributeValue<string>(ManagementPlanner.Env)=="Real env"&&p.Create.GetAttributeValue<string>(ManagementPlanner.Server)=="Real server"&&p.Create.GetAttributeValue<string>(ManagementPlanner.Drive)=="drive");q.Storage.Checked=false;Reject(()=>ManagementPlanner.Prepare(q,r),"保存先");q.Storage.Checked=true;q.Storage.Version="old";Reject(()=>ManagementPlanner.Prepare(q,r),ManagementPlanner.Stale);});
        Run("new environment inherits selected server and checked storage",()=>{var r=Rows();var q=Request("addEnvironment",r);q.Environment="env-C";q.Server="ignored-client-value";var p=ManagementPlanner.Prepare(q,r);Check(p.Create.GetAttributeValue<string>(ManagementPlanner.Server)=="server-A"&&p.Create.GetAttributeValue<string>(ManagementPlanner.Env)=="env-C");});
        Run("old management screen cannot write but list remains compatible",()=>{var r=Rows();var q=Request("endServer",r);q.ManagementModel=null;Reject(()=>ManagementPlanner.Prepare(q,r),"画面を開き直して");q.Operation="list";Check(ManagementPlanner.Prepare(q,r).Updates.Count==0);});
        Run("name boundaries reject blank and overlong",()=>{var r=Rows();var q=Request("renameServer",r);foreach(var value in new[]{" ",new string('a',101)}){q.Server=value;Reject(()=>ManagementPlanner.Prepare(q,r),"サーバー名");}q.Server=new string('a',100);Check(ManagementPlanner.Prepare(q,r).Updates.Count>0);});
        Run("unexpected operation cannot write",()=>{var r=Rows();Reject(()=>ManagementPlanner.Prepare(Request("delete",r),r),"操作");});
        Run("duplicate is rechecked after transaction lock",PluginContracts.RecheckAfterLock);
        Run("write fault propagates for rollback",PluginContracts.PropagateFailure);
        Console.WriteLine("Failures: "+failures);Environment.ExitCode=failures==0?0:1;
    }
    static void Check(bool ok){if(!ok)throw new Exception("Contract mismatch");}
    static void Reject(Action action,string text){try{action();}catch(ValidationException ex){Check(ex.Message.Contains(text));return;}throw new Exception("Expected rejection");}
    static void Run(string name,Action test){try{test();Console.WriteLine("PASS "+name);}catch(Exception ex){failures++;Console.WriteLine("FAIL "+name+": "+ex.Message);}}
    static List<Entity> Rows(){return new List<Entity>{Row("00000000-0000-0000-0000-000000000001","env-A","server-A"),Row("00000000-0000-0000-0000-000000000002","env-B","server-A"),Row("00000000-0000-0000-0000-000000000003","env-C","server-B")};}
    static Entity Row(string id,string env,string server){var r=new Entity(ManagementPlanner.Table,Guid.Parse(id));r.RowVersion="1";r[ManagementPlanner.Env]=env;r[ManagementPlanner.Server]=server;r[ManagementPlanner.ServerEnabled]=true;r[ManagementPlanner.Drive]="drive";r[ManagementPlanner.Folder]="folder";return r;}
    static List<VersionProof> Proofs(IEnumerable<Entity> rows){return rows.Select(x=>new VersionProof{Id=x.Id.ToString(),Version=ManagementPlanner.Version(x)}).ToList();}
    static ManagementRequest Request(string op,List<Entity> rows){return new ManagementRequest{ManagementModel="server-first-v1",Operation=op,TargetId=rows[0].Id.ToString(),ExpectedRows=Proofs(rows.Take(2)),Storage=Storage(rows[0])};}
    static StorageProof Storage(Entity row){return new StorageProof{Id=row.Id.ToString(),Version=ManagementPlanner.Version(row),DriveId="drive",FolderId="folder",Checked=true};}
}
