import type { CodegenConfig } from "@graphql-codegen/cli";

const config: CodegenConfig = {
  schema: process.env.VITE_API_URL ?? "http://localhost:8000/graphql",
  documents: ["src/graphql/operations.graphql"],
  generates: {
    "src/graphql/generated.ts": {
      plugins: ["typescript", "typescript-operations", "typed-document-node"],
    },
  },
  ignoreNoDocuments: true,
};

export default config;
