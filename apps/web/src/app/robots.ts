import type { MetadataRoute } from "next";

import { siteUrl } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // Search result pages duplicate the city pages; the admin panel is private.
      disallow: ["/api/", "/fa/search", "/en/search", "/fa/admin", "/en/admin"],
    },
    sitemap: `${siteUrl()}/sitemap.xml`,
  };
}
