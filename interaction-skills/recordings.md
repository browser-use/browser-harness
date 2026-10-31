# Recordings and Videos

Fresh installs do not record. Users can enable local background traces:

```bash
browser-harness recordings enable
browser-harness recordings disable
browser-harness recordings
```

`BH_RECORD=1` or `BH_RECORD=0` overrides the preference for one process. Any
natural nudge to “record,” “show,” “demo,” or “make a video” opts in that task;
significant work alone does not.

Before browser work, call `start_recording(name, title=...)`, retain its exact
returned directory, and call `stop_recording()` after verifying the result.
Never replace that path with `recordings --latest`. For a request made after
the task, use:

```bash
browser-harness recordings --latest
```

Use it only if timestamps and pages match; otherwise say the work was not
captured. Never reenact a completed task. For a video, follow
[make-video.md](https://github.com/browser-use/browser-harness/blob/main/interaction-skills/make-video.md).
If sub-agents are available, they may handle post-production from the exact
recording path while the main agent returns the task result.
