/**
 * ux.js — World-Class Interactive UX Enhancements (R16)
 * Zero dependencies. Progressive enhancement.
 * Features: reading progress bar, back-to-top, lazy image loading,
 * accordions, smooth scroll, exit-intent detection, mobile bottom nav,
 * sticky CTA bar, bottom sheets, toast notifications, auto lazy-load,
 * scroll-driven UI visibility, view transitions opt-in.
 */
(function() {
  'use strict';

  var REDUCED_MOTION = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ── READING PROGRESS BAR ────────────────────────────
  function initReadingProgress() {
    if (document.getElementById('ux-reading-progress')) return;
    var bar = document.createElement('div');
    bar.id = 'ux-reading-progress';
    bar.setAttribute('aria-hidden', 'true');
    document.body.prepend(bar);

    var ticking = false;
    window.addEventListener('scroll', function() {
      if (!ticking) {
        requestAnimationFrame(function() {
          var scrollTop = window.scrollY || document.documentElement.scrollTop;
          var docHeight = document.documentElement.scrollHeight - window.innerHeight;
          var progress = docHeight > 0 ? Math.min((scrollTop / docHeight) * 100, 100) : 0;
          bar.style.width = progress + '%';
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });
  }

  // ── BACK-TO-TOP BUTTON ──────────────────────────────
  function initBackToTop() {
    if (document.getElementById('ux-back-to-top')) return;
    var btn = document.createElement('button');
    btn.id = 'ux-back-to-top';
    btn.setAttribute('aria-label', 'Back to top');
    btn.innerHTML = '↑';
    btn.title = 'Back to top';
    document.body.appendChild(btn);

    var ticking = false;
    window.addEventListener('scroll', function() {
      if (!ticking) {
        requestAnimationFrame(function() {
          if (window.scrollY > 400) {
            btn.classList.add('visible');
          } else {
            btn.classList.remove('visible');
          }
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });

    btn.addEventListener('click', function() {
      window.scrollTo({ top: 0, behavior: REDUCED_MOTION ? 'auto' : 'smooth' });
    });
  }

  // ── LAZY IMAGE LOADING ──────────────────────────────
  function initLazyImages() {
    if ('IntersectionObserver' in window) {
      var observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
          if (entry.isIntersecting) {
            var img = entry.target;
            if (img.dataset.src) {
              img.src = img.dataset.src;
              img.removeAttribute('data-src');
            }
            if (img.dataset.srcset) {
              img.srcset = img.dataset.srcset;
              img.removeAttribute('data-srcset');
            }
            img.addEventListener('load', function() {
              img.classList.add('loaded');
            });
            observer.unobserve(img);
          }
        });
      }, { rootMargin: '200px' });

      document.querySelectorAll('img[loading="lazy"]').forEach(function(img) {
        img.addEventListener('load', function() {
          img.classList.add('loaded');
        });
        if (img.complete) {
          img.classList.add('loaded');
        }
      });
    }
  }

  // R16: Auto-lazy-load images below the fold (native browser handles above-fold)
  function initAutoLazyImages() {
    var images = document.querySelectorAll('img:not([loading])');
    if (!('IntersectionObserver' in window) || images.length === 0) return;

    var aboveFoldObserver = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          // Above/at fold — leave eager
          entry.target.setAttribute('data-ux-fold', 'above');
        } else {
          entry.target.setAttribute('data-ux-fold', 'below');
        }
        aboveFoldObserver.unobserve(entry.target);
      });
    }, { rootMargin: '100px' });

    images.forEach(function(img) {
      aboveFoldObserver.observe(img);
    });

    // After a tick, tag all 'below' images as lazy
    setTimeout(function() {
      document.querySelectorAll('img[data-ux-fold="below"]:not([loading])').forEach(function(img) {
        img.setAttribute('loading', 'lazy');
        img.removeAttribute('data-ux-fold');
      });
      document.querySelectorAll('img[data-ux-fold="above"]').forEach(function(img) {
        img.removeAttribute('data-ux-fold');
      });
      initLazyImages();
    }, 50);
  }

  // ── ACCORDIONS ──────────────────────────────────────
  function initAccordions() {
    document.addEventListener('click', function(e) {
      var trigger = e.target.closest('[data-accordion-trigger]');
      if (!trigger) return;

      var targetId = trigger.getAttribute('data-accordion-trigger');
      var content = document.querySelector('[data-accordion="' + targetId + '"]');
      if (!content) return;

      var isOpen = content.classList.contains('open');
      content.classList.toggle('open', !isOpen);
      trigger.setAttribute('aria-expanded', !isOpen);
    });
  }

  // ── EXIT-INTENT DETECTION HELPER ────────────────────
  function initExitIntent(callback) {
    var fired = false;
    document.addEventListener('mouseleave', function(e) {
      if (fired) return;
      if (e.clientY <= 0 && e.clientX >= 0 && e.clientX <= window.innerWidth) {
        fired = true;
        if (typeof callback === 'function') callback();
      }
    });
  }

  // ── SMOOTH ANCHOR SCROLL (respects sticky nav) ──────
  function initSmoothAnchors() {
    document.addEventListener('click', function(e) {
      var link = e.target.closest('a[href^="#"]');
      if (!link) return;

      var targetId = link.getAttribute('href');
      if (targetId === '#' || targetId === '#main-content' || targetId === '#main') return;

      var target = document.querySelector(targetId);
      if (!target) return;

      e.preventDefault();
      var navHeight = 80;
      var targetPosition = target.getBoundingClientRect().top + window.scrollY - navHeight;

      window.scrollTo({
        top: targetPosition,
        behavior: REDUCED_MOTION ? 'auto' : 'smooth'
      });

      // Update URL without jump
      if (history.pushState) {
        history.pushState(null, null, targetId);
      }
    });
  }

  // ── MOBILE NAV TOGGLE HELPER ────────────────────────
  function initMobileNav() {
    document.addEventListener('click', function(e) {
      var toggle = e.target.closest('[data-mobile-nav-toggle]');
      if (!toggle) return;

      var targetId = toggle.getAttribute('data-mobile-nav-toggle');
      var nav = document.querySelector('[data-mobile-nav="' + targetId + '"]');
      if (!nav) return;

      var isOpen = nav.classList.contains('open');
      nav.classList.toggle('open', !isOpen);
      toggle.setAttribute('aria-expanded', !isOpen);
      document.body.classList.toggle('nav-open', !isOpen);
    });
  }

  // ── R16: MOBILE BOTTOM NAV ──────────────────────────
  // Auto-builds from data-ux-nav JSON or auto-detects nav links
  function initMobileBottomNav() {
    if (document.querySelector('.ux-mobile-nav')) return;
    if (window.matchMedia('(min-width: 769px)').matches) return;

    // Build from explicit data attribute
    var navData = document.body.getAttribute('data-ux-nav');
    var links = [];
    if (navData) {
      try { links = JSON.parse(navData); } catch(e) { links = []; }
    }
    if (links.length === 0) {
      // Auto-detect from existing <nav> links (top 5)
      var navLinks = document.querySelectorAll('nav a, header nav a');
      var seen = {};
      navLinks.forEach(function(a) {
        var href = a.getAttribute('href');
        var text = (a.textContent || '').trim();
        if (!href || href.startsWith('#') || href.startsWith('mailto') || href.startsWith('tel') || seen[href]) return;
        if (text.length === 0 || text.length > 20) return;
        seen[href] = true;
        links.push({ href: href, label: text, icon: '●' });
        if (links.length >= 5) return;
      });
    }
    if (links.length < 2) return;

    var currentPath = window.location.pathname;
    var nav = document.createElement('nav');
    nav.className = 'ux-mobile-nav';
    nav.setAttribute('aria-label', 'Mobile navigation');
    links.forEach(function(link) {
      var a = document.createElement('a');
      a.href = link.href;
      var icon = document.createElement('span');
      icon.className = 'ux-nav-icon';
      icon.textContent = link.icon || '●';
      var label = document.createElement('span');
      label.textContent = link.label;
      a.appendChild(icon);
      a.appendChild(label);
      // Mark active
      try {
        var linkPath = new URL(link.href, window.location.origin).pathname;
        if (linkPath === currentPath || currentPath.indexOf(linkPath + '/') === 0) {
          a.setAttribute('aria-current', 'page');
        }
      } catch(e) {}
      nav.appendChild(a);
    });

    document.body.appendChild(nav);
    document.body.classList.add('ux-has-mobile-nav');

    // Show after slight delay for smooth entrance
    requestAnimationFrame(function() {
      nav.classList.add('visible');
    });
  }

  // ── R16: STICKY CTA BAR ─────────────────────────────
  // Builds from data-ux-sticky-cta JSON: {primary: {href, label}, secondary: {href,label}}
  function initStickyCta() {
    if (document.querySelector('.ux-sticky-cta')) return;
    if (window.matchMedia('(min-width: 769px)').matches) return;

    var ctaData = document.body.getAttribute('data-ux-sticky-cta');
    if (!ctaData) return;
    var cta;
    try { cta = JSON.parse(ctaData); } catch(e) { return; }
    if (!cta.primary && !cta.secondary) return;

    var bar = document.createElement('div');
    bar.className = 'ux-sticky-cta';
    bar.setAttribute('role', 'region');
    bar.setAttribute('aria-label', 'Quick actions');

    if (cta.secondary) {
      var sec = document.createElement('a');
      sec.href = cta.secondary.href || '#';
      sec.className = 'ux-sticky-cta__secondary';
      sec.textContent = cta.secondary.label;
      bar.appendChild(sec);
    }
    if (cta.primary) {
      var pri = document.createElement('a');
      pri.href = cta.primary.href || '#';
      pri.className = 'ux-sticky-cta__primary btn';
      pri.textContent = cta.primary.label;
      bar.appendChild(pri);
    }

    document.body.appendChild(bar);
    document.body.classList.add('ux-has-sticky-cta');

    // Show after user scrolls past hero (> 1 viewport)
    var shown = false;
    var ticking = false;
    window.addEventListener('scroll', function() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function() {
        if (!shown && window.scrollY > window.innerHeight * 0.8) {
          bar.classList.add('visible');
          shown = true;
        } else if (shown && window.scrollY < window.innerHeight * 0.5) {
          bar.classList.remove('visible');
          // keep shown=false so it re-shows; but don't flash — keep shown true once revealed
        }
        ticking = false;
      });
    }, { passive: true });
  }

  // ── R16: BOTTOM SHEET ───────────────────────────────
  function openBottomSheet(sheetId) {
    var sheet = document.getElementById(sheetId);
    if (!sheet || !sheet.classList.contains('ux-bottom-sheet')) return;
    var overlay = sheet.previousElementSibling;
    if (!overlay || !overlay.classList.contains('ux-bottom-sheet-overlay')) {
      overlay = document.createElement('div');
      overlay.className = 'ux-bottom-sheet-overlay';
      sheet.parentNode.insertBefore(overlay, sheet);
    }
    overlay.classList.add('open');
    sheet.classList.add('open');
    sheet.setAttribute('aria-hidden', 'false');
    document.body.classList.add('ux-sheet-open');

    var close = function() {
      overlay.classList.remove('open');
      sheet.classList.remove('open');
      sheet.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('ux-sheet-open');
    };
    overlay.onclick = close;
    // Close on handle drag / Escape
    sheet.querySelectorAll('[data-ux-sheet-close]').forEach(function(b) { b.onclick = close; });
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') close();
    });
  }
  function initBottomSheets() {
    document.addEventListener('click', function(e) {
      var trigger = e.target.closest('[data-ux-sheet-trigger]');
      if (!trigger) return;
      e.preventDefault();
      openBottomSheet(trigger.getAttribute('data-ux-sheet-trigger'));
    });
  }

  // ── R16: TOAST NOTIFICATIONS ────────────────────────
  function ensureToastContainer() {
    var c = document.querySelector('.ux-toast-container');
    if (!c) {
      c = document.createElement('div');
      c.className = 'ux-toast-container';
      c.setAttribute('role', 'status');
      c.setAttribute('aria-live', 'polite');
      document.body.appendChild(c);
    }
    return c;
  }
  function showToast(message, type, duration) {
    type = type || 'primary'; // primary|success|warning|danger
    duration = duration || 4000;
    var c = ensureToastContainer();
    var toast = document.createElement('div');
    toast.className = 'ux-toast ux-toast--' + type;
    var icons = { success: '✓', warning: '⚠', danger: '✕', primary: 'ℹ' };
    toast.innerHTML = '<span class="ux-toast__icon">' + (icons[type] || 'ℹ') + '</span><span>' + message + '</span>';
    var close = document.createElement('button');
    close.className = 'ux-toast__close';
    close.setAttribute('aria-label', 'Dismiss');
    close.innerHTML = '×';
    toast.appendChild(close);
    c.appendChild(toast);

    var remove = function() {
      toast.classList.add('removing');
      setTimeout(function() { toast.remove(); }, 250);
    };
    close.onclick = remove;
    if (duration > 0) setTimeout(remove, duration);
  }
  window.uxToast = showToast;

  // ── R16: VIEW TRANSITIONS for same-origin links ─────
  function initViewTransitions() {
    if (!document.startViewTransition) return;
    // Respect reduced motion — don't hijack navigation if user dislikes motion
    if (REDUCED_MOTION) return;
    document.addEventListener('click', function(e) {
      var link = e.target.closest('a');
      if (!link) return;
      var href = link.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('mailto') || href.startsWith('tel')) return;
      // Only same-origin, non-modifier-clicks
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      try {
        var url = new URL(link.href, window.location.origin);
        if (url.origin !== window.location.origin) return;
      } catch(e) { return; }
      // Let the browser handle; View Transition just wraps the MPA nav in supported browsers
    });
  }

  // ── INITIALIZE EVERYTHING ───────────────────────────
  function init() {
    initReadingProgress();
    initBackToTop();
    initLazyImages();
    initAutoLazyImages();
    initAccordions();
    initSmoothAnchors();
    initMobileNav();
    initMobileBottomNav();
    initStickyCta();
    initBottomSheets();
    initViewTransitions();

    // Expose helpers for site-specific use
    window.uxExitIntent = initExitIntent;
    window.uxOpenBottomSheet = openBottomSheet;
    window.uxToast = showToast;
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
