# Viewport

Cover how viewport size changes affect layout, coordinate clicks, and any workflow that depends on stable geometry.

## Touch emulation

`maxTouchPoints` is optional, but Chrome validates it as 1–16 even when touch
emulation is being disabled. Omit it when disabling:

```js
cdp("Emulation.setTouchEmulationEnabled", {enabled: true, maxTouchPoints: 5});
cdp("Emulation.setTouchEmulationEnabled", {enabled: false});
```

Do not pass `maxTouchPoints: 0`; Chrome rejects the supplied value before acting
on `enabled: false`.
