public class CoveoEinsteinModelPRAPI {
    @InvocableMethod(label='Coveo Einstein Model PR API' description='Give a summary with Coveo PR API related to a case' category='Case')
    
    public static List<Response> getRelevantPassages(List<Case> queries) {
        System.debug('CoveoPassageRetrieval.getRelevantPassages - Start - Case Description: ' + queries);
        // Log the start of the method execution
        System.debug('CoveoPassageRetrieval.getRelevantPassages - Start - Case Description: ' + queries[0].Description + 'Case Subject' + queries[0].Subject);
        
        // Construct the HTTP request
        HttpRequest req = new HttpRequest();
        req.setEndpoint('https://platform.cloud.coveo.com/rest/search/v3/passages/retrieve?organizationId=[org_id]');
        req.setMethod('POST');
        req.setHeader('Content-Type', 'application/json');
        req.setHeader('Authorization', 'Bearer [api_key]');

        // Log the request details
        System.debug('HTTP Request - Endpoint: ' + req.getEndpoint());
        System.debug('HTTP Request - Headers: Content-Type: ' + req.getHeader('Content-Type') + ', Authorization: ' + req.getHeader('Authorization'));

        // Prepare the request body
        Map<String, Object> requestBody = new Map<String, Object>();
        Map<String, Object> localization = new Map<String, Object>();
        localization.put('locale','en-CA');
        localization.put('timezone','America/Montreal');
        requestBody.put('query', queries[0].Subject.replaceAll(' ',', ')); // Using the input as the search query
        requestBody.put('searchHub', '[searchHub]'); // Adjust pipeline if necessary
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
                promptResponse += '"""'+ text + '""",'; // Accumulating text from all results
                System.debug('Accumulated Response Text: ' + text);
            }
        } else {
            System.debug('Error response from Coveo API: ' + res.getStatusCode() + ' ' + res.getStatus() +' X-Request-ID :'+ res.getHeader('X-Request-ID'));
            throw new CalloutException('Error response from Coveo API: ' + res.getStatusCode() + ' ' + res.getStatus() + ' X-Request-ID :' + res.getHeader('X-Request-ID'));
        }

        // Log the final prompt response
        System.debug('Final Prompt Response: ' + promptResponse);

        // Prepare the response list
        List<Response> responses = new List<Response>();
        Response output = new Response();
        output.Prompt = getAnswer(promptResponse);
        responses.add(output);

        // Log the end of the method execution
        System.debug('CoveoPassageRetrieval.getRelevantPassages - End');

        return responses;
    }
    
    public static string getAnswer(string chunks){
        // Create generate text request
		aiplatform.ModelsAPI.createGenerations_Request request = new aiplatform.ModelsAPI.createGenerations_Request();

		// Specify model
		request.modelName = 'sfdc_ai__DefaultOpenAIGPT4OmniMini';

        // Create request body
        aiplatform.ModelsAPI_GenerationRequest requestBody = new aiplatform.ModelsAPI_GenerationRequest();
        request.body = requestBody;

        // Add prompt to body
        requestBody.prompt = 'Generate short summary with those passages only : ' + chunks;

        try {
            // Make request
            aiplatform.ModelsAPI modelsAPI = new aiplatform.ModelsAPI();
            aiplatform.ModelsAPI.createGenerations_Response response = modelsAPI.createGenerations(request);
            System.debug('Models API response: ' + response.Code200.generation.generatedText);
            return response.Code200.generation.generatedText;
        
        // Handle error
        } catch(aiplatform.ModelsAPI.createGenerations_ResponseException e) {
            System.debug('Response code: ' + e.responseCode);
            System.debug('The following exception occurred: ' + e);
            return 'Error';
        }
     
    }

    // Class that represents the output for the method
    public class Response {
        @InvocableVariable
        public String Prompt; // The required output
    }
}