public with sharing class CoveoQuestionAnswer {   
    @InvocableMethod(
        label='Answer question'
        description='Fetches relevant passages from Coveo using a query'
    )
    public static List<Response> getRelevantPassages(List<Request> requests) {
        System.debug('Coveo Question Answer - Start -' + requests[0].Query );
        
        // Construct the HTTP request
        HttpRequest req = new HttpRequest();
        req.setEndpoint('https://platform.cloud.coveo.com/rest/search/v3/passages/retrieve?organizationId=[org_id]');
        req.setMethod('POST');
        req.setHeader('Content-Type', 'application/json');
        req.setHeader('Authorization', 'Bearer [api_key]); // Replace with your access token

        // Log the request details
        System.debug('HTTP Request - Endpoint: ' + req.getEndpoint());
        System.debug('HTTP Request - Headers: Content-Type: ' + req.getHeader('Content-Type') + ', Authorization: ' + req.getHeader('Authorization'));

        // Prepare the request body
        Map<String, Object> requestBody = new Map<String, Object>();
        Map<String, Object> localization = new Map<String, Object>();
        localization.put('locale','en-CA');
        localization.put('timezone','America/Montreal');
        requestBody.put('query', requests[0].Query); // Using the input as the search query
        requestBody.put('searchHub', '[SearchHub]); // Adjust pipeline if necessary
        requestBody.put('maxPassages', 5);
        requestBody.put('localization', localization);
        
        // Convert the request body to JSON
        req.setBody(JSON.serialize(requestBody));

        // Log the request body
        System.debug('HTTP Request Body: ' + req.getBody());

        // Send the HTTP request
        Http http = new Http();
        HttpResponse res;
        String promptResponse = ''; // The response prompt to be returned
        try {
            res = http.send(req);
            System.debug('HTTP Response Status: ' + res.getStatusCode());
        } catch (Exception e) {
            System.debug('Exception occurred during HTTP callout: ' + e.getMessage());
            throw new CalloutException('Failed to send request to Coveo API: ' + e.getMessage());
        }

        // Handle the response
        if (res.getStatusCode() == 200) {
            System.debug('Processing successful HTTP response');
            Map<String, Object> responseBody = (Map<String, Object>)JSON.deserializeUntyped(res.getBody());
            List<Object> items = (List<Object>)responseBody.get('items');

            for (Object item : items) {
                Map<String, Object> itemMap = (Map<String, Object>)item;
                String text = (String)itemMap.get('text');
                promptResponse += text + '\n---\n'; // Accumulating text from all results
                System.debug('Accumulated Response Text: ' + text);
            }
        } else {
            System.debug('Error response from Coveo API: ' + res.getStatusCode() + ' ' + res.getStatus());
            throw new CalloutException('Error response from Coveo API: ' + res.getStatusCode() + ' ' + res.getStatus());
        }

        // Log the final prompt response
        System.debug('Final Prompt Response: ' + promptResponse);

        // Prepare the response list
        List<Response> responses = new List<Response>();
        Response output = new Response();
        output.Prompt = promptResponse;
        responses.add(output);

        // Log the end of the method execution
        System.debug('CoveoPassageRetrieval.getRelevantPassages - End');

        return responses;
    }
    
    // Type and API Name of all variables must match the template
    public class Request {
        @InvocableVariable(required=true)
        public String Query;
    }

    // Class that represents the output for the method
    public class Response {
        @InvocableVariable
        public String Prompt; // The required output
    }
}