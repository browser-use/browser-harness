# Cathedral runbook — Deploy proof

Use this when proving a deploy actually landed across code, platform, and edge.

Typical stack:
- GitHub
- Vercel
- Cloudflare

## Goal

Answer, with evidence:
- was code merged/pushed?
- did the deployment succeed?
- is the correct domain serving the correct build?
- is the edge/routing layer pointing where we think it is?

## Browser lane plan

- `github`
- `vercel`
- `cloudflare`

## Order of operations

1. **GitHub**
   - confirm branch / commit / workflow status / repo settings if relevant
2. **Vercel**
   - confirm latest attempted deploy vs latest successful deploy
   - capture production domain and deployment metadata
3. **Cloudflare**
   - confirm DNS and any Workers / Pages / proxy routing that could override behavior
4. **Terminal/API**
   - `curl -I`, cert check, response fingerprints, HTML markers

## Required output

- latest code state
- latest deployment state
- live domain behavior
- mismatch point if broken
- recommended next action

## Best use

This is the default post-deploy truth runbook when “it should be live” is not good enough.