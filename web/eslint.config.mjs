import globals from "globals";

export default [
  { ignores: ["public/**"] },
  {
    files: ["assets/**/*.mjs", "sw.js"],
    languageOptions: {
      globals: { ...globals.browser, ...globals.serviceworker },
    },
  },
  {
    files: ["*.cjs", "build.js", "qa/**/*.mjs", "eslint.config.mjs"],
    languageOptions: { globals: globals.node },
  },
  {
    files: ["**/*.js", "**/*.mjs", "**/*.cjs"],
    rules: {
      "no-undef": "error",
      "no-unreachable": "error",
      "no-dupe-keys": "error",
      "no-duplicate-imports": "error",
      "no-var": "error",
    },
  },
];
