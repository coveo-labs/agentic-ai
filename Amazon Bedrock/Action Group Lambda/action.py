import json
import http.client
import urllib.parse
import time

def lambda_handler(event, context):

    print(event)
    print(context)
    
    apiPath = event["apiPath"]
    org_id = "[org_id]"
    server = f"{org_id}.org.coveo.com"
    search_token = "[api_key]"
    query = event["inputText"]
    searchHub = "[searchHub]"

    #if you want to use the repharse query from bedrock
    #for prop in event['requestBody']['content']['application/json']['properties']:
    #    if prop['name'] == 'query':
    #        query = prop['value']
    
    api_url = f"{apiPath}?organizationId={org_id}"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {search_token}'
    }

    request_body = {
        'localization':  {
            "locale": "en-CA",
            "timezone": "America/Montreal"
        },
        'query': query,
        'additionalFields' : ['clickableuri'],
        'searchHub': searchHub, 
        'maxPassages': 5
    }

    json_body = json.dumps(request_body)

    try:
        # Create an HTTP connection
        connection = http.client.HTTPSConnection(server)
        print("connection",connection)
        
        # Send POST request
        connection.request("POST", api_url, body=json_body, headers=headers)

        # Get response
        response = connection.getresponse()
        response_body = response.read().decode('utf-8')
        
        print(f'HTTP Response Status: {response.status}, Reason: {response.reason}')
        
        if response.status >= 200 and response.status < 300:
            response_data = json.loads(response_body)['items']
            
            for ind, data in enumerate(response_data,start=1):
                print(f"Chunk #{ind} : {data}")
            
            if 'requestBody' in event:
                action_response = {
                    "actionGroup": event["actionGroup"],
                    "apiPath": event["apiPath"],
                    "httpMethod": event["httpMethod"],
                    "parameters": event["parameters"],
                    "httpStatusCode": response.status,
                    "responseBody": response_data,
                }

                session_attributes = event.get("sessionAttributes", {})
                prompt_session_attributes = event.get("promptSessionAttributes", {})

                return {
                    "messageVersion": "1.0",
                    "response": action_response,
                    "sessionAttributes": session_attributes,
                    "promptSessionAttributes": prompt_session_attributes,
                }
            else:
                strResult = ", ".join(item['text'] for item in response_data)
                return strResult
        else:
            raise Exception(f'Failed to send request to Coveo API: {response.status}, {response.reason}')
    
    except Exception as e:
        print(f'Exception occurred during HTTP callout: {str(e)}')
        raise Exception(f'Failed to send request to Coveo API: {str(e)}')

    finally:
        connection.close()