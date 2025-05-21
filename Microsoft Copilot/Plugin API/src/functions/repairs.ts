import { app, HttpRequest, HttpResponseInit, InvocationContext } from "@azure/functions";

export async function coveoPRAPI(
  req: HttpRequest,
  context: InvocationContext
): Promise<HttpResponseInit> {
  context.log("HTTP trigger function processed a request.");
  let items: any = {};

  const res: HttpResponseInit = {
    status: 200,
    jsonBody: {
      results: items,
    },
  };

  const query = req.query.get("query");

  const payload:any = {
                      'localization':  {
                        "locale": "en-CA",
                        "timezone": "America/Montreal"
                      },
                      'query': query,  
                      'searchHub': '[SearchHub]', 
                      'maxPassages': 20,
                    };

   const response = await fetch(
      "https://[org_id].org.coveo.com/rest/search/v3/passages/retrieve?organizationId=coveosearch",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer [apk_key]",
        },
        body: JSON.stringify(payload),
      }
    );

    if (response.ok) {
      items = await response.json();
      console.log(items);
    } else {
      context.log(`API Error: ${response.status} - ${response.statusText}`);
      return { status: response.status, body: response.statusText };
    }

  res.jsonBody.items = items;
  return res;
}

app.http("passages", {
  methods: ["GET"],
  authLevel: "anonymous",
  handler: coveoPRAPI,
});