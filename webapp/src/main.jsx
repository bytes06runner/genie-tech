import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

window.__log?.('main.jsx executing — React loaded')

// Hide boot screen once React takes over
const bootScreen = document.getElementById('boot-screen')
if (bootScreen) bootScreen.style.display = 'none'

window.__log?.('Mounting React root')

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

window.__log?.('React root mounted')
