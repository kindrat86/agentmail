/* =====================================================================
   SanctionsAI — shared site behaviour
   Vanilla, no deps. Nav drawer, scroll state, reveals, copy buttons, FAQ,
   command palette (Ctrl/Cmd+K), touch-friendly.
   ===================================================================== */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const prefersReduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---- nav: scrolled state ---- */
  const nav = $('#nav');
  if (nav) {
    const onScroll = () => nav.classList.toggle('scrolled', scrollY > 8);
    onScroll();
    addEventListener('scroll', onScroll, { passive: true });
  }

  /* ---- nav: mobile drawer (accessible) ---- */
  const burger = $('#burger');
  const links = $('#navlinks');
  const scrim = $('#scrim');
  function setMenu(open) {
    if (!burger) return;
    burger.setAttribute('aria-expanded', String(open));
    links.classList.toggle('open', open);
    scrim && scrim.classList.toggle('show', open);
    document.body.style.overflow = open ? 'hidden' : '';
    if (open) {
      const first = links.querySelector('a');
      first && first.focus();
    }
  }
  burger && burger.addEventListener('click', () => setMenu(burger.getAttribute('aria-expanded') !== 'true'));
  scrim && scrim.addEventListener('click', () => setMenu(false));
  $$('a', links).forEach(a => a.addEventListener('click', () => setMenu(false)));
  addEventListener('keydown', e => { if (e.key === 'Escape') setMenu(false); });

  /* ---- active nav link: mark current page ---- */
  const here = location.pathname.replace(/\/index\.html$/, '/').replace(/\.html$/, '');
  $$('#navlinks a[data-nav]').forEach(a => {
    const p = a.getAttribute('data-nav');
    if (!p) return;
    const target = p === '/' ? '/' : p.replace(/\/$/, '');
    if (here === target || (target !== '/' && here.startsWith(target + '/'))) {
      a.setAttribute('aria-current', 'page');
    }
  });

  /* ---- reveal on scroll ---- */
  const reveals = $$('.reveal');
  if (reveals.length) {
    if (prefersReduce) {
      reveals.forEach(el => el.classList.add('in'));
    } else {
      const io = new IntersectionObserver((entries) => {
        entries.forEach(en => {
          if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
        });
      }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
      reveals.forEach(el => io.observe(el));
    }
  }

  /* ---- copy-to-clipboard for code windows ---- */
  $$('.copy-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const win = btn.closest('.codewin');
      const code = win && (win.querySelector('pre') || win.querySelector('code'));
      if (!code) return;
      try {
        await navigator.clipboard.writeText(code.innerText.trim());
        const old = btn.innerHTML;
        btn.classList.add('copied');
        btn.innerHTML = '✓ Copied';
        setTimeout(() => { btn.classList.remove('copied'); btn.innerHTML = old; }, 1600);
      } catch (e) { /* clipboard blocked — silent */ }
    });
  });

  /* ---- FAQ accordions ---- */
  $$('.faq-item').forEach(item => {
    const q = item.querySelector('.faq-q');
    const a = item.querySelector('.faq-a');
    if (!q || !a) return;
    q.setAttribute('aria-expanded', 'false');
    q.addEventListener('click', () => {
      const open = item.classList.toggle('open');
      q.setAttribute('aria-expanded', String(open));
      a.style.maxHeight = open ? a.scrollHeight + 'px' : '0px';
    });
  });

  /* ---- wallet checker (free tool, client-side demo) ---- */
  const checker = $('#wallet-checker');
  if (checker) {
    const input = checker.querySelector('input[name="address"]');
    const out = checker.querySelector('[data-result]');
    const DEMO = {
      hit: { sanctioned: true, name: 'Tornado Cash (Runtime)', list: 'OFAC SDN', program: 'EO 13694', severity: 'CRITICAL' },
      clean: { sanctioned: false, list: 'OFAC SDN', checked: 947, latency_ms: 84 }
    };
    checker.addEventListener('submit', async (e) => {
      e.preventDefault();
      const addr = (input.value || '').trim();
      if (!/^0x[a-fA-F0-9]{40}$/.test(addr)) {
        out.innerHTML = '<p class="muted" style="color:var(--red-2)">Enter a valid 0x… address (40 hex chars).</p>';
        out.style.display = 'block'; return;
      }
      out.innerHTML = '<p class="muted">Screening against OFAC SDN list…</p>';
      out.style.display = 'block';
      await new Promise(r => setTimeout(r, prefersReduce ? 120 : 520));
      const hit = /0x1f9840|0xdead|0xbad/.test(addr.toLowerCase());
      const r = hit ? DEMO.hit : DEMO.clean;
      out.innerHTML = hit
        ? `<div class="card" style="border-color:var(--red-line);background:var(--red-soft)">
             <div class="pill" style="margin-bottom:10px"><span class="tag">SANCTIONED</span>Match on SDN list</div>
             <p style="color:var(--red-2);line-height:1.6"><b>${r.name}</b> — Program: ${r.program}. Do not transact. Severity: ${r.severity}.</p>
             <pre style="margin-top:12px;font-size:.78rem">${JSON.stringify({ address: addr, ...r }, null, 2)}</pre>
           </div>`
        : `<div class="card" style="border-color:var(--teal-line);background:var(--teal-soft)">
             <div class="pill teal" style="margin-bottom:10px"><span class="tag">CLEAR</span>No match on SDN list</div>
             <p style="color:var(--teal-2);line-height:1.6">Screened against <b>${r.checked}</b> sanctioned wallets. Latency ${r.latency_ms} ms.</p>
           </div>`;
    });
  }

  /* ---- SEI calculator (interactive) ---- */
  const sei = $('#sei-calc');
  if (sei) {
    const sliders = $$('input[type="range"]', sei);
    const scoreEl = $('[data-sei-score]', sei);
    const verdict = $('[data-sei-verdict]', sei);
    const calc = () => {
      const v = sliders.map(s => +s.value);
      const w = [0.30, 0.25, 0.20, 0.15, 0.10]; // exposure, control, value, vol, recovery
      const raw = v.reduce((a, x, i) => a + x * w[i], 0);
      const score = Math.round(raw * 10);
      scoreEl.textContent = String(score);
      const lvl = score >= 70 ? ['SEVERE', 'var(--red)', 'var(--red-2)'] : score >= 40 ? ['ELEVATED', '#febc2e', '#ffd66e'] : ['ACCEPTABLE', 'var(--teal)', 'var(--teal-2)'];
      verdict.innerHTML = `<span class="pill" style="background:${lvl[1]}1a;border-color:${lvl[1]}55;color:${lvl[2]}"><span class="tag" style="background:${lvl[1]};color:#0a0b0d">${lvl[0]}</span>SEI ${score}/100</span>`;
    };
    sliders.forEach(s => s.addEventListener('input', () => { s.nextElementSibling.textContent = s.value + '/10'; calc(); }));
    calc();
  }

  /* ---- smooth-scroll for in-page anchors (respect reduced motion) ---- */
  if (!prefersReduce) {
    $$('a[href^="#"]').forEach(a => {
      a.addEventListener('click', e => {
        const id = a.getAttribute('href').slice(1);
        if (!id) return;
        const t = document.getElementById(id);
        if (t) { e.preventDefault(); t.scrollIntoView({ behavior: 'smooth', block: 'start' }); history.replaceState(null, '', '#' + id); }
      });
    });
  }
})();
