// Gorkcode Browser Bridge - Background Service Worker

let lastState = {
  url: '',
  title: '',
  timestamp: 0,
  logs: []
};

let pendingCommand = null;

// Poll bridge for commands
async function pollBridge() {
  try {
    const res = await fetch('http://localhost:9876/command', {
      method: 'GET',
      headers: { 'Accept': 'application/json' }
    });
    if (res.ok) {
      const data = await res.json();
      if (data.command === 'execute' && data.code) {
        pendingCommand = data;
        chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
          if (tabs[0]) {
            chrome.scripting.executeScript({
              target: { tabId: tabs[0].id },
              func: executeInPage,
              args: [data.code]
            });
          }
        });
      }
    }
  } catch (e) {
    // Bridge not running, silent
  }
}

function executeInPage(code) {
  const logs = [];
  const originalConsole = console.log;
  console.log = (...args) => {
    logs.push(args.join(' '));
    originalConsole.apply(console, args);
  };

  let result = null;
  let error = null;

  try {
    // eslint-disable-next-line no-eval
    result = eval(`(function() { ${code} })()`);
  } catch (e) {
    error = e.toString();
  }

  console.log = originalConsole;
  return { result, logs, error };
}

// Listen for results from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'gorkcode_result') {
    lastState.logs = message.logs || [];
    lastState.url = sender.tab ? sender.tab.url : '';
    lastState.title = sender.tab ? sender.tab.title : '';
    lastState.timestamp = Date.now();
    
    // Send result back to bridge
    fetch('http://localhost:9876/result', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(message)
    }).catch(() => {});
  }
  return true;
});

// Update state periodically
setInterval(() => {
  chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
    if (tabs[0]) {
      lastState.url = tabs[0].url || '';
      lastState.title = tabs[0].title || '';
      lastState.timestamp = Date.now();
    }
  });
}, 2000);

setInterval(pollBridge, 1500);

console.log('Gorkcode Bridge background loaded');