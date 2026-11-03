import { defineConfig } from "vitest/config";

// Next.js tsconfig memakai "jsx": "preserve" (untuk compiler Next).
// Vitest perlu transform JSX sendiri — automatic runtime React 18/17+.
export default defineConfig({
  esbuild: {
    jsx: "automatic",
  },
  test: {
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    environment: "node",
  },
});
