(() => {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const d = document, h = d.documentElement;
  h.classList.add('fx');

  // scroll reveal (also catches content your other JS renders later)
  const SEL = '.section,.metric,.scenario-card,.result-card,.finding,.ownership-row,.flow-step,.claims-card,.audit-row,.identity-grid .item,.banner';
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }), { threshold: .08, rootMargin: '0px 0px -4% 0px' });

  function scan(root) {
    let i = 0;
    root.querySelectorAll(SEL).forEach(el => {
      if (el.classList.contains('rv')) return;
      el.classList.add('rv');
      el.style.setProperty('--d', Math.min(i++, 8) * 60 + 'ms');
      io.observe(el);
    });
  }

  // count-up for dashboard numbers
  function count() {
    d.querySelectorAll('.metric .value').forEach(el => {
      const t = el.textContent.trim();
      if (!/^\d+$/.test(t) || el._n === t) return;
      el._n = t;
      const n = +t, k = el._k = (el._k || 0) + 1, s = performance.now();
      (function f(now) {
        if (el._k !== k || !el.firstChild) return;
        const p = Math.min(1, (now - s) / 1100);
        el.firstChild.nodeValue = Math.round(n * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(f);
      })(s);
    });
  }

  // hero headline: split into words for staggered entrance
  d.querySelectorAll('.hero h1').forEach(hd => {
    let i = 0;
    (function walk(n) {
      [...n.childNodes].forEach(c => {
        if (c.nodeType === 3) {
          const f = d.createDocumentFragment();
          c.textContent.split(/(\s+)/).forEach(t => {
            if (!t.trim()) { f.append(t); return; }
            const s = d.createElement('span');
            s.className = 'w'; s.style.setProperty('--i', i++); s.textContent = t;
            f.append(s);
          });
          c.replaceWith(f);
        } else walk(c);
      });
    })(hd);
  });

  scan(d.body); count();
  let q = 0;
  new MutationObserver(() => {
    if (q) return;
    q = requestAnimationFrame(() => { q = 0; scan(d.body); count(); });
  }).observe(d.body, { childList: true, subtree: true });

  // cursor spotlight on cards + hero tilt
  const art = d.querySelector('.hero-art');
  d.addEventListener('pointermove', e => {
    const c = e.target.closest && e.target.closest('.section,.scenario-card,.result-card,.metric');
    if (c) {
      const r = c.getBoundingClientRect();
      c.style.setProperty('--mx', e.clientX - r.left + 'px');
      c.style.setProperty('--my', e.clientY - r.top + 'px');
    }
    if (art) {
      art.style.setProperty('--rx', -(e.clientY / innerHeight - .5) * 8 + 'deg');
      art.style.setProperty('--ry', (e.clientX / innerWidth - .5) * 10 + 'deg');
    }
  }, { passive: true });
})();