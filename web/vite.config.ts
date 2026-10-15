/// <reference types="vitest/config" />
import preact from '@preact/preset-vite';
import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  plugins: [preact()],
  test: {
    include: ['testler/birim/**/*.test.ts'],
  },
});
