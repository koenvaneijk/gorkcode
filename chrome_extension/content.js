// Gorkcode Content Script

console.log('%cGorkcode content script injected', 'color: #8b5cf6; font-weight: bold');

window.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'gorkcode-execute') {
    const { code, id } = event.data;
    const logs = [];
    const orig = console.log;
    console.log = (...a) => {
      logs.push(a.join(' '));
      orig.apply(console, a);
    };

    let result = null;
    let error = null;
    try {
      result = new Function(code)();
    } catch (e) {
      error = e.message;
    }
    console.log = orig;

    window.postMessage({
      type: 'gorkcode-result',
      id,
      result,
      logs,
      error
    }, '*');
  }
});

// Also expose for manual use
window.gorkcode = {
  execute: (code) => {
    const id = 'manual-' + Date.now();
    window.postMessage({type: 'gorkcode-execute', code, id}, '*');
    return 'Executed. Check console for result.';
  }
};