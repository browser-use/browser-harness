# Gastronovi — Public Reservation Widget

## Direct URL

The public widget can be opened without the restaurant page or iframe wrapper:

```text
https://services.gastronovi.com/restaurants/{restaurantId}/reservation/widget/referral?embed=1&companyRoute=1&fixedButton=0
```

`wait_for_load()` can finish before the reservation app renders. Wait for a button named `Reservierung` or `Reservation` before starting.

## Stable controls

- Start: button role with the exact name `Reservierung` or `Reservation`
- Guest count: exact button name (`2` through `6` in the public flow)
- Date: `button[aria-label="YYYY-MM-DD"]`
- Next calendar month: exact button name `Nächster Monat`
- Open time choices: exact button name `Uhrzeit wählen`
- Pick a time: exact button name such as `18:00`
- Check capacity: exact button name `Verfügbarkeit prüfen`
- Contact inputs: `#personaldata-firstname`, `#personaldata-customer-lastname`, `#personaldata-customer-email`, and `#personaldata-customer-telephone`
- Notes: `#personaldata-customer-notes`
- Continue to review: `#continueButton`

The widget's custom select boxes are not native `select` elements. Click `[role=button]` inside the box, then click `[role=option][data-key="..."]` inside the same box. Known box IDs include `#smartselectbox-gender` and IDs starting with `#smartSelectbox-additionalField-`.

## Safe review boundary

After `#continueButton`, wait for the exact text `Übersicht` and the exact button name `Reservierung abschließen`. This is the last safe point for a dry run. Do not click that final button unless the task clearly permits a real booking.

Take the proof screenshot only after both the heading and final button appear.

## Cloud egress trap

In July 2026, the public widget returned a plain nginx `403 Forbidden` page from a Vercel Sandbox in `iad1`, while it worked in a normal desktop browser. Check the initial navigation response before waiting for controls. A headless job should report the 403 clearly or use an explicit mock for a dry run; extra DOM waits do not fix it.

The staff backoffice sits behind login and may have different bot checks and limits. Do not treat the public widget's 2–6 guest limit as a backoffice rule.
