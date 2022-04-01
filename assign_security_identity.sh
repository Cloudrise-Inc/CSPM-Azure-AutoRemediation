#! /bin/bash
set -e

read -p "Enter the Azure security function app name: " FUNCTION_APP
read -p "Enter the target Azure subscription name: " SUBSCRIPTION
read -p "Enter the target Azure resource group name: " RESOURCE_GROUP
read -p "Enter the target Azure storage account: " STORAGE_ACCOUNT

SP=`az account subscription list --query "[?displayName=='$SUBSCRIPTION'].subscriptionId | [0]"`
SP=`sed -e 's/^"//' -e 's/"$//' <<<"$SP"`
FA=`az ad sp list --display-name $FUNCTION_APP --query "[?displayName=='$FUNCTION_APP'].objectId | [0]" --all`
FA=`sed -e 's/^"//' -e 's/"$//' <<<"$FA"`
SCOPE="/subscriptions/${SP}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT}"

az role assignment create \
    --role "Storage Blob Data Contributor" \
    --assignee-object-id $FA \
    --assignee-principal-type ServicePrincipal \
    --scope $SCOPE
