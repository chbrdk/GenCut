const tokens = require('./design-tokens.json');

module.exports = {
  content: [
    './templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        primary: tokens.color.primary,
        secondary: tokens.color.secondary,
        background: tokens.color.background,
        surface: tokens.color.surface,
        text: tokens.color.text,
      },
      spacing: {
        xs: tokens.spacing.xs,
        sm: tokens.spacing.sm,
        md: tokens.spacing.md,
        lg: tokens.spacing.lg,
      },
      borderRadius: {
        sm: tokens.radius.sm,
        md: tokens.radius.md,
        xl: tokens.radius.xl,
      },
    },
  },
  plugins: [],
}; 