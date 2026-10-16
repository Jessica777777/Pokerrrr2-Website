// Shared site behaviour: mobile nav toggle + active link highlighting.
document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.querySelector('.nav-toggle');
  const links = document.querySelector('.nav-links');

  if (toggle && links) {
    toggle.addEventListener('click', () => {
      links.classList.toggle('open');
    });
    // Close the mobile menu after a link is tapped.
    links.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', () => links.classList.remove('open'));
    });
  }

  // Highlight the current page in the nav.
  const current = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a').forEach((link) => {
    const href = link.getAttribute('href');
    if (href === current || (current === '' && href === 'index.html')) {
      link.classList.add('active');
    }
  });

  // Footer year.
  const yearEl = document.querySelector('[data-year]');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // --- Shared carousel engine (v26) ---
  // Powers both the B "feature" carousel and the C "collectibles"
  // carousel (see css/style.css's "Carousel engine" comment for the
  // matching CSS). Each .carousel-wrap[data-carousel] gets:
  //  - a true seamless infinite loop: the real slides are flanked by a
  //    full cloned copy on each side, so sliding past the last (or
  //    before the first) real slide keeps showing content; once the
  //    CSS transition finishes we silently (no-transition) jump the
  //    track back to the equivalent position within the real slides,
  //    so the illusion never runs out of clones to show.
  //  - autoplay (data-autoplay="<ms>" on the wrap) that pauses on
  //    hover/focus/touch-drag and can be toggled off with the
  //    play/pause button; prefers-reduced-motion starts paused.
  //  - progress-bar style dots (one per REAL slide) — click one to jump
  //    straight there; the active dot's fill sweeps over the autoplay
  //    interval so visitors can see when the next auto-advance lands.
  //  - left/right arrow buttons + pointer-drag (mouse/touch) swipe,
  //    since the track is a JS-transformed <div>, not a native
  //    overflow-x scroller, so there's no built-in swipe any more.
  function initCarousel(wrap) {
    const viewport = wrap.querySelector('.carousel-viewport');
    const track = wrap.querySelector('.carousel-track');
    if (!viewport || !track) return;
    const realSlides = Array.from(track.children);
    const realCount = realSlides.length;
    if (realCount < 2) return;

    // Clone a full copy of every real slide onto each side. Simplest
    // rule that's guaranteed to cover every breakpoint's --slides-visible
    // without having to read CSS custom properties in JS: even showing
    // every real slide at once, a full extra copy on each side is
    // always enough to keep the loop illusion going.
    const cloneCount = realCount;
    const originalFirst = track.firstChild;
    realSlides.slice(-cloneCount).forEach((n) => {
      const clone = n.cloneNode(true);
      clone.setAttribute('aria-hidden', 'true');
      clone.setAttribute('inert', '');
      track.insertBefore(clone, originalFirst);
    });
    realSlides.slice(0, cloneCount).forEach((n) => {
      const clone = n.cloneNode(true);
      clone.setAttribute('aria-hidden', 'true');
      clone.setAttribute('inert', '');
      track.appendChild(clone);
    });

    let index = cloneCount; // track-index currently at the viewport's left edge
    const autoplayMs = parseInt(wrap.getAttribute('data-autoplay'), 10) || 5000;
    // Keep the active dot's progress sweep in sync with the real interval
    // (CSS falls back to 5000ms when this custom property is missing).
    wrap.style.setProperty('--autoplay-ms', autoplayMs + 'ms');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let userPaused = reducedMotion;
    let hoverPaused = false;
    let hiddenPaused = document.hidden; // tab in background — see visibilitychange below
    let dragging = false;
    let dragStartX = 0;
    let dragBaseOffset = 0;
    let timer = null;
    let settleTimer = null; // fallback for a transitionend that never arrives

    function slideStep() {
      const first = track.children[0];
      if (!first) return 0;
      const cs = getComputedStyle(track);
      const gap = parseFloat(cs.columnGap || cs.gap || '0') || 0;
      return first.getBoundingClientRect().width + gap;
    }
    function applyTransform(withTransition) {
      if (!withTransition) track.classList.add('no-transition');
      track.style.transform = `translateX(${-index * slideStep()}px)`;
      if (!withTransition) {
        void track.offsetHeight; // force reflow before re-enabling transitions
        requestAnimationFrame(() => track.classList.remove('no-transition'));
      }
    }
    function realIndex() { return ((index - cloneCount) % realCount + realCount) % realCount; }
    function isPlaying() { return !userPaused && !hoverPaused && !hiddenPaused && !dragging; }

    // Longest transform transition on the track, in ms (0 if none).
    function transitionMs() {
      const cs = getComputedStyle(track);
      const toMs = (v) => (v.trim().endsWith('ms') ? parseFloat(v) : parseFloat(v) * 1000) || 0;
      const durs = (cs.transitionDuration || '0s').split(',').map(toMs);
      const delays = (cs.transitionDelay || '0s').split(',').map(toMs);
      return durs.reduce((max, d, i) => Math.max(max, d + (delays[i % delays.length] || 0)), 0);
    }

    // Pull `index` back into the real-slide range [cloneCount, cloneCount + realCount)
    // and jump there with no transition. Uses modulo rather than a single
    // ±realCount step, so it also recovers when the index has drifted
    // several slides out (e.g. transitionend never fired while the tab
    // was in the background, which used to leave the track translated
    // past every slide = blank carousel). Returns true if it moved.
    function settle() {
      clearTimeout(settleTimer);
      settleTimer = null;
      if (index >= cloneCount && index < cloneCount + realCount) return false;
      index = cloneCount + realIndex();
      track.classList.add('no-transition');
      track.style.transform = `translateX(${-index * slideStep()}px)`;
      void track.offsetHeight; // commit the jump before transitions come back
      track.classList.remove('no-transition');
      void track.offsetHeight;
      return true;
    }

    function updateDots() {
      const dots = wrap.querySelectorAll('.carousel-dot');
      if (!dots.length) return;
      const active = realIndex();
      const playing = isPlaying();
      dots.forEach((dot) => dot.classList.remove('is-animating'));
      void wrap.offsetWidth; // force reflow so the fill animation restarts cleanly
      dots.forEach((dot, i) => {
        const isActive = i === active;
        dot.classList.toggle('is-active', isActive);
        if (isActive && playing) dot.classList.add('is-animating');
      });
    }
    function stopAutoplay() { if (timer) { clearTimeout(timer); timer = null; } }
    function scheduleAutoplay() {
      stopAutoplay();
      if (!isPlaying()) return;
      timer = setTimeout(next, autoplayMs);
    }
    function refresh() {
      wrap.classList.toggle('is-paused', userPaused || hoverPaused);
      updateDots();
      scheduleAutoplay();
    }
    function goTo(newIndex, withTransition) {
      index = newIndex;
      const animate = withTransition !== false;
      applyTransform(animate);
      clearTimeout(settleTimer);
      settleTimer = null;
      // Safety net: transitionend can be skipped (background tab, transition
      // interrupted, element briefly display:none). Settle anyway once the
      // transition should have finished.
      if (animate) settleTimer = setTimeout(settle, transitionMs() + 100);
    }
    // Every move starts by settling, so a missed transitionend can never
    // let the index keep counting up past the clones.
    function next() { settle(); goTo(index + 1); refresh(); }
    function prev() { settle(); goTo(index - 1); refresh(); }
    function goToReal(i) { settle(); goTo(cloneCount + i); refresh(); }

    // Once a slide-to-slide transition finishes, silently snap the track
    // back into the real-slide range if we've drifted into a clone zone
    // — the clone at that position mirrors the real slide exactly, so
    // this jump is invisible to the visitor.
    track.addEventListener('transitionend', (e) => {
      if (e.target !== track || e.propertyName !== 'transform') return;
      settle();
      // Lets other features follow the carousel's rhythm (see
      // initAnimTakeTurns: nameplates animate after each move).
      wrap.dispatchEvent(new CustomEvent('carousel:moved'));
    });

    // Background tab: browsers throttle timers and skip transitions /
    // transitionend for hidden documents. Pause autoplay while hidden and
    // re-sync the track position when the tab comes back.
    document.addEventListener('visibilitychange', () => {
      hiddenPaused = document.hidden;
      if (hiddenPaused) {
        stopAutoplay();
        settle();
      } else {
        settle();
        applyTransform(false);
        refresh();
      }
    });

    // Arrows.
    const prevBtn = wrap.querySelector('.carousel-arrow-prev');
    const nextBtn = wrap.querySelector('.carousel-arrow-next');
    if (prevBtn) prevBtn.addEventListener('click', prev);
    if (nextBtn) nextBtn.addEventListener('click', next);

    // Dots — one per REAL slide (clones don't get one).
    const dotsWrap = wrap.querySelector('.carousel-dots');
    if (dotsWrap) {
      for (let i = 0; i < realCount; i++) {
        const dot = document.createElement('button');
        dot.type = 'button';
        dot.className = 'carousel-dot';
        dot.innerHTML = '<span class="carousel-dot-fill"></span>';
        dot.addEventListener('click', () => goToReal(i));
        dotsWrap.appendChild(dot);
      }
    }
    function relabelDots() {
      const lang = (window.OFC_I18N_CURRENT) || 'en';
      // Note: I18N is declared with `const` in js/i18n.js, so — unlike a
      // `var` or function declaration — it never becomes a property of
      // `window`. It's still reachable as a bare identifier here because
      // both files are classic (non-module) scripts sharing one global
      // scope, just not via `window.I18N`.
      const dict = (typeof I18N !== 'undefined' && I18N[lang]) || {};
      const tpl = dict['common.carousel.goTo'] || 'Go to slide {n}';
      wrap.querySelectorAll('.carousel-dot').forEach((dot, i) => {
        dot.setAttribute('aria-label', tpl.replace('{n}', i + 1));
      });
    }

    // Play/pause toggle — an explicit visitor override, separate from
    // the transient hover/focus pause below (leaving hover shouldn't
    // silently resume autoplay after the visitor has paused it on purpose).
    const playPauseBtn = wrap.querySelector('.carousel-playpause');
    function updatePlayPauseUI() {
      if (!playPauseBtn) return;
      const iconPause = playPauseBtn.querySelector('.icon-pause');
      const iconPlay = playPauseBtn.querySelector('.icon-play');
      const lang = (window.OFC_I18N_CURRENT) || 'en';
      const dict = (typeof I18N !== 'undefined' && I18N[lang]) || {};
      // toggleAttribute, not `.hidden = …`: these icons are <svg> elements,
      // and SVGElement has no `hidden` IDL property — assigning it only sets
      // a JS expando and never touches the attribute, which is why both
      // icons used to render side by side. CSS `svg[hidden]` does the hiding.
      if (iconPause) iconPause.toggleAttribute('hidden', userPaused);
      if (iconPlay) iconPlay.toggleAttribute('hidden', !userPaused);
      playPauseBtn.setAttribute('aria-label', (userPaused ? dict['common.carousel.play'] : dict['common.carousel.pause']) || 'Play/pause');
    }
    if (playPauseBtn) {
      playPauseBtn.addEventListener('click', () => {
        userPaused = !userPaused;
        updatePlayPauseUI();
        refresh();
      });
    }
    document.addEventListener('ofc:langchange', () => { relabelDots(); updatePlayPauseUI(); });

    // Pause on hover/focus (mouse & keyboard users); resumes on
    // leave unless the visitor explicitly paused via the button above.
    wrap.addEventListener('mouseenter', () => { hoverPaused = true; refresh(); });
    wrap.addEventListener('mouseleave', () => { hoverPaused = false; refresh(); });
    wrap.addEventListener('focusin', () => { hoverPaused = true; refresh(); });
    wrap.addEventListener('focusout', () => { hoverPaused = false; refresh(); });

    // Pointer-drag swipe (mouse + touch) — the track is a JS-transformed
    // element now, not a native scroller, so this replaces the swipe
    // that overflow-x used to give us for free.
    track.addEventListener('pointerdown', (e) => {
      settle(); // make sure the drag starts from a real slide
      dragging = true;
      dragStartX = e.clientX;
      dragBaseOffset = -index * slideStep();
      track.classList.add('is-dragging');
      stopAutoplay();
      try { track.setPointerCapture(e.pointerId); } catch (err) { /* unsupported, ignore */ }
    });
    track.addEventListener('pointermove', (e) => {
      if (!dragging) return;
      track.style.transform = `translateX(${dragBaseOffset + (e.clientX - dragStartX)}px)`;
    });
    function endDrag(e) {
      if (!dragging) return;
      dragging = false;
      track.classList.remove('is-dragging');
      const delta = e.clientX - dragStartX;
      const threshold = Math.max(40, slideStep() * 0.15);
      if (delta > threshold) prev();
      else if (delta < -threshold) next();
      else { goTo(index); refresh(); }
    }
    track.addEventListener('pointerup', endDrag);
    track.addEventListener('pointercancel', endDrag);

    // Left/right arrow keys when the track has keyboard focus.
    track.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') { e.preventDefault(); prev(); }
      if (e.key === 'ArrowRight') { e.preventDefault(); next(); }
    });

    // --slides-visible changes at breakpoints, which changes the slide's
    // pixel width — recompute and snap (no transition) on resize.
    let resizeTimer = null;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => { settle(); applyTransform(false); }, 120);
    });

    applyTransform(false);
    relabelDots();
    updatePlayPauseUI();
    refresh();
  }

  document.querySelectorAll('.carousel-wrap[data-carousel]').forEach(initCarousel);
  initAnimTakeTurns();

  // --- Animated nameplates: one at a time, in step with the carousel ---
  // (2026-10-08) Each <img data-anim-src data-anim-ms> normally shows a
  // still (its animation's final frame). Every time the carousel finishes
  // a move, the on-screen nameplate nearest the middle of the screen plays
  // its animated WebP once, then swaps back to the still -- so animation
  // and slide movement share one rhythm. The one that just played never
  // plays twice in a row, and cards near the edges are ignored (no play
  // that step if nothing qualifies). If the carousel is stopped (hover / pause button), nameplates
  // keep taking turns on their own timer instead.
  // An animated WebP can't be restarted reliably by re-setting the same
  // src, so each play uses a fresh blob: URL (new URL = new decode = starts
  // at frame 0). Carousel clones share data-anim-src, so all copies of one
  // nameplate play together. Skipped entirely for prefers-reduced-motion.
  function initAnimTakeTurns() {
    const imgs = [...document.querySelectorAll('img[data-anim-src]')];
    if (!imgs.length) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const REST_MS = 500; // minimum rest between two plays
    const IDLE_MS = 6000; // no carousel move for this long = carousel stopped
    const keys = [...new Set(imgs.map((img) => img.getAttribute('data-anim-src')))];
    const groups = keys.map((key) => {
      const members = imgs.filter((img) => img.getAttribute('data-anim-src') === key);
      return {
        key,
        members,
        still: members[0].getAttribute('src'),
        ms: parseInt(members[0].getAttribute('data-anim-ms'), 10) || 3000,
        blob: null,
      };
    });
    let last = null; // group that played most recently
    let playing = false;
    let lastEnd = 0; // when the previous play finished
    let lastMove = 0; // when the carousel last finished a move

    function onScreen(img) {
      const r = img.getBoundingClientRect();
      const box = (img.closest('.carousel-viewport') || document.documentElement).getBoundingClientRect();
      const left = Math.max(r.left, box.left, 0);
      const right = Math.min(r.right, box.right, window.innerWidth);
      return r.width > 0 && right - left > r.width * 0.6 && r.bottom > 0 && r.top < window.innerHeight;
    }

    async function loadBlob(g) {
      if (g.blob) return g.blob;
      const res = await fetch(new URL(g.key, document.baseURI));
      if (!res.ok) throw new Error('anim fetch ' + res.status);
      g.blob = await res.blob();
      return g.blob;
    }

    function pick() {
      const mid = window.innerWidth / 2;
      let g = null;
      let best = Infinity;
      groups.forEach((cand) => {
        if (cand === last && groups.length > 1) return; // never twice in a row
        cand.members.filter(onScreen).forEach((img) => {
          const r = img.getBoundingClientRect();
          const off = Math.abs(r.left + r.width / 2 - mid);
          if (off > window.innerWidth * 0.35) return; // too close to the edge
          if (off < best) { best = off; g = cand; }
        });
      });
      return g;
    }

    async function play() {
      if (playing || document.hidden || Date.now() - lastEnd < REST_MS) return;
      const g = pick();
      if (!g) return; // no nameplate near the middle this time
      playing = true;
      let url;
      try { url = URL.createObjectURL(await loadBlob(g)); } catch (e) { playing = false; return; }
      last = g;
      g.members.forEach((img) => { img.src = url; });
      setTimeout(() => {
        g.members.forEach((img) => { img.src = g.still; });
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        playing = false;
        lastEnd = Date.now();
      }, g.ms);
    }

    // Follow the carousel: play right after each move settles.
    new Set(imgs.map((img) => img.closest('[data-carousel]')).filter(Boolean)).forEach((wrap) => {
      wrap.addEventListener('carousel:moved', () => {
        lastMove = Date.now();
        play();
      });
    });
    // Fallback while the carousel is stopped (and for the first play on load).
    setInterval(() => {
      if (Date.now() - lastMove > IDLE_MS) play();
    }, 1000);
    // Warm the blobs in the background so the first play starts on time.
    groups.forEach((g) => { loadBlob(g).catch(() => {}); });
  }
});

