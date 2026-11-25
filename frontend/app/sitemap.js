const site = "https://www.daytello.com";

export default function sitemap() {
  return ["/", "/signup", "/support", "/privacy-policy", "/term-of-service"]
    .map(path => ({ url: site + path }));
}
