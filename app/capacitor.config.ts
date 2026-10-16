import type { CapacitorConfig } from "@capacitor/cli";

// Wraps the same React build as a native Android/iOS app. The WebView is a secure context, so
// getUserMedia (camera) works without HTTPS on the server. During development the app talks to the
// Chesstor API on your laptop via VITE_API_URL (see README "Phone app").
const config: CapacitorConfig = {
  appId: "pk.edu.nu.chesstor",
  appName: "Chesstor",
  webDir: "dist",
  server: { androidScheme: "https", cleartext: true },
};

export default config;
