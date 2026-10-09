import {test} from 'node:test';
import assert from 'node:assert/strict';
import {messageBlocks, tableCells} from '../src/message-format.js';

test('fenced code preserves CRLF, empty lines and unclosed streaming content', () => {
  assert.deepEqual(messageBlocks('before\n```js\r\nconst x = 1;\r\n\r\n```\r\nafter'), [
    {kind:'text',text:'before\n'}, {kind:'code',language:'js',text:'const x = 1;\r\n\r\n'}, {kind:'text',text:'after'}]);
  assert.deepEqual(messageBlocks('~~~python\nprint(1)\n\nmore'), [{kind:'code',language:'python',text:'print(1)\n\nmore'}]);
  assert.deepEqual(messageBlocks('````md\n```\n| a | b |\n| --- | --- |\n````'),
    [{kind:'code',language:'md',text:'```\n| a | b |\n| --- | --- |\n'}]);
});
test('tables require a valid divider and preserve code and escaped pipes', () => {
  assert.deepEqual(tableCells('| A\\|B | `x|y` |'), ['A|B','`x|y`']);
  assert.deepEqual(messageBlocks('| A | B |\n| :--- | ---: |\n| a\\|b | `x|y` |\ntrailing'), [
    {kind:'table',header:['A','B'],rows:[['a|b','`x|y`']]}, {kind:'text',text:'trailing'}]);
  for (const text of ['A | B\nno divider', '| A | B |\n| --- |\n', 'unclosed **markup', '<img src=x onerror=alert(1)>'])
    assert.deepEqual(messageBlocks(text), [{kind:'text',text}]);
});
test('table-like content in streamed code stays code until an actual closing fence', () => {
  const code = '```txt\n| A | B |\n| --- | --- |\n| 1 | 2 |';
  assert.equal(messageBlocks(code)[0].kind, 'code');
  assert.equal(messageBlocks(code)[0].text, code.slice(7));
  assert.equal(messageBlocks(code+'\n```\n| A | B |\n| --- | --- |')[1].kind, 'table');
});
test('large messages use a lossless plain-text fallback', () => {
  for (const text of ['```\n'+'x'.repeat(200001), '\n'.repeat(4001)])
    assert.deepEqual(messageBlocks(text), [{kind:'text',text}]);
});
