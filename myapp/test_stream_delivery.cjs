// Run with: node myapp/test_stream_delivery.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, 'templates/ai.html'), 'utf8').replace(/\r\n/g, '\n');
const start = source.indexOf('      function renderStreamText(){');
const end = source.indexOf('      function pump(){', start);
assert(start >= 0 && end > start);
let queued, writes = 0;
const bubble = {set innerHTML(value) { this.html = value; writes++; }};
const context = {
  bubble, assistantText: 'Hello', streamRenderTimer: null,
  streamHasRendered: false, streamLastHtml: null, streamRenderInterval: 64,
  formatMd: text => '<p>' + text + '</p>',
  setTimeout: (callback, delay) => { assert.equal(delay, 64); queued = callback; return 1; }
};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);
context.scheduleStreamRender();
assert.equal(writes, 1, 'First chunk must render immediately');
assert.equal(queued, undefined);
context.assistantText += ' world';
context.scheduleStreamRender();
const firstTimer = queued;
context.assistantText += '!';
context.scheduleStreamRender();
assert.equal(queued, firstTimer, 'Later chunks coalesce');
assert.equal(writes, 1);
queued();
assert.equal(bubble.html, '<p>Hello world!</p><span class="msg-cursor"></span>');
context.scheduleStreamRender(); queued();
assert.equal(writes, 2, 'Identical markup does not replace the DOM');
// Exercise the actual pump with byte-split Unicode and an incomplete trailing
// sequence, comparing with decoding the entire HTTP response at once.
const pumpStart = end;
const pumpEnd = source.indexOf('      return pump();\n    }).then', pumpStart);
assert(pumpEnd > pumpStart);
const bytes = Buffer.concat([Buffer.from('Hello नमस्ते 🌟'), Buffer.from([0xe2])]);
let offset = 0;
context.assistantText = '';
context.TextDecoder = TextDecoder;
context.decoder = new TextDecoder();
context.stopBubbleTyping = () => {};
context.reader = {read: async () => offset < bytes.length
  ? {done: false, value: bytes.subarray(offset, ++offset)} : {done: true}};
vm.runInContext(source.slice(pumpStart, pumpEnd), context);
context.pump().then(() => {
  assert.equal(context.assistantText, new TextDecoder().decode(bytes));
  const finalizer = source.slice(source.indexOf('    function finalizeBubble(){'), source.indexOf("    fetch('/AI/api/send/'"));
  assert(finalizer.includes('clearTimeout(streamRenderTimer)'));
  assert(finalizer.includes('formatMd(assistantText)'));
  console.log('PASS: immediate first paint, coalescing, unchanged markup, Unicode preservation, final-render cleanup.');
}).catch(error => { console.error(error); process.exitCode = 1; });
