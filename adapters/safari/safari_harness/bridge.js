function dispatch(request) {
    const safari = Application('Safari');
    if (!safari.running()) throw Error('Safari is not running. Open Safari and retry.');
    const windows = safari.windows();
    function describe(w, t, i) {
        return {window: w.id(), index: i, url: t.url() || '', title: t.name() || ''};
    }
    if (request.action === 'list') {
        const result = [];
        windows.forEach(w => w.tabs().forEach((t, i) => result.push(describe(w, t, i))));
        return JSON.stringify(result);
    }
    if (request.action === 'new') {
        // A dedicated normal window avoids ambiguous insertion into a user's tab group.
        const before = windows.map(w => w.id());
        const doc = safari.Document({url: request.url});
        safari.documents.push(doc);
        const added = safari.windows().filter(w => !before.includes(w.id()));
        if (added.length !== 1 || added[0].tabs().length !== 1)
            throw Error('Created a document but cannot identify its new window. Do not repeat creation; inspect list_tabs().');
        return JSON.stringify(describe(added[0], added[0].tabs[0], 0));
    }
    const ref = request.target;
    const w = windows.find(w => w.id() === ref.window);
    if (!w || ref.index < 0 || ref.index >= w.tabs().length)
        throw Error('Stale tab reference: list_tabs() and switch_tab() again.');
    const t = w.tabs[ref.index];
    if ((t.url() || '') !== ref.url || (t.name() || '') !== ref.title)
        throw Error('Tab changed or moved: list_tabs() and switch_tab() again.');
    const matches = w.tabs().filter(other => (other.url() || '') === ref.url && (other.name() || '') === ref.title);
    if (matches.length !== 1)
        throw Error('Ambiguous identical tabs: Safari does not expose stable tab IDs. Select a uniquely identifiable tab.');
    if (request.action === 'info') return JSON.stringify(describe(w, t, ref.index));
    if (request.action === 'navigate') {
        t.url = request.url;
        return JSON.stringify(describe(w, t, ref.index));
    }
    if (request.action === 'js') {
        // A tab can navigate after the Apple Event metadata checks above. Read
        // browser-owned Location inside the same synchronous page operation,
        // before evaluating any caller code. Top-level `this` avoids replaceable
        // globalThis/self aliases. This is not a stable document or tab identity.
        const guardedCode = '(function(__safariWindow){' +
            'if(__safariWindow.location.href !== ' + JSON.stringify(ref.url) + ')' +
            'throw "Target mismatch: URL changed before execution. List tabs and select again.";' +
            'return (' + request.code + ');})(this)';
        const result = safari.doJavaScript(guardedCode, {in: t});
        return JSON.stringify({result: result === undefined ? null : result});
    }
    throw Error('Unsupported bridge action: ' + request.action);
}
