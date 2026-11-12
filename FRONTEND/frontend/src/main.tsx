// frontend/src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

async function prepareApp() {
  const apiBase = import.meta.env.VITE_API_BASE;
  const isMockMode = !apiBase || apiBase.trim() === '' || apiBase === 'mock';

  if (isMockMode) {
    const { worker } = await import('./mocks/browser');
    await worker.start({
      onUnhandledRequest: 'bypass',
      serviceWorker: {
        url: '/mockServiceWorker.js',
      },
    });
    console.info(
      '%c[GovScheme AI] Running with Mock Service Worker (contracts/fixtures active). To switch to live API, set VITE_API_BASE in .env',
      'color: #1e4f76; font-weight: bold;'
    );
  } else {
    console.info(
      `%c[GovScheme AI] Connected to real backend API: ${apiBase}`,
      'color: #137333; font-weight: bold;'
    );
  }
}

prepareApp().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
});
