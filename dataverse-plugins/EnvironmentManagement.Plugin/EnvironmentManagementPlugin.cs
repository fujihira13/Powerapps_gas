using System;
using System.Collections.Generic;
using System.Linq;
using System.ServiceModel;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Messages;
using Microsoft.Xrm.Sdk.Query;

namespace PowerappsGas.EnvironmentManagement
{
    // Main operation of this Custom API only. No steps on case/history tables.
    public sealed class EnvironmentManagementPlugin : IPlugin
    {
        public const string ApiName="cr6cb_ManageEvidenceDestinations";
        public void Execute(IServiceProvider provider)
        {
            var context=(IPluginExecutionContext)provider.GetService(typeof(IPluginExecutionContext));
            if(context.MessageName!=ApiName||context.Stage!=30||context.Mode!=0)throw new InvalidPluginExecutionException("管理用の保存処理として実行してください。");
            var raw=context.InputParameters.Contains("RequestJson")?context.InputParameters["RequestJson"] as string:null;
            if(String.IsNullOrEmpty(raw)||raw.Length>262144)throw new InvalidPluginExecutionException("操作内容を読み取れません。");
            ManagementRequest request;
            try{request=JsonContract.Read<ManagementRequest>(raw);}catch(Exception){throw new InvalidPluginExecutionException("操作内容を読み取れません。");}
            if(request==null)throw new InvalidPluginExecutionException("操作内容を読み取れません。");
            if(request.Operation!="list"&&!context.IsInTransaction)throw new InvalidPluginExecutionException("一括保存を保証できないため、登録を変更していません。");
            var factory=(IOrganizationServiceFactory)provider.GetService(typeof(IOrganizationServiceFactory));
            var service=factory.CreateOrganizationService(context.UserId);
            try
            {
                var rows=ReadRows(service);ManagementPlan plan;
                try{plan=ManagementPlanner.Prepare(request,rows);}
                catch(ValidationException ex){context.OutputParameters["ResultJson"]=JsonContract.Write(new ManagementResult{Ok=false,Reason=ex.Message,Rows=new List<DestinationView>()});return;}
                if(request.Operation!="list")
                {
                    // Acquire the same existing row lock inside the transaction,
                    // then validate again. No separate lock table is required.
                    var anchor=rows.OrderBy(x=>x.Id).FirstOrDefault();
                    if(anchor==null)throw new InvalidPluginExecutionException("共通保存先の設定を確認できません。");
                    var held=new Entity(ManagementPlanner.Table,anchor.Id){RowVersion=ManagementPlanner.Version(anchor)};
                    held["cr6cb_destinationlabel"]=anchor.GetAttributeValue<string>("cr6cb_destinationlabel");
                    service.Execute(new UpdateRequest{Target=held,ConcurrencyBehavior=ConcurrencyBehavior.IfRowVersionMatches});
                    var current=ReadRows(service);
                    var locked=current.Single(x=>x.Id==anchor.Id);
                    var proof=request.ExpectedRows.FirstOrDefault(x=>x.Id==anchor.Id.ToString());
                    if(proof!=null && proof.Version==ManagementPlanner.Version(anchor))proof.Version=ManagementPlanner.Version(locked);
                    if(request.Storage!=null && request.Storage.Id==anchor.Id.ToString() && request.Storage.Version==ManagementPlanner.Version(anchor))request.Storage.Version=ManagementPlanner.Version(locked);
                    try{plan=ManagementPlanner.Prepare(request,current);}
                    catch(ValidationException ex){throw new InvalidPluginExecutionException(ex.Message);}
                    plan.Updates.RemoveAll(x=>x.Id==anchor.Id && x.Attributes.Count==1 && x.Contains("cr6cb_destinationlabel"));
                }
                foreach(var update in plan.Updates.OrderBy(x=>x.Id))service.Execute(new UpdateRequest{Target=update,ConcurrencyBehavior=ConcurrencyBehavior.IfRowVersionMatches});
                if(plan.Create!=null)service.Create(plan.Create);
                var saved=request.Operation=="list"?rows:ReadRows(service);
                context.OutputParameters["ResultJson"]=JsonContract.Write(new ManagementResult{Ok=true,Reason="",Rows=saved.Select(View).ToList()});
            }
            catch(FaultException<OrganizationServiceFault> ex)
            {
                // Propagate failure to Dataverse so every write in the transaction rolls back.
                var reason=ex.Detail.ErrorCode==-2147088254?ManagementPlanner.Stale:"登録内容を保存できませんでした。読み直してから状態を確認してください。";
                throw new InvalidPluginExecutionException(reason,ex);
            }
        }
        public static List<Entity> ReadRows(IOrganizationService service)
        {
            var query=new QueryExpression(ManagementPlanner.Table){ColumnSet=new ColumnSet(ManagementPlanner.Env,ManagementPlanner.Server,ManagementPlanner.EnvEnabled,ManagementPlanner.ServerEnabled,ManagementPlanner.Drive,ManagementPlanner.Folder,"cr6cb_destinationlabel","versionnumber"),PageInfo=new PagingInfo{Count=500,PageNumber=1}};
            query.AddOrder("cr6cb_evidencedestinationid",OrderType.Ascending);
            var result=new List<Entity>();
            while(true){var page=service.RetrieveMultiple(query);result.AddRange(page.Entities);if(result.Count>2000)throw new InvalidPluginExecutionException("登録が多いため一覧を取得できません。管理設定を確認してください。");if(!page.MoreRecords)break;query.PageInfo.PageNumber++;query.PageInfo.PagingCookie=page.PagingCookie;}
            return result;
        }
        static DestinationView View(Entity row){return new DestinationView{Id=row.Id.ToString(),Version=ManagementPlanner.Version(row),Environment=row.GetAttributeValue<string>(ManagementPlanner.Env),Server=row.GetAttributeValue<string>(ManagementPlanner.Server),EnvironmentEnabled=ManagementPlanner.EnvironmentActive(row),ServerEnabled=row.GetAttributeValue<bool>(ManagementPlanner.ServerEnabled)};}
    }
}
