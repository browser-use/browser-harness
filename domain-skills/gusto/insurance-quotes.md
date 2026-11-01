# Gusto business insurance quote intake

- Entry point: `https://app.gusto.com/business-insurance/insurance-hub` (Taxes & compliance > Business insurance).
- The business owner policy card's quote button opens an embedded ERGO NEXT / AP Intego panel, rather than navigating the main tab. Compositor clicks work through the panel.
- The initial state can be prefilled from the company's older address. Set the actual state being quoted explicitly using the autocomplete result.
- Email validation may suggest replacing a legitimate `.ai` address with `.at`. Preserve the verified original with **Continue with Original**.
- Coverage choices include General Liability, Workers Compensation, Professional Liability, Commercial Auto, Commercial Property, and Other. A technology-services request including property and Other can route to **Work with an agent**, rather than an instant-price application. Do not imply that this referral form captures individual limits or guarantees availability of umbrella coverage.
- Agent intake prefills contact details. The address field can reveal separate city/state/ZIP fields only after an initial submit. USPS validation can reject a spelled-out floor designation; use the verified postal formatting, such as `FL` followed by the actual floor. Do not substitute a different insured location to pass validation.
- Success is explicitly shown as **Thanks! An agent is on it.**, with a stated response time of one business day. This is a contact/quote request, not a binder or a priced quote. Detailed limits and endorsements still need to be supplied to the agent if the intake has no notes field.
