import logging
import azure.functions as func
from .cred_wrapper import CredentialWrapper
from azure.mgmt.keyvault import KeyVaultManagementClient
from msrestazure.tools import parse_resource_id


def main(msg: func.QueueMessage) -> None:
    logging.info('Python queue trigger function processed a queue item: %s', msg.get_body().decode('utf-8'))
    resource_id = msg.get_body().decode('utf-8')
    parse_res = parse_resource_id(resource_id)
    '''
    AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET
    The default credential first checks environment variables for configuration as described above.
    If environment configuration is incomplete, it will try managed identity.
    
    credential = DefaultAzureCredential()
    
    Ref: https://docs.microsoft.com/en-us/azure/developer/python/azure-sdk-authenticate-hosted-applications#credential-object-has-no-attribute-signed_session
    '''
    cred = CredentialWrapper()
    key_client = KeyVaultManagementClient(credentials=cred, subscription_id=parse_res.get('subscription'))
    require_property = {
        "enable_soft_delete" : True,
        "enable_purge_protection" : True
    }
    try:
        updateResult = key_client.vaults.update(
            resource_group_name=parse_res.get('resource_group'),
            vault_name=parse_res.get('resource_name'),
            properties=require_property)
        print(updateResult)
        logging.info("Key Vault enabled soft delete and purge delete on "+ resource_id)
    except Exception as exc:
        logging.info("Error while enable soft delete and purge delete on "+ resource_id + " and the error is " + str(exc))
