const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('safari_harness/bridge.js', 'utf8');
const ref = {window: 7, index: 0, url: 'https://example.com', title: 'Example'};
function collection(items) {
    const f = () => items;
    items.forEach((item, i) => f[i] = item);
    return f;
}
function tab(url = ref.url, title = ref.title) {
    let value = url;
    const t = {name: () => title};
    Object.defineProperty(t, 'url', {get: () => () => value, set: v => {value = v;}});
    return t;
}
function fixture(tabs = [tab()]) {
    const calls = [];
    let windows = [{id: () => 7, tabs: collection(tabs)}];
    const safari = {
        running: () => true,
        windows: () => windows,
        doJavaScript(code, options) { calls.push([code, options]); return 'true'; },
        Document: x => x,
        documents: {push(doc) { windows = [{id: () => 8, tabs: collection([tab(doc.url, '')])}, ...windows]; }}
    };
    const context = vm.createContext({Application: () => safari});
    vm.runInContext(source, context);
    return {safari, calls, run: req => JSON.parse(context.dispatch(req))};
}
function executionRaceFixture(expected, destination, spoofAliases = false) {
    const selected = tab(expected.url, expected.title);
    const f = fixture([selected]);
    const observed = {transportCalls: 0, bodyExecutions: 0, writes: 0, value: ''};
    const field = {};
    Object.defineProperty(field, 'value', {
        get: () => observed.value,
        set(value) { observed.writes++; observed.value = value; }
    });
    const page = {
        observed,
        document: {querySelector: () => field}
    };
    // Model browser-owned Location accessors; this is executable page JS in a
    // Node VM, not evidence of Safari's live Apple Event/reference semantics.
    const location = {};
    Object.defineProperty(location, 'href', {get: () => selected.url()});
    Object.defineProperty(page, 'location', {get: () => location});
    if (spoofAliases) {
        page.globalThis = {location: {href: expected.url}};
        page.self = {location: {href: expected.url}};
    }
    const pageContext = vm.createContext(page);
    f.safari.doJavaScript = (code, options) => {
        observed.transportCalls++;
        assert.equal(options.in, selected);
        // All bridge URL/title checks have finished when this Apple Event is
        // delivered. Change the recipient's URL before evaluating the script.
        selected.url = destination;
        return vm.runInContext(code, pageContext);
    };
    const code = "JSON.stringify((function(){observed.bodyExecutions++;document.querySelector('#secret').value='SYNTHETIC_ORIGIN_VALUE';return true;})())";
    return {observed, run: () => f.run({action: 'js', target: expected, code})};
}
function assertBlockedBeforeMutation(f) {
    let failure;
    try { f.run(); } catch (error) { failure = error; }
    assert.deepEqual(f.observed, {transportCalls: 1, bodyExecutions: 0, writes: 0, value: ''});
    assert.match(String(failure), /Target mismatch/);
}
test('listing returns references without executing page scripts', () => {
    const f = fixture();
    assert.deepEqual(f.run({action: 'list'}), [ref]);
    assert.equal(f.calls.length, 0);
});
test('stale URL blocks page script execution', () => {
    const f = fixture([tab('https://other.example')]);
    assert.throws(() => f.run({action: 'js', target: ref, code: 'deleteStuff()'}), /changed or moved/);
    assert.equal(f.calls.length, 0);
});
test('closed window blocks navigation', () => {
    const f = fixture();
    assert.throws(() => f.run({action: 'navigate', target: {...ref, window: 42}, url: 'https://new.example'}), /Stale tab/);
});
test('identical tabs are rejected', () => {
    const f = fixture([tab(), tab()]);
    assert.throws(() => f.run({action: 'js', target: ref, code: 'deleteStuff()'}), /Ambiguous/);
    assert.equal(f.calls.length, 0);
});
test('new window is selected by identity', () => {
    const f = fixture();
    const created = f.run({action: 'new', url: 'https://new.example'});
    assert.equal(created.window, 8);
    assert.equal(created.url, 'https://new.example');
});
test('creation cannot silently attach to existing frontmost tab', () => {
    const f = fixture();
    f.safari.documents.push = () => {};
    assert.throws(() => f.run({action: 'new', url: 'https://new.example'}), /cannot identify/);
});
test('navigation verifies old reference and returns new URL', () => {
    const f = fixture();
    const result = f.run({action: 'navigate', target: ref, url: 'https://new.example'});
    assert.equal(result.url, 'https://new.example');
});
test('script targets the explicitly selected tab object', () => {
    const t = tab();
    const f = fixture([t]);
    assert.deepEqual(f.run({action: 'js', target: ref, code: '1+1'}), {result: 'true'});
    assert.equal(f.calls[0][1].in, t);
});
test('execution-time cross-origin redirect blocks the page operation', () => {
    const expected = {...ref, url: 'https://intended.invalid/form', title: 'Intended'};
    const f = executionRaceFixture(expected, 'https://recipient.invalid/form');
    assertBlockedBeforeMutation(f);
});
test('execution-time same-origin URL change blocks the page operation', () => {
    const expected = {...ref, url: 'https://intended.invalid/form', title: 'Intended'};
    const f = executionRaceFixture(expected, 'https://intended.invalid/replacement');
    assertBlockedBeforeMutation(f);
});
test('different origin and title variant blocks despite spoofed global aliases', () => {
    const expected = {...ref, url: 'http://source.invalid:8080/alternate?x=1', title: 'Another fixture'};
    const f = executionRaceFixture(expected, 'http://recipient.invalid:8081/alternate?x=1', true);
    assertBlockedBeforeMutation(f);
});
test('matching execution-time URL evaluates the page operation exactly once', () => {
    const expected = {...ref, url: 'https://intended.invalid/form', title: 'Intended'};
    const f = executionRaceFixture(expected, expected.url);
    assert.deepEqual(f.run(), {result: 'true'});
    assert.deepEqual(f.observed, {
        transportCalls: 1, bodyExecutions: 1, writes: 1, value: 'SYNTHETIC_ORIGIN_VALUE'
    });
});
