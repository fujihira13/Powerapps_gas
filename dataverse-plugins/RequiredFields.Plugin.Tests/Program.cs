using System;
using System.Collections.Generic;
using Microsoft.Xrm.Sdk;
using PowerappsGas.DataversePlugins;

namespace PowerappsGas.DataversePlugins.Tests
{
    internal static class Program
    {
        private static int _passed;
        private static int _failed;

        private static int Main()
        {
            Run("Create rejects each missing business field", CreateRejectsEachMissingBusinessField);
            Run("Create rejects null for each business field", CreateRejectsNullForEachBusinessField);
            Run("Create rejects empty and whitespace environment/server", CreateRejectsBlankStringFields);
            Run("Create accepts four valid business values", CreateAcceptsValidValues);
            Run("Create rejects run number zero", () => CreateRejectsRunNumber(0));
            Run("Create rejects negative run number", () => CreateRejectsRunNumber(-1));
            Run("Update rejects clearing each business field", UpdateRejectsClearingEachBusinessField);
            Run("Update rejects empty and whitespace environment/server", UpdateRejectsBlankStringFields);
            Run("Update merges changed Target values with unchanged PreImage values", UpdateMergesTargetAndPreImage);
            Run("Update accepts all four valid values in Target", UpdateAcceptsValidTargetValues);
            Run("Update rejects run number zero", () => UpdateRejectsRunNumber(0));
            Run("Update rejects negative run number", () => UpdateRejectsRunNumber(-1));
            Run("Update accepts an unrelated-field change when PreImage has valid business fields", UpdateAcceptsUnrelatedFieldChange);
            Run("Update rejects an omitted business field when its PreImage is absent", UpdateRejectsMissingPreImageValue);
            Run("A future dedicated test table is not blocked by an existing-table name constant", CreateAcceptsFutureDedicatedTableName);
            Run("Identical complete business tuples pass local validation; duplicate rejection remains the alternate key's responsibility", DuplicateTupleIsOutsidePluginValidation);

            Console.WriteLine("Local results: {0} passed, {1} failed.", _passed, _failed);
            Console.WriteLine("LIMIT: duplicate-key rejection and alternate-key Active state require Dataverse verification; this local run does not establish either.");
            return _failed == 0 ? 0 : 1;
        }

        private static void Run(string name, Action test)
        {
            try
            {
                test();
                _passed++;
                Console.WriteLine("PASS  " + name);
            }
            catch (Exception ex)
            {
                _failed++;
                Console.WriteLine("FAIL  " + name + " — " + ex.Message);
            }
        }

        private static void CreateRejectsEachMissingBusinessField()
        {
            foreach (var field in BusinessFields.All)
            {
                var target = BusinessFields.ValidCase();
                target.Attributes.Remove(field);
                ExpectRejected(CreateContext(target), "missing " + field, field);
            }
        }

        private static void CreateRejectsNullForEachBusinessField()
        {
            foreach (var field in BusinessFields.All)
            {
                var target = BusinessFields.ValidCase();
                target[field] = null;
                ExpectRejected(CreateContext(target), "null " + field, field);
            }
        }

        private static void CreateRejectsBlankStringFields()
        {
            foreach (var field in BusinessFields.StringFields)
            {
                foreach (var value in new[] { "", " \t\r\n " })
                {
                    var target = BusinessFields.ValidCase();
                    target[field] = value;
                    ExpectRejected(CreateContext(target), "blank " + field, field);
                }
            }
        }

        private static void CreateAcceptsValidValues()
        {
            Execute(CreateContext(BusinessFields.ValidCase()));
        }

        private static void CreateRejectsRunNumber(int runNumber)
        {
            var target = BusinessFields.ValidCase();
            target[BusinessFields.RunNumber] = runNumber;
            ExpectRejected(CreateContext(target), "run number " + runNumber, BusinessFields.RunNumber);
        }

        private static void UpdateRejectsClearingEachBusinessField()
        {
            foreach (var field in BusinessFields.All)
            {
                var target = new Entity(BusinessFields.LocalEntityName);
                target[field] = null;
                ExpectRejected(UpdateContext(target, BusinessFields.ValidCase()), "cleared " + field, field);
            }
        }

        private static void UpdateRejectsBlankStringFields()
        {
            foreach (var field in BusinessFields.StringFields)
            {
                foreach (var value in new[] { "", " \t\r\n " })
                {
                    var target = new Entity(BusinessFields.LocalEntityName);
                    target[field] = value;
                    ExpectRejected(UpdateContext(target, BusinessFields.ValidCase()), "blank " + field, field);
                }
            }
        }

        private static void UpdateMergesTargetAndPreImage()
        {
            var target = new Entity(BusinessFields.LocalEntityName);
            target[BusinessFields.Environment] = "更新後環境";
            target[BusinessFields.RunNumber] = 2;
            Execute(UpdateContext(target, BusinessFields.ValidCase()));
        }

        private static void UpdateAcceptsValidTargetValues()
        {
            Execute(UpdateContext(BusinessFields.ValidCase(), new Entity(BusinessFields.LocalEntityName)));
        }

        private static void UpdateRejectsRunNumber(int runNumber)
        {
            var target = new Entity(BusinessFields.LocalEntityName);
            target[BusinessFields.RunNumber] = runNumber;
            ExpectRejected(UpdateContext(target, BusinessFields.ValidCase()), "run number " + runNumber, BusinessFields.RunNumber);
        }