/* Pokerrrr2 FAQ: category filter. Every answer is already in the HTML (SEO);
   without JS all categories show with their headings. faq.html#gold-01 opens
   that category and question. */
(function initFaqCategories() {
  const cats = document.getElementById('faqCats');
  if (!cats) return;
  const groups = document.querySelectorAll('.faq-group');
  document.documentElement.classList.add('js-faq');
  function show(id) {
    groups.forEach((g) => { g.hidden = g.dataset.cat !== id; });
    cats.querySelectorAll('.faq-cat').forEach((b) => {
      const on = b.dataset.cat === id;
      b.classList.toggle('is-active', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }
  cats.addEventListener('click', (e) => {
    const b = e.target.closest('.faq-cat');
    if (b) show(b.dataset.cat);
  });
  const target = location.hash && document.getElementById(location.hash.slice(1));
  if (target && target.classList.contains('faq-item')) {
    show(target.closest('.faq-group').dataset.cat);
    target.open = true;
    target.scrollIntoView();
  } else if (groups.length) {
    show(groups[0].dataset.cat);
  }
})();

// News list: category filter + "Load more" (all cards are in the HTML, so
// without JS everything is simply shown).
(function initNewsList() {
  const grid = document.getElementById('news-grid');
  if (!grid) return;
  const cards = Array.from(grid.querySelectorAll('.news-card'));
  const chips = Array.from(document.querySelectorAll('.news-chip'));
  const moreWrap = document.querySelector('.news-more');
  const moreBtn = document.getElementById('news-more');
  const size = parseInt(grid.dataset.pageSize, 10) || 12;
  let cat = 'all';
  let shown = size;
  function render() {
    const match = cards.filter((c) => cat === 'all' || c.dataset.cat === cat);
    cards.forEach((c) => { c.hidden = true; });
    match.slice(0, shown).forEach((c) => { c.hidden = false; });
    if (moreWrap) moreWrap.hidden = match.length <= shown;
  }
  chips.forEach((chip) => chip.addEventListener('click', () => {
    cat = chip.dataset.cat;
    shown = size;
    chips.forEach((c) => {
      const on = c === chip;
      c.classList.toggle('is-active', on);
      c.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    render();
  }));
  if (moreBtn) moreBtn.addEventListener('click', () => { shown += size; render(); });
  render();
})();
