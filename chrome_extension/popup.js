document.getElementById('capture').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  const output = document.getElementById('output');
  
  output.textContent = `Captured:\nTitle: ${tab.title}\nURL: ${tab.url}\n\nState sent to bridge.`;
  
  try {
    await fetch('http://localhost:9876/update', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        url: tab.url,
        title: tab.title,
        timestamp: Date.now()
      })
    });
  } catch (e) {
    output.textContent += '\n\nBridge not running.';
  }
});

document.getElementById('run').addEventListener('click', async () => {
  const code = document.getElementById('js').value.trim();
  const output = document.getElementById('output');
  if (!code) return;
  
  output.textContent = 'Executing...';
  
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: (codeStr) => {
        const logs = [];
        const origLog = console.log;
        console.log = (...args) => {
          logs.push(args.join(' '));
          origLog(...args);
        };
        let res = null;
        let err = null;
        try {
          res = new Function(codeStr)();
        } catch (e) {
          err = e.toString();
        }
        console.log = origLog;
        return {result: res, logs, error: err};
      },
      args: [code]
    });
    
    const res = results[0].result;
    output.textContent = `Result: ${JSON.stringify(res.result, null, 2)}\n\nLogs:\n${res.logs.join('\n')}`;
    if (res.error) output.textContent += `\nError: ${res.error}`;
  } catch (e) {
    output.textContent = 'Error: ' + e.message;
  }
});