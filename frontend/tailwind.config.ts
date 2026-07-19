import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        core: "#ff8a3d",      // orange core ring
        accent: "#2dd4bf",    // teal particles / active state
        node: "#1a2030",
        nodedim: "#11151f",
      },
      boxShadow: {
        glow: "0 0 24px rgba(45, 212, 191, 0.55)",
        coreglow: "0 0 60px rgba(255, 138, 61, 0.55)",
      },
    },
  },
  plugins: [],
};
export default config;
