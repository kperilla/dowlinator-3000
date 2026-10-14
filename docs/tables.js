const body = document.body;
const $ = id => document.getElementById(id);

// hide mode: click a blanked cell to reveal it
$('hide').addEventListener('change', e => {
  body.classList.toggle('hide', e.target.checked);
  document.querySelectorAll('td.f.shown').forEach(c => c.classList.remove('shown'));
});
document.addEventListener('click', e => {
  const c = e.target.closest('td.f');
  if (c && body.classList.contains('hide') && !body.classList.contains('quiz')) c.classList.toggle('shown');
});

// quiz mode: a text box in every form cell
document.querySelectorAll('td.f').forEach(c => {
  const i = document.createElement('input');
  i.type = 'text'; i.autocomplete = 'off'; i.spellcheck = false;
  i.setAttribute('autocapitalize', 'off');
  c.appendChild(i);
});
$('quiz').addEventListener('change', e => body.classList.toggle('quiz', e.target.checked));
// match the page to the checkboxes (browsers may restore their state on reload)
body.classList.toggle('hide', $('hide').checked);
body.classList.toggle('quiz', $('quiz').checked);

// typing a vowel then "-" turns it into the macron vowel: a- → ā
const MACRON = {a:'ā', e:'ē', i:'ī', o:'ō', u:'ū', y:'ȳ', A:'Ā', E:'Ē', I:'Ī', O:'Ō', U:'Ū', Y:'Ȳ'};
document.addEventListener('input', e => {
  const i = e.target;
  if (e.data !== '-' || !i.matches('td.f input')) return;
  const p = i.selectionStart;
  const v = MACRON[i.value[p - 2]];
  if (p >= 2 && i.value[p - 1] === '-' && v) i.setRangeText(v, p - 2, p, 'end');
});

// floating macron keyboard: types into the focused (or last focused) quiz box
let lastInput = null;
document.addEventListener('focusin', e => { if (e.target.matches('td.f input')) lastInput = e.target; });
$('macrons').addEventListener('mousedown', e => e.preventDefault());  // keep focus in the text box
$('macrons').addEventListener('click', e => {
  const b = e.target.closest('button');
  if (!b || !lastInput) return;
  const ch = e.shiftKey ? b.textContent.toUpperCase() : b.textContent;
  lastInput.focus();
  lastInput.setRangeText(ch, lastInput.selectionStart, lastInput.selectionEnd, 'end');
  lastInput.dispatchEvent(new Event('input', {bubbles: true}));
});

const norm = s => {
  s = s.trim().replace(/\s+/g, ' ').toLowerCase();
  if ($('nomacrons').checked) s = s.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  return s;
};

function grade(block) {
  const cells = block.querySelectorAll('td.f');
  let right = 0;
  cells.forEach(c => {
    const answers = JSON.parse(c.dataset.a);
    const ok = answers.some(a => norm(a) === norm(c.querySelector('input').value));
    c.classList.toggle('ok', ok);
    c.classList.toggle('bad', !ok);
    right += ok;
  });
  const pct = cells.length ? Math.round(100 * right / cells.length) : 0;
  block.querySelector('.score').textContent = `${right} / ${cells.length} (${pct}%)`;
}

document.querySelectorAll('.block').forEach(b =>
  b.querySelector('.grade').addEventListener('click', () => grade(b)));
$('gradeall').addEventListener('click', () => document.querySelectorAll('.block').forEach(grade));
$('reset').addEventListener('click', () => {
  document.querySelectorAll('td.f').forEach(c => {
    c.querySelector('input').value = ''; c.classList.remove('ok', 'bad');
  });
  document.querySelectorAll('.score').forEach(s => s.textContent = '');
});
