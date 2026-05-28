import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/unit/**/*.{test,spec}.ts'],
    coverage: {
      provider: 'v8',
      exclude: ['src/api/generated/**', 'src/main.ts', '**/*.d.ts', 'tests/**', '**/*.config.*'],
      reporter: ['text', 'html', 'lcov'],
      thresholds: { lines: 60, functions: 60, branches: 50, statements: 60 },
    },
  },
})
