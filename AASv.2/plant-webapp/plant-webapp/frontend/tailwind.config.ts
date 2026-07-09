import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        leaf: "#2f6b3a",
        soil: "#5c4033",
      },
    },
  },
  plugins: [],
};
export default config;
