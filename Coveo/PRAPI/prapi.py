import requests
import json

def make_http_request(input):
    organization_id = input['Coveo_Organization_ID']
    search_token = input['Coveo_Search_Token']

    endpoint = f' https://{organization_id}.org.coveo.com/rest/search/v3/passages/retrieve'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {search_token}'
    }

    request_body = {
        'localization':  {
            "locale": "en-CA",
            "timezone": "America/Montreal"
        },
        'query': input['User_Query'],  
        'searchHub': input['Search_Hub'], 
        'maxPassages': 20
    }

    json_body = json.dumps(request_body)


    try:
        response = requests.post(endpoint, headers=headers, data=json_body)
        #print(f'HTTP Response Status: {response.status_code}')
        response.raise_for_status() 
        return response.json() 
    except requests.exceptions.RequestException as e:
        print(response)
        #print(f'Exception occurred during HTTP callout: {str(e)}')
        raise Exception(f'Failed to send request to Coveo API: {str(e)}')

if __name__ == "__main__":

    input_data = {
        'Coveo_Organization_ID': '[org_id]',
        'Coveo_Search_Token': '[api_key]',
        'User_Query': 'who is beyonce',
        'Pipeline' : '[Pipeline]',
        'Search_Hub' : '[SearchHub]'
    }

    response = make_http_request(input_data)
    print(response['items'])
