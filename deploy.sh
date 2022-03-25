#! /bin/bash
set -e

read -p "Enter the Azure resource group name: " RESOURCE_GROUP
read -p "Enter the Azuere function app name: " FUNCTION_APP
read -p "Enter the Azure location (centralus, eastus, etc.): " LOCATION
read -p "Enter the API token for the Netskope tenant: " TOKEN

echo "[EXECUTING] Creating Azure Resource Group: $RESOURCE_GROUP"
rgExist=`az group exists -n $RESOURCE_GROUP`
if [ $rgExist == 'false' ]; then
    i=0
    az group create --name $RESOURCE_GROUP --location $LOCATION
    while [ $rgExist == 'false' ] && [ $i -lt 10 ]; do
        echo .\r
        sleep 5
        rgExist=`az group exists -n $RESOURCE_GROUP`
        i=$[$i+1]
    done
fi
echo "[DONE]"

# TODO: Leverage KeyVault for token storage.
# echo "[EXECUTING] Creating API token keyvault in group: $RESOURCE_GROUP"
# VAULT_NAME=${FUNCTION_APP:0:17}-vault
# echo "    Vault: $VAULT_NAME"
# az keyvault create \
#   --name $VAULT_NAME \
#   --resource-group $RESOURCE_GROUP \
#   --location $LOCATION \
#   --enabled-for-template-deployment true
# az keyvault secret set --vault-name $VAULT_NAME --name "nsToken" --value $TOKEN
# echo "[DONE]"

echo "[EXECUTING] Deploying ARM template for function application: $FUNCTION_APP"
az deployment group create \
    --name $FUNCTION_APP \
    --resource-group $RESOURCE_GROUP \
    --template-file ARM/deploy.json \
    --parameters ARM/deploy.parameters.json \
    --parameters appName=$FUNCTION_APP location=$LOCATION apiToken=$TOKEN

appSvcExist='false'
i=0
while [ $appSvcExist == 'false' ] && [ $i -lt 10 ]; do
    echo .\r
    sleep 5
    result=`az appservice plan list --query "[?name=='$FUNCTION_APP']"`
    if [ ${#result} -lt 5]; then
        appSvcExist='false'
    else
        appSvcExist='true'
    fi
    i=$[$i + 1]
done
echo "[DONE]"

echo "[EXECUTING] Publishing function code to function application: $FUNCTION_APP"
func azure functionapp publish $FUNCTION_APP
echo "[DONE]"