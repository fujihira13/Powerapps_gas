using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Text;
using Microsoft.Xrm.Sdk;

namespace PowerappsGas.EnvironmentManagement
{
    [DataContract] public sealed class VersionProof
    {
        [DataMember(Name="id")] public string Id { get; set; }
        [DataMember(Name="version")] public string Version { get; set; }
    }
    [DataContract] public sealed class StorageProof
    {
        [DataMember(Name="id")] public string Id { get; set; }
        [DataMember(Name="version")] public string Version { get; set; }
        [DataMember(Name="driveId")] public string DriveId { get; set; }
        [DataMember(Name="folderId")] public string FolderId { get; set; }
        [DataMember(Name="checked")] public bool Checked { get; set; }
    }
    [DataContract] public sealed class ManagementRequest
    {
        [DataMember(Name="managementModel")] public string ManagementModel { get; set; }
        [DataMember(Name="operation")] public string Operation { get; set; }
        [DataMember(Name="targetId")] public string TargetId { get; set; }
        [DataMember(Name="expectedRows")] public List<VersionProof> ExpectedRows { get; set; }
        [DataMember(Name="environment")] public string Environment { get; set; }
        [DataMember(Name="server")] public string Server { get; set; }
        [DataMember(Name="storage")] public StorageProof Storage { get; set; }
    }
    [DataContract] public sealed class DestinationView
    {
        [DataMember(Name="id")] public string Id { get; set; }
        [DataMember(Name="version")] public string Version { get; set; }
        [DataMember(Name="environment")] public string Environment { get; set; }
        [DataMember(Name="server")] public string Server { get; set; }
        [DataMember(Name="environmentEnabled")] public bool EnvironmentEnabled { get; set; }
        [DataMember(Name="serverEnabled")] public bool ServerEnabled { get; set; }
    }
    [DataContract] public sealed class ManagementResult
    {
        [DataMember(Name="ok")] public bool Ok { get; set; }
        [DataMember(Name="reason")] public string Reason { get; set; }
        [DataMember(Name="rows")] public List<DestinationView> Rows { get; set; }
    }
    public sealed class ManagementPlan
    {
        public List<Entity> Updates = new List<Entity>();
        public Entity Create;
    }
    public sealed class ValidationException : Exception { public ValidationException(string message):base(message){} }
    public static class JsonContract
    {
        public static T Read<T>(string json) { using(var stream=new MemoryStream(Encoding.UTF8.GetBytes(json))) return (T)new DataContractJsonSerializer(typeof(T)).ReadObject(stream); }
        public static string Write<T>(T value) { using(var stream=new MemoryStream()) {new DataContractJsonSerializer(typeof(T)).WriteObject(stream,value);return Encoding.UTF8.GetString(stream.ToArray());} }
    }
    public static class ManagementPlanner
    {
        public const string Table="cr6cb_evidencedestination", Env="cr6cb_environment", Server="cr6cb_server", EnvEnabled="cr6cb_environmentenabled", ServerEnabled="cr6cb_isactive", Drive="cr6cb_driveid", Folder="cr6cb_folderid";
        public const string Stale="登録内容が変更されています。読み直してから操作してください。";
        public static bool EnvironmentActive(Entity row) {return !row.Contains(EnvEnabled)||row[EnvEnabled]==null||row.GetAttributeValue<bool>(EnvEnabled);}
        public static string Version(Entity row) {return row.RowVersion ?? row.GetAttributeValue<long>("versionnumber").ToString(System.Globalization.CultureInfo.InvariantCulture);}
        public static ManagementPlan Prepare(ManagementRequest request,List<Entity> rows)
        {
            var plan=new ManagementPlan();
            var op=request.Operation;
            var allowed=new[]{"list","addEnvironment","addServer","renameEnvironment","renameServer","endEnvironment","reactivateEnvironment","endServer","reactivateServer"};
            if(!allowed.Contains(op))throw new ValidationException("操作の種類を確認できません。");
            if(op=="list")return plan;
            if(request.ManagementModel!="server-first-v1")throw new ValidationException("管理画面が更新されています。画面を開き直してから操作してください。");
            if(rows.Any(x=>x.LogicalName!=Table))throw new ValidationException("登録先の表が一致しません。");
            Entity target=null;List<Entity> group=rows;
            if(op!="addServer")
            {
                Guid id;if(!Guid.TryParse(request.TargetId,out id))throw new ValidationException(Stale);
                target=rows.SingleOrDefault(x=>x.Id==id);if(target==null)throw new ValidationException(Stale);
                group=rows.Where(x=>x.GetAttributeValue<string>(Server)==target.GetAttributeValue<string>(Server)).ToList();
                if(group.Any(x=>x.GetAttributeValue<bool>(ServerEnabled)!=target.GetAttributeValue<bool>(ServerEnabled)))throw new ValidationException("サーバーの使用状態が揃っていません。登録内容を確認してください。");
            }
            CheckVersions(request.ExpectedRows,group);
            if(op=="addEnvironment"||op=="reactivateEnvironment")
                if(!target.GetAttributeValue<bool>(ServerEnabled))throw new ValidationException("このサーバーは使用終了です。サーバーを再び使用してから操作してください。");
            var env=op=="addServer"||op=="addEnvironment"||op=="renameEnvironment"?Name(request.Environment,"環境名"):target.GetAttributeValue<string>(Env);
            var server=op=="addServer"||op=="renameServer"?Name(request.Server,"サーバー名"):target.GetAttributeValue<string>(Server);
            if((op=="addServer"||op=="renameServer")&&rows.Any(x=>Equal(x.GetAttributeValue<string>(Server),server)&&(target==null||!group.Contains(x))))
                throw new ValidationException("同じサーバー名が登録されています。");
            if((op=="addEnvironment"||op=="renameEnvironment")&&group.Any(x=>Equal(x.GetAttributeValue<string>(Env),env)&&(op!="renameEnvironment"||x.Id!=target.Id)))
                throw new ValidationException("このサーバーに同じ環境名が登録されています。");
            if(op=="addEnvironment"||op=="addServer")
            {
                var storage=request.Storage;
                if(storage==null||!storage.Checked||String.IsNullOrWhiteSpace(storage.DriveId)||String.IsNullOrWhiteSpace(storage.FolderId))throw new ValidationException("保存先の利用を確認できません。登録は保存していません。");
                Guid sid;if(!Guid.TryParse(storage.Id,out sid))throw new ValidationException(Stale);
                var anchor=rows.SingleOrDefault(x=>x.Id==sid);
                if(anchor==null||Version(anchor)!=storage.Version)throw new ValidationException(Stale);
                if(rows.Count==0||rows.Any(x=>x.GetAttributeValue<string>(Drive)!=storage.DriveId||x.GetAttributeValue<string>(Folder)!=storage.FolderId))throw new ValidationException("共通保存先の設定が揃っていません。登録は保存していません。");
                plan.Create=new Entity(Table,Guid.NewGuid());
                plan.Create[Env]=env;plan.Create[Server]=server;plan.Create[EnvEnabled]=true;plan.Create[ServerEnabled]=true;
                plan.Create[Drive]=storage.DriveId;plan.Create[Folder]=storage.FolderId;
                plan.Create["cr6cb_destinationlabel"]=(env+" / "+server).Substring(0,Math.Min(100,(env+" / "+server).Length));
                // An optimistic no-op pins the configuration read during storage validation.
                plan.Updates.Add(Change(anchor,"cr6cb_destinationlabel",anchor.GetAttributeValue<string>("cr6cb_destinationlabel")));
                if(target!=null&&target.Id!=anchor.Id)plan.Updates.Add(Change(target,"cr6cb_destinationlabel",target.GetAttributeValue<string>("cr6cb_destinationlabel")));
            }
            else if(op=="renameServer")foreach(var row in group)plan.Updates.Add(Change(row,Server,server));
            else if(op=="endServer"||op=="reactivateServer")foreach(var row in group)plan.Updates.Add(Change(row,ServerEnabled,op=="reactivateServer"));
            else if(op=="renameEnvironment")plan.Updates.Add(Change(target,Env,env));
            else plan.Updates.Add(Change(target,EnvEnabled,op=="reactivateEnvironment"));
            return plan;
        }
        static Entity Change(Entity row,string column,object value){var update=new Entity(Table,row.Id){RowVersion=Version(row)};update[column]=value;return update;}
        static string Name(string value,string label){value=(value??"").Trim();if(value.Length==0)throw new ValidationException(label+"を入力してください。");if(value.Length>100)throw new ValidationException(label+"は100文字以内で入力してください。");return value;}
        static bool Equal(string a,string b){return String.Equals((a??"").Trim(),(b??"").Trim(),StringComparison.OrdinalIgnoreCase);}
        static void CheckVersions(List<VersionProof> proof,List<Entity> rows)
        {
            if(proof==null||proof.Count!=rows.Count)throw new ValidationException(Stale);
            var parsed=new Dictionary<Guid,string>();
            foreach(var value in proof){Guid id;if(value==null||!Guid.TryParse(value.Id,out id)||String.IsNullOrEmpty(value.Version)||parsed.ContainsKey(id))throw new ValidationException(Stale);parsed.Add(id,value.Version);}
            if(rows.Any(x=>!parsed.ContainsKey(x.Id)||parsed[x.Id]!=Version(x)))throw new ValidationException(Stale);
        }
    }
}
