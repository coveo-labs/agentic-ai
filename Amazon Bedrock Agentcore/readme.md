# Agentcore Runtime Agent

## Variable to replace
MEMORY_ID = "[Agentcore_Memory_Id]"

## Deploy
Login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin [AWS_ORG_ID].dkr.ecr.us-east-1.amazonaws.com

Build Docker image
docker buildx build --platform linux/arm64 -t [AWS_ORG_ID].dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-agent:v1 .

Publish Docker Image
docker push [AWS_ORG_ID].dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-agent:v1


# Streamlit Client

## Variable to replace
default_aws_org_id = "[AWS Organization ID]"
default_client_id = "[Cognito Client ID]"
default_region = "us-east-1"
default_agent = "[Agentcore Runtime Agent ID ]"
default_runtime_user_id = "[Runtime User ID]"
default_qualifier = "DEFAULT"
default_user_id = "[Cognito Username]"
default_user_pwd= "[Cognito Password]"
default_mcp_url = "https://platform.cloud.coveo.com/api/private/organizations/[org_d]/mcp/server/[mcp_config_id]"

## Start
streamlit run streamlit_app.py