        private static void UpdateAcceptsUnrelatedFieldChange()
        {
            var target = new Entity(BusinessFields.LocalEntityName);
            target["cr6cb_caselabel"] = "更新ラベル";
            Execute(UpdateContext(target, BusinessFields.ValidCase()));
        }

        private static void UpdateRejectsMissingPreImageValue()
        {
            var preImage = BusinessFields.ValidCase();
            preImage.Attributes.Remove(BusinessFields.Server);
            var target = new Entity(BusinessFields.LocalEntityName);
            target[BusinessFields.Environment] = "更新後環境";
            ExpectRejected(UpdateContext(target, preImage), "missing server in PreImage", BusinessFields.Server);
        }

        private static void CreateAcceptsFutureDedicatedTableName()
        {
            var context = new PluginExecutionContext(
                "Create",
                BusinessFields.ValidCase(),
                null,
                "cr6cb_t007pluginverification");
            Execute(context);
        }

        private static void DuplicateTupleIsOutsidePluginValidation()
        {
            var first = BusinessFields.ValidCase();
            var second = BusinessFields.ValidCase();
            Execute(CreateContext(first));
            Execute(CreateContext(second));
        }

        private static void ExpectRejected(PluginExecutionContext context, string label, string expectedReason)
        {
            try
            {
                Execute(context);
            }
            catch (InvalidPluginExecutionException ex)
            {
                if (ex.Message == null || ex.Message.IndexOf(expectedReason, StringComparison.OrdinalIgnoreCase) < 0)
                {
                    throw new InvalidOperationException(
                        "Expected rejection reason containing '" + expectedReason + "' for " + label + ", but received: " + ex.Message);
                }

                return;
            }

            throw new InvalidOperationException("Expected InvalidPluginExecutionException for " + label + ".");
        }

        private static void Execute(PluginExecutionContext context)
        {
            new RequiredFieldsPlugin().Execute(new TestServiceProvider(context));
        }

        private static PluginExecutionContext CreateContext(Entity target)
        {
            return new PluginExecutionContext("Create", target, null);
        }

        private static PluginExecutionContext UpdateContext(Entity target, Entity preImage)
        {
            return new PluginExecutionContext("Update", target, preImage);
        }
    }

    internal static class BusinessFields
    {
        public const string LocalEntityName = "cr6cb_localplugintest";
        public const string Environment = "cr6cb_environment";
        public const string Server = "cr6cb_server";
        public const string RunNumber = "cr6cb_runnumber";
        public const string TargetDate = "cr6cb_targetdate";
        public const string PreImageName = "PreImage";

        public static readonly string[] All = { Environment, Server, RunNumber, TargetDate };
        public static readonly string[] StringFields = { Environment, Server };

        public static Entity ValidCase()
        {
            var entity = new Entity(LocalEntityName);
            entity[Environment] = "架空環境A";
            entity[Server] = "架空サーバーA";
            entity[RunNumber] = 1;
            entity[TargetDate] = new DateTime(2026, 9, 25);
            return entity;
        }
    }

    internal sealed class TestServiceProvider : IServiceProvider
    {
        private readonly PluginExecutionContext _context;

        public TestServiceProvider(PluginExecutionContext context)
        {
            _context = context;
        }

        public object GetService(Type serviceType)
        {
            return serviceType == typeof(IPluginExecutionContext) ? _context : null;
        }
    }

    internal sealed class PluginExecutionContext : IPluginExecutionContext
    {
        public PluginExecutionContext(string messageName, Entity target, Entity preImage, string primaryEntityName = BusinessFields.LocalEntityName)
        {
            MessageName = messageName;
            PrimaryEntityName = primaryEntityName;
            InputParameters = new ParameterCollection();
            InputParameters["Target"] = target;
            PreEntityImages = new EntityImageCollection();
            if (preImage != null)
            {
                PreEntityImages[BusinessFields.PreImageName] = preImage;
            }
        }

        public int Mode { get { return 0; } }
        public int IsolationMode { get { return 0; } }
        public int Depth { get { return 1; } }
        public string MessageName { get; private set; }
        public string PrimaryEntityName { get; private set; }
        public Guid? RequestId { get { return null; } }
        public string SecondaryEntityName { get { return null; } }
        public ParameterCollection InputParameters { get; private set; }
        public ParameterCollection OutputParameters { get { return new ParameterCollection(); } }
        public ParameterCollection SharedVariables { get { return new ParameterCollection(); } }
        public Guid UserId { get { return Guid.Empty; } }
        public Guid InitiatingUserId { get { return Guid.Empty; } }
        public Guid BusinessUnitId { get { return Guid.Empty; } }
        public Guid OrganizationId { get { return Guid.Empty; } }
        public string OrganizationName { get { return "local-test"; } }
        public Guid PrimaryEntityId { get { return Guid.Empty; } }
        public EntityImageCollection PreEntityImages { get; private set; }
        public EntityImageCollection PostEntityImages { get { return new EntityImageCollection(); } }
        public EntityReference OwningExtension { get { return null; } }
        public Guid CorrelationId { get { return Guid.Empty; } }
        public bool IsExecutingOffline { get { return false; } }
        public bool IsOfflinePlayback { get { return false; } }
        public bool IsInTransaction { get { return true; } }
        public Guid OperationId { get { return Guid.Empty; } }
        public DateTime OperationCreatedOn { get { return DateTime.UtcNow; } }
        public int Stage { get { return 10; } }
        public IPluginExecutionContext ParentContext { get { return null; } }
    }
}
