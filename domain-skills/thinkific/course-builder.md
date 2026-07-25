# Thinkific — building course curriculum (admin)

Creating chapters and lessons at scale. The public REST API (`api.thinkific.com/api/public/v1`) is **GET-only** for courses/chapters/contents — there is no POST. The admin course-builder instead drives a private GraphQL API, and that one writes everything. Don't conclude "must be done by hand in the UI"; it doesn't.

## Endpoint

```
POST https://<subdomain>.thinkific.com/api/graphql      # or the custom domain, e.g. courses.example.org
headers:
  content-type: application/json
  x-csrf-token: <document.querySelector('meta[name=csrf-token]').content>
  x-client-id: COURSE-BUILDER
credentials: include        # _thinkific_session cookie
```

Call it from inside a logged-in admin tab with `fetch` — no cookie extraction needed, and the CSRF token is already in the page. `_thinkific_session` is httpOnly, so `document.cookie` won't show it anyway.

## Node IDs

Global IDs are `base64("<Type>-<numericId>")`:

```
base64("Course-1234567")  -> Q291cnNlLTEyMzQ1Njc=
base64("Chapter-2345678") -> Q2hhcHRlci0yMzQ1Njc4
base64("Content-3456789") -> Q29udGVudC0zNDU2Nzg5
```

Reading a lesson back may return a type-specific id (`TextLesson-…`, `QuizLesson-…`) — the numeric part is the same content id, and both work as `node(id:)`.

## Mutations

`lessonInput` is shared by every lesson type:

```js
{name, draft:false,
 lessonTypeIcon:"text|quiz|pdf|video|assignment",
 lessonTypeLabel:"Text|Quiz|PDF|Video|Assignment",
 options:{discussionsEnabled:false}}
```

| Mutation | Type-specific input |
|---|---|
| `createChapter` | `(courseId, name, position, setNewLessonsToDraft)` |
| `createTextLesson` / `updateTextLesson` | `lessonWithTextInput{htmlDescription}` |
| `createQuizLesson` | `lessonWithQuizInput{quizType:"simple", passingScore:<int %>, showExplanation, numberOfSelectedQuizQuestions}` + `questions:[…]` + `promptId:""` |
| `createPdfLesson` | `lessonWithPdfInput{url, downloadable, assetId:""}` — `url` is the S3 link from the upload widget |
| `createVideoLesson` | `lessonWithVideoInput{videoId}` — from the Video Library after upload |
| `createAssignmentLesson` | `lessonWithAssignmentInput{fileSizeLimit, htmlDescription}` |
| `deleteLesson` | `(id)` |
| `reorderLessonInChapter` | `(chapterId, lessonId, newPosition)` |

### Quizzes go in one call

`createQuizLesson` accepts the whole question set inline — no per-question mutations:

```js
questions: [{
  prompt: "<p>Which division contains the skull and spine?</p>",
  displayType: "radio",          // one correct answer
  position: 0,                   // 0-indexed
  textExplanation: "",
  choices: [{position:0, text:"Axial skeleton", credited:true},
            {position:1, text:"Appendicular skeleton", credited:false}]
}]
```

`passingScore` is an integer percent (80 = 80%). A quiz **cannot be saved with zero questions** unless it's a draft — the UI enforces this and so does the API.

### Reordering

`reorderLessonInChapter` is **0-indexed** with move-to-index semantics (the lesson is removed from its slot and inserted at `newPosition`, everything else shifts). Selection-sort into the target order converges:

```
for i, name in enumerate(target_order):
    if working[i] != name:
        reorder(chapter, id_of(name), i)
        working.remove(name); working.insert(i, name)
```

Lessons are appended in creation order, so if you create by type (all text, then all quizzes, then all PDFs) you must reorder afterwards. Creating strictly in curriculum order avoids the pass entirely.

## Discovery without introspection

`__schema` is disabled, but the error messages are unusually good:

- Wrong mutation name → ``Field 'reorderLessons' doesn't exist on type 'Mutation' (Did you mean `reorderLessonInChapter`?)``
- `input: {}` → lists **every required argument with its exact type**.
- A bogus field on an input object or a concrete type → tells you it isn't accepted, often with a suggestion.

