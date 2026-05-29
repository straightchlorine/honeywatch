import { defineConfig } from '@hey-api/openapi-ts'

// Input is the committed `api/openapi.json` snapshot.
// If the file is missing on a fresh clone, run `just openapi-regen` first
// (or `just api-openapi`).
export default defineConfig({
  input: '../api/openapi.json',
  output: {
    path: './src/api/generated',
    postProcess: ['prettier'],
  },
  plugins: [
    '@hey-api/typescript',
    '@hey-api/sdk',
    {
      name: '@hey-api/client-fetch',
      runtimeConfigPath: './src/api/runtime-config.ts',
    },
    {
      name: '@tanstack/vue-query',
      queryOptions: {
        enabled: true,
        name: '{{name}}Options',
      },
      queryKeys: {
        enabled: true,
        name: '{{name}}QueryKey',
        tags: true,
      },
      infiniteQueryOptions: {
        enabled: true,
        name: '{{name}}InfiniteOptions',
      },
      infiniteQueryKeys: {
        enabled: true,
        name: '{{name}}InfiniteQueryKey',
        tags: true,
      },
      mutationOptions: {
        enabled: true,
        name: '{{name}}Mutation',
      },
    },
  ],
})
