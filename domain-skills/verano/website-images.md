# Verano website image discovery

The public site is at `https://verano.fi/`. Service pages under `/it-ratkaisut/` are linked from the home navigation and include IT services, software, AI, modern work and hardware. Static HTML is sufficient for bulk discovery; a browser is unnecessary for most asset downloads.

Images may be in normal `img`/`srcset` markup or inline Elementor background settings. Looking only at image elements misses service hero compositions. Parse HTML attributes and background/settings URLs, decoding JSON-escaped slashes and HTML entities.

Many assets are served from `res.cloudinary.com/nestit/images/` through SEO image URLs, including optional `w_<width>,h_<height>,c_scale/`, format/quality transforms, a version, a public ID and a filename. Responsive variants of the same filename are not distinct photographs. Strip trailing HTML quotes from extracted URLs, group matching image identities, and prefer the largest published variant. Other files are first-party WordPress uploads under `/wp-content/uploads/` with responsive dimension suffixes.

Inspect decoded dimensions and visual contact sheets before selecting files. The site mixes workplace imagery and muted conceptual service illustrations with logos, certification badges, SVG brand devices and article graphics. A service-page context does not turn a conceptual illustration into a product screenshot or establish the identity of pictured people. Preserve source page/asset URLs and downloaded-byte hashes when collecting authorised assets.
