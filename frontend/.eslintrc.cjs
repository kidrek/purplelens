module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    node: true,
  },
  extends: ['eslint:recommended', 'plugin:vue/vue3-recommended'],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  rules: {
    // Beaucoup de vues du cockpit portent un nom métier mono-mot (Cockpit,
    // Journal, Admin...) — le routing par dossier suffit à éviter les collisions.
    'vue/multi-word-component-names': 'off',
  },
}
