# Overview of the declarative agent with API plugin that is using Coveo PR API

### How to add your own API Key

1. Open terminal and run command `npm install` to install all dependency packages

   ```
   > npm install
   ```

2. After `npm install` completed, run command `npm run keygen`
   ```
   > npm run keygen
   ```
3. The above command will output something like "Generated a new API Key: xxx..."
4. Fill in API Key into `env/.env.*.user`
   ```
   SECRET_API_KEY=<your-api-key>
   ```
