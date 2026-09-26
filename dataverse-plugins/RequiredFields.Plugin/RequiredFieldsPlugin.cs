using System;
using Microsoft.Xrm.Sdk;

namespace PowerappsGas.DataversePlugins
{
    public sealed class RequiredFieldsPlugin : IPlugin
    {
        private const string EnvironmentField = "cr6cb_environment";
        private const string ServerField = "cr6cb_server";
        private const string RunNumberField = "cr6cb_runnumber";
        private const string TargetDateField = "cr6cb_targetdate";
        private const string PreImageName = "PreImage";

        public void Execute(IServiceProvider serviceProvider)
        {
            if (serviceProvider == null)
            {
                throw new InvalidPluginExecutionException("A Dataverse plug-in execution context is required.");
            }

            var context = serviceProvider.GetService(typeof(IPluginExecutionContext)) as IPluginExecutionContext;
            if (context == null)
            {
                throw new InvalidPluginExecutionException("The Dataverse plug-in execution context is unavailable.");
            }

            var isCreate = string.Equals(context.MessageName, "Create", StringComparison.OrdinalIgnoreCase);
            var isUpdate = string.Equals(context.MessageName, "Update", StringComparison.OrdinalIgnoreCase);
            if (!isCreate && !isUpdate)
            {
                return;
            }

            // The dedicated test table's logical name is undecided at this phase.
            // Scope the eventual registration through the exact entity on each step; do not bind this candidate to an existing table.
            if (context.InputParameters == null || !context.InputParameters.Contains("Target") || !(context.InputParameters["Target"] is Entity))
            {
                throw new InvalidPluginExecutionException("The Dataverse Target entity is missing or invalid.");
            }

            var target = (Entity)context.InputParameters["Target"];
            Entity preImage = null;
            if (isUpdate && context.PreEntityImages != null && context.PreEntityImages.Contains(PreImageName))
            {
                preImage = context.PreEntityImages[PreImageName];
            }

            ValidateString(target, preImage, EnvironmentField, "environment");
            ValidateString(target, preImage, ServerField, "server");
            ValidateInteger(target, preImage, RunNumberField, "run number");
            ValidateDate(target, preImage, TargetDateField, "target date");
        }

        private static void ValidateString(Entity target, Entity preImage, string field, string label)
        {
            var value = GetEffectiveValue(target, preImage, field);
            if (!(value is string) || string.IsNullOrWhiteSpace((string)value))
            {
                throw InvalidRequiredValue(field, label);
            }
        }

        private static void ValidateInteger(Entity target, Entity preImage, string field, string label)
        {
            var value = GetEffectiveValue(target, preImage, field);
            if (!(value is int) || (int)value < 1)
            {
                throw new InvalidPluginExecutionException(
                    "The required " + label + " field '" + field + "' must be an integer greater than or equal to 1.");
            }
        }

        private static void ValidateDate(Entity target, Entity preImage, string field, string label)
        {
            var value = GetEffectiveValue(target, preImage, field);
            if (!(value is DateTime))
            {
                throw InvalidRequiredValue(field, label);
            }
        }

        private static object GetEffectiveValue(Entity target, Entity preImage, string field)
        {
            // An explicitly supplied null in Target must override an older PreImage value.
            if (target.Attributes.Contains(field))
            {
                return target[field];
            }

            if (preImage != null && preImage.Attributes.Contains(field))
            {
                return preImage[field];
            }

            return null;
        }

        private static InvalidPluginExecutionException InvalidRequiredValue(string field, string label)
        {
            return new InvalidPluginExecutionException(
                "The required " + label + " field '" + field + "' must have a non-empty value.");
        }
    }
}
