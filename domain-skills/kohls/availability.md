# Kohl’s product availability

Product URLs can include a color query parameter, but that does not guarantee the color is available. The initial render may show the requested color, photo, and price before client-side inventory loads. Once loaded, the page may silently switch to another available color.

For stock checks, inspect the final selected color and available swatches after loading, along with the enabled Add to Cart button. Verify again with a screenshot. Do not treat an indexed product snippet, the URL color parameter, or the initial product image as confirmation of current color availability.

Shipping estimates may depend on the browser’s location or stored preferences; do not assume those match the user’s destination.
