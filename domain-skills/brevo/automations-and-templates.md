# Brevo (app.brevo.com) — automations & email templates

App is a React SPA (class names like `sib-*___hash`, `naos-btn___hash` — CSS modules, don't hardcode full hashes).

## URL patterns

- `/automation/list` → **404-style error page**. The real list is `/automation/automations` (sidebar "Automatisations > Scénarios").
- Workflow editor: `/automation/edit/<id>`; settings: `/automation/settings/<id>`.
- Templates list: `/templates/listing`; template setup page: `/templates/email/edit/<id>`.
- Raw HTML editor: `/editor/classic/html/<id>` — a single plain `<textarea>` (no CodeMirror/Monaco). Set its value with the native setter + `dispatchEvent('input')`, then click "Enregistrer & Quitter".

## Creating a template from custom HTML

1. `/templates/listing` → "Créer un template" → "Template d'email" → lands on `/templates/email/create`.
2. Setup page fields:
   - Name: pencil button `#campaign-name-edit` → input `#campaign-name-input`; confirm with the ✓ button next to it (Enter does NOT commit).
   - Sender email: custom selectmenu — open `.sib-selectmenu-control` (mousedown + click), options are `li[class*=sib-selectmenu-option]`.
   - Sender name: plain input `#sender-name`.
   - **Objet and Aperçu du texte are Froala contenteditables** (`.fr-element.default-styles-1` and `.default-styles-2`), not inputs: set `innerHTML='<p>…</p>'` + dispatch `input`.
3. "Ajouter du contenu" (`#template-asset-selection-trigger`) → modal → "Créer de zéro" dropdown → menu options are plain leaf DIVs ("Éditeur Drag & Drop" / "Éditeur simple" / "Code HTML personnalisé") — find the leaf div by text and click it.
4. Paste HTML in the textarea editor, save, then back on the setup page use the "Enregistrer" split button (`#template-actions`) → "Enregistrer et activer" (template must be **Actif** to be usable).

## Automations (Scénarios)

- "Créer une automatisation" opens a modal with prebuilt types: Message de bienvenue, Panier abandonné, Activité marketing, **Achat de produit** (post-purchase), Date d'anniversaire.
- "Achat de produit" prebuilt = Commande créée → Attendre 1 minute → Envoyer un email → Sortie, with a 3-step guided config (trigger filters / delay / email). The trigger event is fixed by the prebuilt.
- Delay inputs are `input[name=Months|Days|Hours|Minutes]` (React number inputs — native setter + input/change events).
- The guided email step auto-generates a template. To use your own: trash icon next to "Modifier"/"Aperçu" → confirm "Supprimer le message" → "Ajouter un message" → **"Créer un nouveau message"** (NOT "Sélectionner un message existant" — that list only shows other automations' messages, not your saved templates) → template gallery shows "Vos templates" → "Utiliser ce template".
- ⚠️ Using a template **copies** it into a new message (named `<automation>_step_#N`, new template id). Later edits to the source template do NOT propagate to the workflow message.
- Rename automation: chevron button right of the title (h3) → "Renommer" → input + ✓ button.
- Re-entry (repeat buyers re-trigger the flow) is **OFF by default**: Para-mètres tab (`/automation/settings/<id>`) → toggle "Autoriser une nouvelle entrée des contacts après la sortie" → "Enregistrer les conditions".

## Test emails

Template setup page → "Aperçu et test" (`#preview-template`) → tab "Envoyer un email test" → "Destinataires" multiselect (checkboxes from the saved test list) → "Envoyer le test".

## Traps

- **Escape closes the whole modal**, not just an open dropdown inside it — close dropdowns by clicking elsewhere inside the modal.
- Multi-select dropdown choices don't persist if the modal is closed before sending.
- Pages are 1800px wide; screenshots come back scaled (~2.5×) — recompute click coordinates or click via `js()` + `getBoundingClientRect`.
- Color pickers all stay mounted in the DOM — target the one inside the `.rc-dropdown` that is NOT `rc-dropdown-hidden`.
- React inputs need the native value setter + `dispatchEvent('input')`; `type_text` into them is unreliable.
- react-beautiful-dnd drag & drop (form editor): keyboard sensor works (focus handle + Space), arrow keys are flaky.
- Success toasts ("Template enregistré et activé avec succès", "Conditions enregistrées", "Email de test envoyé") appear bottom-center — screenshot to confirm an action landed.
