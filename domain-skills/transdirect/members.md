# Transdirect React members area

Use only the environment and member account authorized for the task. A local URL does not establish which backend it uses; confirm its configured API target before creating records. Do not infer that legacy PHP members routes and the React app share a session.

## Navigation and controls

- React routes include `/orders`, `/bookings`, `/billing`, `/stats`, and `/settings/addresses`. `/book?new=1` creates a fresh booking draft and redirects to `/book/<draft-id>`.
- Desktop navigation labels the dashboard **Dashboard**; the mobile bottom navigation labels it **Home**. A desktop-only link is a poor readiness check on a phone viewport.
- Booking addresses use **Ship From** and **Ship To** sections. Orders use **From (Sender)** and **To (Recipient)** with **Edit sender** and **Edit recipient** controls.
- Custom locality, state, and street-type controls expose `combobox` roles and options. Read current options instead of treating them as native selects. A warehouse-hours option can include both its readable time and its 24-hour hint in the accessible name.
- The Referrals screen uses tabs for **Past Referrals** and **Permalinks**.
- Empty billing accounts may have no pagination controls. Assert pagination only when the account actually has enough records.

## Verification traps

- Draft creation and a displayed quote do not prove booking completion. Require the visible confirmation screen, then verify the requested follow-on action such as reopening or cloning.
- When explicitly authorized to test in a preview environment, select the **Demo** courier and **Use test payment**. Verify that test payment is selected before confirming. Do not substitute another courier or a real payment method if these controls are unavailable.
- Courier quotes have desktop rows and mobile cards in the DOM at the same time. Scope quote selection to the visible layout before asserting `aria-selected`.
- Terms and warranty text can contain buttons opening informational dialogs. Operate the checkbox control when accepting an authorized test declaration.
- A cached saved-address or package row is weaker evidence than persistence. Reopen or reload and confirm the edited data, accounting for the app's persistent query cache.
- Rapid partial-address entry deserves explicit coverage: enter Unit before No. and Street, then check all fields after save and reopen.
- Vite can report a lazy page as failing to load when a dependency request returns **Outdated Optimize Dep**. Inspect the failed dependency response before attributing that development-server error to the page or backend.
