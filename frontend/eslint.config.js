// ESLint flat configuration (VIII §49.2 stage 1): TypeScript rules, React rules, and react/no-danger as an error,
// since dangerouslySetInnerHTML would bypass the strict CSP (VII §37.3).
import js from "@eslint/js";
import react from "eslint-plugin-react";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist/", "node_modules/"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: { react },
    settings: { react: { version: "detect" } },
    rules: {
      ...react.configs.recommended.rules,
      ...react.configs["jsx-runtime"].rules,
      "react/no-danger": "error",
    },
  },
);