That's the fastest way to map this API. Otherwise, watch the builder: patch `window.fetch`/`XMLHttpRequest` in the admin page, perform the action once in the UI, and read the captured `operationName` + `variables` + `query`.

## File uploads (PDF / video)

GraphQL needs a URL/id that only the upload pipeline produces. It goes through a **Filestack** widget, and — importantly — **no native OS file dialog is involved**, so this is fully automatable:

1. Open `/manage/courses/<id>/chapters/<chapterId>/contents/new_pdf_lesson` (or `new_video_lesson`, `new_text_lesson`, `new_quiz_lesson`, `new_assignment_lesson`).
2. Click **Browse files**. Only *after* this does a real `input#fsp-fileUpload` appear — in the **top document**, not an iframe. Its `accept` matches the lesson type.
3. `upload_file('#fsp-fileUpload', path)` (CDP `DOM.setFileInputFiles`).
4. Click **Upload** in the widget.
5. Poll for attachment: PDFs show the text `Uploaded PDF file`; videos show the filename in the "Videos from your library" select (with `(processing)` — you can save immediately, transcoding continues server-side).
6. Fill the title, click **Save lesson**, wait for the URL to become `/manage/courses/<id>/contents/<numericId>`.

Locate the buttons by visible text and click the rect centre rather than hardcoding pixels — the title wraps to two lines on long names and shifts everything below it.

## Images inside lesson HTML — do not use data URIs

Thinkific rewrites every `<img>` on save and injects a responsive `srcset` with `?width=1920`/`&dpr=2`/`&dpr=3` variants. Appended to a `data:` URI that produces **invalid** candidates (`?` isn't in the base64 alphabet), the browser prefers srcset over `src`, and the image renders as a broken icon in the student player. The stored `src` still looks perfect on inspection — it fails silently.

Detect with `img.complete === true && img.naturalWidth === 0`. A stored body ~3× the source length is the tell that srcset was injected.

Fix — upload the image and reference it by URL:

```js
// 1. get the tokenized endpoint
query { site { imageUploadUrl } }   // -> /file_assets/upload_image?authenticity_token=…

// 2. POST a Blob as FormData from the page
var fd = new FormData(); fd.append('file', blob, 'banner.png');
fetch(imageUploadUrl, {method:'POST', body:fd, credentials:'include'})
// -> {"link":"https://files.cdn.thinkific.com/file_uploads/<id>/images/…/banner.png"}
```

Then rewrite the HTML to use the links. Dedupe by hashing the base64 first — reused banners mean far fewer uploads than files (one course had 65 files but only 5 distinct images).

Lesson bodies are Froala HTML; a `<div class="fr-view">…</div>` fragment pastes in cleanly.

## Player URLs

`/courses/take/<course-slug>/<texts|pdfs|quizzes|videos>/<contentId>-<lesson-slug>`

The `-<slug>` suffix is **required** — id alone 404s to "The content cannot be displayed." Get real URLs by clicking a lesson in the player and reading `location`. Preview mode (`You are previewing all course lessons`) works on a Draft course.

## Traps

- Large `Runtime.evaluate` payloads break the browser-harness daemon socket (`BrokenPipeError`). Chunk injected strings to ~8–16 KB: `js("window.__b += " + json.dumps(chunk))`, then `JSON.parse`.
- `updateAssignmentLesson` needs its variable declared `LessonWithAssignmentInput!` (non-null) or it fails with `Nullability mismatch`. The create variant is fine either way.
- Assignment bodies are written as `htmlDescription` but **read back as `assignmentContent`** — querying `htmlDescription` on an `AssignmentLesson` returns empty and looks like data loss.
- `updateTextLesson` with `questions: []` does **not** wipe existing quiz questions (the UI sends exactly that on a plain save).
- The admin page is a mix of Rails navigations and React; "Add chapter"/"Add lesson" are full page loads to `/chapters/new` and `/contents/new_*_lesson`, not XHR.
