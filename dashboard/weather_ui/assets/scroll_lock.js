// Keeps the scroll position while Streamlit re-runs the script.
// While a rerun is in progress Streamlit briefly shrinks the page, which throws the view back
// to the top. ONE watcher is installed (guarded, so reruns don't stack it); it remembers where
// the user is scrolled and holds that position until the rerun has finished.
(function () {
  const P = window.parent, D = P.document;
  if (P.__scrollLock) return;
  P.__scrollLock = true;
  let lastY = 0, lastInput = 0, enforceUntil = 0, wasRunning = false;
  const scroller = () => {
    const c = ['[data-testid="stMain"]', 'section.main', '[data-testid="stAppViewContainer"]']
      .map(q => D.querySelector(q)).filter(Boolean);
    return c.find(e => e.scrollHeight > e.clientHeight) || c[0];
  };
  ['wheel', 'touchmove', 'keydown', 'mousedown'].forEach(ev =>
    D.addEventListener(ev, () => { lastInput = Date.now(); }, {passive: true, capture: true}));
  const running = () => {
    const app = D.querySelector('.stApp');
    const st = app && app.getAttribute('data-test-script-state');
    return (st && st !== 'notRunning') || !!D.querySelector('[data-testid="stStatusWidget"]');
  };
  setInterval(() => {
    const el = scroller();
    if (!el) return;
    const now = Date.now(), r = running(), userActive = now - lastInput < 400;
    if (wasRunning && !r) enforceUntil = now + 800;
    wasRunning = r;
    if (r || now < enforceUntil) {
      if (userActive) lastY = el.scrollTop;
      else if (lastY > 0 && Math.abs(el.scrollTop - lastY) > 2) el.scrollTop = lastY;
    } else if (!userActive && el.scrollTop < 5 && lastY > 200) {
      enforceUntil = now + 1500;           // sudden unexplained jump to the top -> undo it
      el.scrollTop = lastY;
    } else {
      lastY = el.scrollTop;                // idle: just follow the user's own scrolling
    }
  }, 30);
})();
