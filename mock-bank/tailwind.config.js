/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        canvas: "#eef2f7",
        surface: "#ffffff",
        line: "#e2e8f0",
        navy: { DEFAULT: "#1e3a5f", 700: "#1b3453", 900: "#14273f" },
        accent: "#2563eb",
        positive: "#047857",
        warning: "#b45309",
        danger: "#b91c1c",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      borderRadius: { card: "0.625rem" },
      boxShadow: {
        card: "0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.06)",
      },
    },
  },
  plugins: [],
};
