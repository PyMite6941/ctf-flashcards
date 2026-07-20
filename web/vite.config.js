import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// build.outDir 'dist' is what Capacitor points its webDir at when wrapping
// the web app into the Android / iOS shells.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
