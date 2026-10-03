using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.Remoting.Messaging;
using System.Runtime.Remoting.Proxies;
using System.ServiceModel;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Messages;
using Microsoft.Xrm.Sdk.Query;
using PowerappsGas.EnvironmentManagement;

static class PluginContracts
{
    public static void RecheckAfterLock()
    {
        var service=new FakeService();var rows=service.Rows;
        var request=new ManagementRequest{ManagementModel="server-first-v1",Operation="renameServer",TargetId=rows[0].Id.ToString(),Server="new-server",ExpectedRows=rows.Select(x=>new VersionProof{Id=x.Id.ToString(),Version=x.RowVersion}).ToList()};
        service.InsertDuplicateBeforeSecondRead=true;
        var provider=new Provider(service,request);
        try {new EnvironmentManagementPlugin().Execute(provider);}
        catch(InvalidPluginExecutionException e) {if(!e.Message.Contains("同じサーバー名"))throw; if(service.NameWrites!=0)throw new Exception("Name written before recheck.");return;}
        throw new Exception("A concurrent server name must be rejected after locking.");
    }
    public static void PropagateFailure()
    {
        var service=new FakeService{FailOnThirdWrite=true};var row=service.Rows[0];
        var request=new ManagementRequest{ManagementModel="server-first-v1",Operation="renameServer",TargetId=row.Id.ToString(),Server="new-server",ExpectedRows=service.Rows.Select(x=>new VersionProof{Id=x.Id.ToString(),Version=x.RowVersion}).ToList()};
        var provider=new Provider(service,request);
        try {new EnvironmentManagementPlugin().Execute(provider);}catch(InvalidPluginExecutionException){if(provider.Output.Contains("ResultJson"))throw new Exception("Failure reported as output success.");if(service.NameWrites!=1)throw new Exception("Expected failure after the first group mutation.");return;}
        throw new Exception("Write fault was swallowed.");
    }
    sealed class Provider:IServiceProvider,IOrganizationServiceFactory
    {
        readonly FakeService service;readonly IPluginExecutionContext context;
        public readonly ParameterCollection Output=new ParameterCollection();
        public Provider(FakeService s,ManagementRequest r){service=s;context=(IPluginExecutionContext)new ContextProxy(new Dictionary<string,object>{{"MessageName",EnvironmentManagementPlugin.ApiName},{"Stage",30},{"Mode",0},{"IsInTransaction",true},{"UserId",Guid.NewGuid()},{"InputParameters",new ParameterCollection{{"RequestJson",JsonContract.Write(r)}}},{"OutputParameters",Output}}).GetTransparentProxy();}
        public object GetService(Type type){if(type==typeof(IPluginExecutionContext))return context;if(type==typeof(IOrganizationServiceFactory))return this;return null;}
        public IOrganizationService CreateOrganizationService(Guid? id){return service;}
    }
    sealed class ContextProxy:RealProxy
    {
        readonly Dictionary<string,object> values;
        public ContextProxy(Dictionary<string,object> v):base(typeof(IPluginExecutionContext)){values=v;}
        public override IMessage Invoke(IMessage message){var call=(IMethodCallMessage)message;object value;values.TryGetValue(call.MethodName.Substring(4),out value);return new ReturnMessage(value,null,0,call.LogicalCallContext,call);}
    }
    sealed class FakeService:IOrganizationService
    {
        public readonly List<Entity> Rows=new List<Entity>();public bool InsertDuplicateBeforeSecondRead,FailOnThirdWrite;public int NameWrites;int reads,writes;
        public FakeService(){for(int i=0;i<2;i++){var e=new Entity(ManagementPlanner.Table,new Guid("00000000-0000-0000-0000-00000000000"+(i+1))){RowVersion="1"};e[ManagementPlanner.Env]="env"+i;e[ManagementPlanner.Server]="server";e[ManagementPlanner.ServerEnabled]=true;e[ManagementPlanner.Drive]="drive";e[ManagementPlanner.Folder]="folder";e["cr6cb_destinationlabel"]="label";Rows.Add(e);}}
        public EntityCollection RetrieveMultiple(QueryBase q){reads++;if(reads==2&&InsertDuplicateBeforeSecondRead){var e=new Entity(ManagementPlanner.Table,Guid.NewGuid()){RowVersion="1"};e[ManagementPlanner.Env]="new-env";e[ManagementPlanner.Server]="new-server";e[ManagementPlanner.ServerEnabled]=true;Rows.Add(e);}return new EntityCollection(Rows.Select(Clone).ToList());}
        static Entity Clone(Entity row){var e=new Entity(row.LogicalName,row.Id){RowVersion=row.RowVersion};foreach(var p in row.Attributes)e[p.Key]=p.Value;return e;}
        public OrganizationResponse Execute(OrganizationRequest request){var u=request as UpdateRequest;if(u==null)throw new NotImplementedException();writes++;if(writes==3&&FailOnThirdWrite)throw new FaultException<OrganizationServiceFault>(new OrganizationServiceFault{ErrorCode=-1,Message="simulated failure"});var row=Rows.Single(x=>x.Id==u.Target.Id);if(row.RowVersion!=u.Target.RowVersion)throw new Exception("Wrong optimistic version.");if(u.Target.Contains(ManagementPlanner.Env)||u.Target.Contains(ManagementPlanner.Server))NameWrites++;foreach(var p in u.Target.Attributes)row[p.Key]=p.Value;row.RowVersion=(Int32.Parse(row.RowVersion)+1).ToString();return new UpdateResponse();}
        public Guid Create(Entity e){throw new NotImplementedException();}public void Update(Entity e){throw new NotImplementedException();}public void Delete(string n,Guid id){throw new NotImplementedException();}public Entity Retrieve(string n,Guid id,ColumnSet c){throw new NotImplementedException();}public void Associate(string n,Guid id,Relationship r,EntityReferenceCollection e){throw new NotImplementedException();}public void Disassociate(string n,Guid id,Relationship r,EntityReferenceCollection e){throw new NotImplementedException();}
    }
}
