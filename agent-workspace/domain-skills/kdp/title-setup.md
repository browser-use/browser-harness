# Amazon KDP

Use the user's existing Chrome profile; KDP account and setup pages can require recent Amazon re-auth even when the title setup pages are still accessible.

## Title Setup

- Pricing URL pattern: `https://kdp.amazon.com/en_US/title-setup/kindle/<ASIN_OR_DRAFT_ID>/pricing`.
- The visible `Publish Your Kindle eBook` button shares the duplicate id `save-and-publish-announce` with many hidden buttons. Select the visible button by text, not id alone.
- KDP forms keep state in hidden inputs as well as visible controls. For KDP Select, check both `#data-is-select` and `#data-is-select-hidden`. For royalty, check `#data-digital-royalty-rate-hidden` and the `data[digital][royalty_rate]-radio` radios.
- The publish endpoint is `/pricing/action/save-and-publish?formId=form-main-1`. It can return HTTP 200 with a generic `saveError` and an empty `errors:{}` object, while the UI says only `Please fix the highlighted error(s) to continue`.
- Pricing-grid calls are useful for hidden royalty issues: `/pricing/pricing-grid/digital/conversion-and-royalty-preview/...`. `royaltyDegradationCode: KDP_SELECT_NOT_ENROLLED` can appear for IN/JP/BR/MX when using `70_PERCENT`, worldwide territories, and KDP Select off.
- KDP can show account/status blockers on the pricing page: `Account Information Incomplete` and `We're still setting up your account`. If KDP Select on or global `35_PERCENT` removes pricing degradation but publish still returns empty `errors:{}`, treat account/status gating as the likely blocker.
