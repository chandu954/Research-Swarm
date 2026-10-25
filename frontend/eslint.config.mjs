import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { FlatCompat } = require("@eslint/eslintrc");
const compat = new FlatCompat({ baseDirectory: process.cwd() });

const eslintConfig = [
  ...compat.extends("next/core-web-vitals"),
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "next-env.d.ts",
      "tsconfig.tsbuildinfo",
      "coverage/**",
      "playwright-report/**",
      "test-results/**",
    ],
  },
];

export default eslintConfig;
