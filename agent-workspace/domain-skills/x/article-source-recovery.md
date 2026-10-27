# Recover canonical sources from public X article cards

Use this when a public `x.com/<handle>/status/<id>` post contains an X Article card, but opening the card itself redirects an anonymous browser to login.

## Public status extraction

A public status page can render the post and article card without authentication even when the article route is gated. Inspect links in the post before clicking:

```javascript
Array.from(document.querySelectorAll('article a')).map(a => ({
  text: (a.innerText || '').trim(),
  href: a.href,
})).filter(x => x.href)
```

Article cards commonly point to `https://x.com/i/article/<id>`. An anonymous visit to that route may redirect to `x.com/i/jf/onboarding/web?...mode=login`; do not interpret this as evidence that the status itself is private or deleted.

## Cross-post fallback

Authors sometimes cross-post the same article on LinkedIn or another public profile and link the canonical external page there. A LinkedIn sign-in modal may cover the page visually while the public post text and anchors remain in the DOM.

Inspect the public DOM rather than entering credentials:

```javascript
({
  description: document.querySelector('meta[name="description"]')?.content || null,
  body: (document.body.innerText || '').slice(0, 12000),
  links: Array.from(document.querySelectorAll('a')).map(a => ({
    text: (a.innerText || '').trim(),
    href: a.href,
  })),
})
```

LinkedIn wraps external links as `https://www.linkedin.com/redir/redirect?url=<encoded-url>&...`. Decode the `url` query parameter, open that canonical URL directly, and validate the article title and content there.

## Guardrails

- Treat the X status and the author's canonical page as primary sources; comments and search snippets are secondary context.
- If no author-controlled canonical page is recoverable, cite the public status and mark the X Article body as inaccessible rather than reconstructing it from commentary.
- Never type credentials from screenshots or attempt to bypass a login wall.
