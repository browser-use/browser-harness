# eBool submissions

- `/submit` shows listing plans. The free route links to `/submit/start?plan=free` with a long standard consideration queue; paid placement is distinct.
- The form creates a vendor account at the final step. Fields use Livewire bindings such as `wire:model="contact_name"`, `email`, `password`, `password_confirmation`, `product`, `website_url`, `company`, `country`, `description`, and `logo`.
- Description accepts 100–500 plain-text characters. Logo upload has a small file-size limit; inspect the current requirement before upload.
- Primary category search uses `wire:model.live.debounce.400ms="primaryCategorySearch"`, with results exposing `wire:click="selectPrimaryCategory(...)"`.
- Category fit is a real requirement. Software-only data categories are not evidence that a data-brokerage service qualifies. Do not choose unrelated data-management or data-extraction software merely to complete submission.
