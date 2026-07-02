# Deploy runbook — josephbankole.ca

Static site. Repo is built and committed locally. Deploys to GitHub Pages on the
existing (empty) repo `josephbankole/josephbankole-site`, custom domain `josephbankole.ca`,
DNS at Web Hosting Canada. Brand inherited from The ARCHV (navy/cream/gold, Fraunces +
Inter Tight); funnel mechanics from JoeySDR.

## 1. Push the site (run on your Mac, where your GitHub creds live)

```bash
cd ~/Claude/personal-brand/josephbankole-site
git push -u origin main
```

(The repo is already initialised, committed, and the `origin` remote is set to
`https://github.com/josephbankole/josephbankole-site.git`.)

## 2. Turn on GitHub Pages

GitHub repo → Settings → Pages → Build and deployment → Source: **Deploy from a branch**
→ Branch: **main** / **/ (root)** → Save. The `CNAME` file (already in the repo) sets the
custom domain to `josephbankole.ca`. Leave "Enforce HTTPS" ticked once the cert issues.

## 3. Point DNS at Web Hosting Canada (clients.whc.ca → josephbankole.ca → DNS)

Apex `josephbankole.ca` → four A records to GitHub Pages:

```
A   @   185.199.108.153
A   @   185.199.109.153
A   @   185.199.110.153
A   @   185.199.111.153
```

And the www alias:

```
CNAME   www   josephbankole.github.io.
```

Remove any conflicting existing A/AAAA on the apex. Propagation is usually under an hour.
GitHub then issues the HTTPS cert automatically (can take up to ~24h).

## 4. Newsletter (no setup needed)

`index.html` → the subscribe section embeds the ARCHV AI Substack
(archvai.substack.com/embed), which handles email capture directly. No Web3Forms key
or backend required. Done 2026-07-01. Contact email across the site is
partnerships@josephbankole.ca (Zoho mailbox).

## 5. SEO / search indexing (once the site resolves over HTTPS)

- Google Search Console (search.google.com/search-console): add property `josephbankole.ca`,
  verify by DNS TXT at WHC, then submit `https://josephbankole.ca/sitemap.xml`.
- Bing Webmaster Tools: add the site, import from GSC, submit the same sitemap.
- Request indexing on the homepage URL in GSC to prime the crawl.
- `robots.txt` and `sitemap.xml` are already in place and reference the live domain.

## Files
- `index.html` — home: hero, About, Projects (ARCHV + JoeySDR), blog/news teasers, consultation funnel, subscribe
- `blog/` — index + 5 articles (expanded + humanised from the LinkedIn post bank)
- `news/` — index + the 19 Jun 2026 agentic-commerce digest (sourced)
- `assets/style.css` — brand system · `assets/og.png` — social share image
- `CNAME`, `robots.txt`, `sitemap.xml`, `404.html`
