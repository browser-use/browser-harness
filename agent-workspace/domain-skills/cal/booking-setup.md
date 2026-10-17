# Cal.com booking setup

Observed in the Cal.com v6.9 UI. Labels and routes may differ in later releases; inspect the current page before applying these notes.

## Event editor map

- **Links** is the event-type list (older instructions may call it **Event Types**).
- **Basics** contains the title, slug, duration, description, and location. **Link meeting** (`link_meeting`) accepts a fixed meeting URL. Selecting an installed conferencing app is a different location mode and may create a new room per booking.
- **Availability** selects the schedule used by this event.
- **Limits & buffers** contains before/after buffers, time-slot interval, minimum notice, and the future-booking date range.
- **Appearance** contains the booking-page timezone lock and its own timezone picker. The picker can initially show **Europe/London**; explicitly choose the intended timezone instead of assuming it inherits the availability schedule.
- **Privacy & security** contains the confirmation requirement.
- **Booking form** contains **Select**, **Long Text**, and **Add guests** controls. Set each question's required state separately.
- **Confirmation** contains the custom calendar event title. The attendee-name variable is `{Scheduler}`.
- The event's top visibility toggle can show **Hidden**. This hides it from the profile listing while its direct public booking URL still works.

## One-day availability

Create a dedicated schedule under **Availability**, select its timezone, turn off all recurring weekdays, and add a date override for the intended day and hours. Assign that schedule to the target event. Creating a schedule does not require making it the account default.

Time inputs are comboboxes: typing a value and pressing Tab can leave the previous value committed. Filter the choices, select the matching option, then verify the displayed start and end times after saving and reopening.

When replacing an existing booking date range with a single day, the range picker may require clicking the target date twice to set both endpoints. Read back both dates after saving; a highlighted calendar day alone is insufficient proof.

## Diagnosing missing slots

The authenticated troubleshooter route is:

```text
/availability/troubleshoot?eventTypeId=<event-type-id>&date=YYYY-MM-DD&month=YYYY-MM
```

It can explain why a displayed slot is unavailable. Compare the event duration, buffers, date override, notice, and connected-calendar conflicts before changing any settings.

The observed read-only availability request is a batched tRPC GET:

```text
/api/trpc/availability/user?batch=1&input=<URL-encoded JSON>
```

```json
{
  "0": {
    "json": {
      "username": "<username>",
      "dateFrom": "<range-start>",
      "dateTo": "<range-end>",
      "eventTypeId": 123,
      "withSource": true
    }
  }
}
```

Reuse the date formats and identifiers from the current page's observed request; this is a private endpoint and can change. Busy entries can include `calendarId`, `calendarName`, `start`, `end`, and `title`. Some calendar integrations supply only free/busy data: the UI may say **Busy** while `title` is null. Report the known calendar and time range, and explicitly state that the event title is unavailable. Do not invent a title or edit a conflicting event while diagnosing it.

## Event-specific calendar overrides

Availability > Check for conflicts has a **Use Account Settings / Use Link Settings** selector. Link settings apply to that event only. Switching from Account to Link can initialize with every calendar off instead of copying inherited selections; record and restore all intended checks explicitly. Individual calendar toggles persist asynchronously, so wait and reopen the editor before comparing checked states.

Calendar free/busy entries and Cal booking entries are separate: excluding a calendar does not remove an existing Cal booking conflict. When authorized to override a calendar hold, verify the remaining public slots and confirm the booked slot stays unavailable. A public no-availability message can mention a cutoff date even when a calendar block is the actual cause; inspect the saved range and troubleshooter before changing dates.

## Verification

Reopen saved editor sections and the public booking page. Verify the intended timezone, selectable dates, and exact slot count. For an authorized test booking, check the saved booking, fixed location in its confirmation, cancellation state, and that the released slot returns to the public picker.
