import requests
import json

def make_http_request(input):
    organization_id = input['Coveo_Organization_ID']
    search_token = input['Coveo_Search_Token']
    config_id = input['Coveo_Config_ID']
    pipeline = input['Pipeline']
    search_hub = input['Search_Hub'] 

    endpoint = f'https://{organization_id}.org.coveo.com/rest/organizations/{organization_id}/answer/v1/configs/{config_id}/generate'
    headers = {
        'accept': "application/json, text/event-stream",
        'content-type': 'application/json',
        'Authorization': f'Bearer {search_token}',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
    }

    request_body = {
        'q': input['User_Query'],  
        'searchHub': search_hub,
        'pipeline' : pipeline,
        "context": "{answerAPI:true}",
        "pipelineRuleParameters": {
            "mlGenerativeQuestionAnswering": {
                "responseFormat": {
                    "contentFormat": ["text/markdown", "text/plain"]
                }
            }
        }
    }

    json_body = json.dumps(request_body)

    try:

        response = requests.post(endpoint, headers=headers, data=json_body, stream=True)
        full_text = []
        for line in response.iter_lines():
            if line:
                decoded = line.decode("utf-8")
                if decoded.startswith("data: "):
                    try:
                        data_json = json.loads(decoded[6:]) 
                        payload_type = data_json.get("payloadType")
                        payload_raw = data_json.get("payload")

                        if payload_raw:
                            payload = json.loads(payload_raw)

                            if payload_type == "genqa.messageType":
                                delta = payload.get("textDelta", "")
                                print(delta, end="")
                                full_text.append(delta)
                    except Exception as e:
                        print("Failed to parse line:", decoded)
                        print("Error:", e)

        return "".join(full_text)

    except requests.exceptions.RequestException as e:
        print(response.__dict__)
        print(f'Exception occurred during HTTP callout: {str(e)}')
        raise Exception(f'Failed to send request to Coveo API: {str(e)}')

if __name__ == "__main__":

    input_data = {
        'Coveo_Config_ID' : '[answer config id]',
        'Coveo_Organization_ID': '[org id]',
        'Coveo_Search_Token': '[api key]',
        'User_Query': '[query]',
        'Pipeline' : '[pipeline]',
        'Search_Hub' : '[search hub]'
    }

    make_http_request(input_data)
