import { defineConfig } from 'orval';

export default defineConfig({
  "api-gateway": {
    "input": {
      "target": "./openapi.yaml"
    },
    "output": {
      "target": "../gen/typescript-orval/api.ts",
      "schemas": "../gen/typescript-orval/models",
      "client": "axios",
      "mode": "split"
    }
  }
});