// popup.js - OkoCRM Mail Filter
const DEFAULT_CODES = [
  '1Vf6ZV1',
  '9mBA4U0',
  'JdFpDtJ',
  'Jx8gasS',
  'mp5WvVX',
  'icKKRxR',
  'nYVUhOn',
  'eonvzb4',
  'cc8OzlS',
  'uELDGph',
  'ZLH0hVB',
  'kx9rx6E',
  'O6VBbdu',
  '2FAGSWY',
  'wVQHpag'
];

document.addEventListener('DOMContentLoaded', async () => {
  const toggle = document.getElementById('toggle-filter');
  const codesInput = document.getElementById('codes-input');
  const codeCount = document.getElementById('code-count');
  const btnSave = document.getElementById('btn-save');
  const statusMsg = document.getElementById('status-msg');

  // Load existing configuration
  const data = await chrome.storage.local.get(['warmupCodes', 'hideWarmupEnabled']);
  const codes = (data.warmupCodes && data.warmupCodes.length > 0)
    ? Array.from(new Set([...DEFAULT_CODES, ...data.warmupCodes]))
    : DEFAULT_CODES;
  const isEnabled = data.hideWarmupEnabled !== undefined ? data.hideWarmupEnabled : true;

  toggle.checked = isEnabled;
  codesInput.value = codes.join('\n');
  codeCount.innerText = `${codes.length} кодов`;

  // Toggle change
  toggle.addEventListener('change', async (e) => {
    await chrome.storage.local.set({ hideWarmupEnabled: e.target.checked });
  });

  // Save button
  btnSave.addEventListener('click', async () => {
    const rawCodes = codesInput.value;
    const linesCodes = rawCodes.split('\n').map(l => l.trim()).filter(Boolean);

    await chrome.storage.local.set({
      warmupCodes: linesCodes,
      hideWarmupEnabled: toggle.checked
    });

    codeCount.innerText = `${linesCodes.length} кодов`;
    statusMsg.style.display = 'block';
    setTimeout(() => {
      statusMsg.style.display = 'none';
    }, 2000);
  });
});
