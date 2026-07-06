import type { MetadataRoute } from "next";

// PWA manifest (M7.5, D-023). Tamil-first name, editorial-paper theme.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "அறிவோம் · Arivom",
    short_name: "அறிவோம்",
    description:
      "தமிழ்நாடு குடிமக்களுக்கான வெளிப்படையான, நடுநிலை தகவல் தளம் · Transparent civic information for Tamil Nadu",
    start_url: "/",
    display: "standalone",
    background_color: "#faf8f3",
    theme_color: "#16646e",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      {
        src: "/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
