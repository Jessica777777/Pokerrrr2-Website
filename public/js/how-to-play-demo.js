/**
 * How-to-Play: full interactive walkthrough of the in-app tutorial.
 *
 * v4 — every round (1-5) is now something the visitor actually places
 * themselves (click-to-select-then-click-target AND native drag-and-drop
 * both work), instead of rounds 1-4 being an auto-applied "guided reveal".
 *
 * v21 — reworked the placement rule and the round-1-4 "wrong" outcome per
 * direct user feedback, referencing the app's own OFC-tutorial spec doc
 * (which places cards "exactly like the real game" — i.e. any row, capped
 * only by that row's remaining physical slots — then auto-corrects to the
 * scripted layout on confirm rather than blocking the player):
 *  - openCap() now returns each row's REAL remaining capacity
 *    (TOTAL_MAX[row] minus what earlier rounds already placed there), not
 *    the scripted per-round split. A card can go in any row that still has
 *    room, not just the one the script has in mind for it.
 *  - Confirming a round 1-4 no longer has a blocking "wrong, try again"
 *    outcome. It always locks and advances: if the free placement already
 *    matches the script, that's a normal success; if not, the mismatched
 *    cards are silently reassigned to the script's row (correctRowFor) and
 *    the same per-round explanation text is shown, framed as "here's the
 *    recommended layout" rather than "here's why you were right".
 *  - Round 5 is the one exception, kept on user request: it still runs the
 *    real hand-strength evaluator (back >= middle >= front) rather than
 *    snapping to a script, because that comparison is only meaningful once
 *    all three rows are complete. The old dedicated "Show me a foul" demo
 *    button was removed, though — a foul is now only ever seen by actually
 *    drawing one, with a bomb-emoji animation on that reveal instead of a
 *    tucked-away demo path.
 * See how-to-play-page-task-context.md "v21" for the full discussion.
 *
 * v22 — four follow-up fixes from direct user feedback on v21:
 *  - openCap() (real remaining ROW capacity) was the only limit on free
 *    placement, but a round only deals a fixed number of cards you're
 *    allowed to place (2 for rounds 2-5) — the rest must stay in the tray
 *    as the discard, even if some other row still has spare room. Added
 *    withinRoundQuota() as a second, independent check, with a small hint
 *    (#ofcDemoHint) explaining the rejection instead of silently no-op'ing.
 *  - Confirm now relabels itself to "Next" once a non-final round is
 *    locked, instead of requiring a second click on the separate nav
 *    arrow to advance (see the confirmBtn click handler and
 *    renderControls()).
 *  - The round-by-round title/desc copy (steps 1-5) was checked against
 *    the actual Notion tutorial spec's per-round card text — round 3's
 *    "front row max 3" reminder was never in that source and has been
 *    replaced; see js/i18n.js.
 * See how-to-play-page-task-context.md "v22" for the full discussion.
 *
 * For rounds 1-4 (Page 2-5 in the tutorial spec doc), "correct" means
 * matching that round's one scripted placement (each dealt card has a
 * single correct destination row, or must be left undiscarded/undrafted
 * in the tray if the script discards it) — we deliberately do NOT
 * evaluate real poker hand strength on these incomplete rows (that was
 * the exact mistake in v1: comparing partial rows is misleading). Nothing
 * is graded as a "foul" until row 5, which is the one round where the rows
 * involved are actually complete (front 3, middle 5, back 5) and a real
 * back >= middle >= front check is meaningful.
 *
 * Because rounds 1-4 are solved for real cards (not invented
 * placeholders), the board state feeding into round 5 is exactly the
 * tutorial's own continuous example hand: front ends up Q♥ Q♦ (before the
 * final CQ), middle ends up H3 H2 D2 C3 (before the final D3), and back
 * is already complete at S7 S8 S9 ST SJ (a straight flush) after round 3.
 *
 * Deliberately NOT the real game engine — the hand ranking below is a
 * simplified evaluator that works for any 0-5 card subset, built only to
 * teach the row-order rule on this marketing page.
 */
(function () {
  const SUITS = { S: '♠', H: '♥', D: '♦', C: '♣' };
  const SUIT_FILE = { S: 'spade', H: 'heart', D: 'diamond', C: 'club' };
  const RED_SUITS = ['H', 'D'];
  // v35: real card-set artwork (assets/images/cards/, from the user's
  // 素材/POKER/V08 material), same asset set the game-rules pages use --
  // see makeCardEl() below. This script is shared by the root (English)
  // how-to-play.html AND the generated zh/ and ja/ copies one directory
  // down (see tools/build_i18n.py) -- ofcStaticLang() (js/i18n.js) reports
  // which static copy is running, so a plain 'assets/...' path (correct at
  // root) doesn't 404 once it's nested under zh/ or ja/ instead.
  const STATIC_LANG = (typeof ofcStaticLang === 'function') ? ofcStaticLang() : null;
  const ASSET_PREFIX = (STATIC_LANG === 'zh' || STATIC_LANG === 'ja') ? '../' : '';
  const CARD_IMG_BASE = ASSET_PREFIX + 'assets/images/cards/';
  const RANK_FILE_LABEL = { 14: 'A', 13: 'K', 12: 'Q', 11: 'J' };
  const RANK_LABEL = { 14: 'A', 13: 'K', 12: 'Q', 11: 'J' };
  const ROW_ORDER = ['front', 'middle', 'back'];
  const TOTAL_MAX = { front: 3, middle: 5, back: 5 };

  const ROUNDS = [
    null,
    {
      dealt: [
        { rank: 3, suit: 'H' }, { rank: 2, suit: 'H' },
        { rank: 11, suit: 'S' }, { rank: 10, suit: 'S' }, { rank: 7, suit: 'S' },
      ],
      place: { front: [], middle: [0, 1], back: [2, 3, 4] },
      discard: [],
    },
    {
      dealt: [{ rank: 2, suit: 'D' }, { rank: 9, suit: 'S' }, { rank: 10, suit: 'D' }],
      place: { front: [], middle: [0], back: [1] },
      discard: [2],
    },
    {
      dealt: [{ rank: 12, suit: 'H' }, { rank: 8, suit: 'S' }, { rank: 4, suit: 'S' }],
      place: { front: [0], middle: [], back: [1] },
      discard: [2],
    },
    {
      dealt: [{ rank: 12, suit: 'D' }, { rank: 3, suit: 'C' }, { rank: 11, suit: 'D' }],
      place: { front: [0], middle: [1], back: [] },
      discard: [2],
    },
    {
      dealt: [{ rank: 9, suit: 'C' }, { rank: 12, suit: 'C' }, { rank: 3, suit: 'D' }],
      place: { front: [1], middle: [2], back: [] },
      discard: [0],
    },
  ];

  const LAST_STEP = ROUNDS.length - 1;

  function t(key) {
    const lang = (typeof ofcGetLang === 'function') ? ofcGetLang() : 'en';
    // Note: I18N is declared with `const` in js/i18n.js, so it never becomes
    // a `window` property (unlike `var`/function declarations) even though
    // both files are classic scripts sharing one global scope — read the
    // bare identifier instead. (Same latent bug as main.js's carousel code
    // had before the v26 fix; this file had never been opened in a real
    // browser since it was written, so it went unnoticed until now.)
    const dict = (typeof I18N !== 'undefined' && I18N[lang]) || {};
    return dict[key] !== undefined ? dict[key] : key;
  }

  function cardLabel(card) {
    return RANK_LABEL[card.rank] || String(card.rank);
  }

  function rankCards(cards) {
    if (!cards.length) return [-1];
    const ranks = cards.map((c) => c.rank).sort((a, b) => b - a);
    const bySuit = {};
    cards.forEach((c) => { bySuit[c.suit] = (bySuit[c.suit] || 0) + 1; });
    const isFlush = cards.length === 5 && Object.keys(bySuit).length === 1;

    const uniq = [...new Set(ranks)];
    let isStraight = false;
    let straightHigh = 0;
    if (cards.length === 5 && uniq.length === 5) {
      if (uniq[0] - uniq[4] === 4) { isStraight = true; straightHigh = uniq[0]; }
      else if (uniq.join(',') === '14,5,4,3,2') { isStraight = true; straightHigh = 5; }
    }

    const counts = {};
    ranks.forEach((r) => { counts[r] = (counts[r] || 0) + 1; });
    const groups = Object.keys(counts)
      .map((r) => [Number(r), counts[r]])
      .sort((a, b) => (b[1] - a[1]) || (b[0] - a[0]));
    const kickers = groups.filter((g) => g[1] === 1).map((g) => g[0]);

    if (isStraight && isFlush) return [8, straightHigh];
    if (groups[0][1] === 4) return [7, groups[0][0], ...kickers];
    if (cards.length === 5 && groups[0][1] === 3 && groups[1] && groups[1][1] >= 2) {
      return [6, groups[0][0], groups[1][0]];
    }
    if (isFlush) return [5, ...ranks];
    if (isStraight) return [4, straightHigh];
    if (groups[0][1] === 3) return [3, groups[0][0], ...kickers];
    if (groups[0][1] === 2 && groups[1] && groups[1][1] === 2) {
      const pairRanks = [groups[0][0], groups[1][0]].sort((a, b) => b - a);
      return [2, ...pairRanks, ...kickers];
    }
    if (groups[0][1] === 2) return [1, groups[0][0], ...kickers];
    return [0, ...ranks];
  }

  function compareRank(a, b) {
    const len = Math.max(a.length, b.length);
    for (let i = 0; i < len; i += 1) {
      const av = a[i] === undefined ? -1 : a[i];
      const bv = b[i] === undefined ? -1 : b[i];
      if (av !== bv) return av > bv ? 1 : -1;
    }
    return 0;
  }

  const CAT_KEYS = [
    'howToPlay.interactive.cat.high',
    'howToPlay.interactive.cat.pair',
    'howToPlay.interactive.cat.twoPair',
    'howToPlay.interactive.cat.trips',
    'howToPlay.interactive.cat.straight',
    'howToPlay.interactive.cat.flush',
    'howToPlay.interactive.cat.fullHouse',
    'howToPlay.interactive.cat.quads',
    'howToPlay.interactive.cat.straightFlush',
  ];

  function categoryName(rankInfo) {
    if (rankInfo[0] < 0) return t('howToPlay.interactive.cat.empty');
    return t(CAT_KEYS[rankInfo[0]]);
  }

  function boardBefore(upToStep) {
    const board = { front: [], middle: [], back: [] };
    for (let s = 1; s < upToStep; s += 1) {
      const round = ROUNDS[s];
      ROW_ORDER.forEach((row) => {
        round.place[row].forEach((idx) => board[row].push(round.dealt[idx]));
      });
    }
    return board;
  }

  function initOfcDemo(root) {
    const titleEl = root.querySelector('#ofcDemoTitle');
    const descEl = root.querySelector('#ofcDemoDesc');
    const progressEl = root.querySelector('#ofcDemoProgress');
    const restartBtn = root.querySelector('#ofcDemoRestart');
    const handEl = root.querySelector('#ofcDemoHand');
    const resultEl = root.querySelector('#ofcDemoResult');
    const navControls = root.querySelector('#ofcDemoNavControls');
    const prevBtn = root.querySelector('#ofcDemoPrev');
    const nextBtn = root.querySelector('#ofcDemoNext');
    const dotsEl = root.querySelector('#ofcDemoDots');
    const roundControls = root.querySelector('#ofcDemoStep5Controls');
    const confirmBtn = root.querySelector('#ofcDemoConfirm');
    const resetBtn = root.querySelector('#ofcDemoReset');
    const boomEl = root.querySelector('#ofcDemoBoom');
    const hintEl = root.querySelector('#ofcDemoHint');
    const rowEls = {
      front: root.querySelector('[data-row="front"]'),
      middle: root.querySelector('[data-row="middle"]'),
      back: root.querySelector('[data-row="back"]'),
    };

    let step = 0;

    let placement = [];
    let selected = null;
    let locked = false;
    let lastResult = null;
    let dragIdx = null;
    let quotaHintVisible = false;
    // v29d: absolute slot position (0-based, within the row's fixed
    // TOTAL_MAX[row] grid) that this round's card `idx` was actually
    // dropped/clicked into — keyed by dealt-index, only meaningful while
    // placement[idx] is a row (not 'tray'). Lets a card stay exactly where
    // the visitor put it instead of always packing to the leftmost open
    // slot; see firstOpenSlot()/renderBoard() below.
    let liveSlot = {};

    function currentRound() { return ROUNDS[step]; }

    function openCap(row) {
      // v21: real remaining physical capacity for this row — whatever
      // TOTAL_MAX[row] allows, minus what earlier rounds already placed
      // there — not the scripted count for THIS round. This is what lets
      // the visitor place any of the round's cards into any row that
      // still has room, exactly like the real game, instead of being
      // boxed into the one row split the script has in mind.
      const round = currentRound();
      if (!round) return 0;
      return TOTAL_MAX[row] - boardBefore(step)[row].length;
    }

    function totalToPlace() {
      const round = currentRound();
      if (!round) return 0;
      return round.dealt.length - round.discard.length;
    }

    // v22: openCap() (above) only checks a ROW's real remaining physical
    // capacity — it happily lets you place a 3rd card this round into a
    // row that still has room, even though this round only deals 3 cards
    // and 1 of them has to stay in the tray as a discard. That's a second,
    // independent limit ("how many of THIS round's cards can leave the
    // tray") on top of the row-capacity one, so it needs its own check:
    // a card already off the tray (in some row) never counts against this
    // — only cards still sitting in the tray attempting to move out do.
    function withinRoundQuota(idx) {
      if (placement[idx] !== 'tray') return true;
      const placedCount = placement.filter((loc) => loc !== 'tray').length;
      return placedCount < totalToPlace();
    }

    function dealtIn(row) {
      return placement
        .map((loc, idx) => (loc === row ? idx : -1))
        .filter((idx) => idx !== -1)
        .map((idx) => currentRound().dealt[idx]);
    }

    function correctRowFor(idx) {
      const round = currentRound();
      const row = ROW_ORDER.find((r) => round.place[r].includes(idx));
      return row || 'tray';
    }

    function scriptMatches() {
      const round = currentRound();
      return round.dealt.every((_, idx) => placement[idx] === correctRowFor(idx));
    }

    function fullRowForEval(row) {
      return [...boardBefore(step)[row], ...dealtIn(row)];
    }

    function makeCardEl(card, opts) {
      const el = document.createElement('div');
      el.className = 'ofc-card' + (RED_SUITS.includes(card.suit) ? ' is-red' : '');
      if (opts && opts.preset) el.classList.add('preset');
      if (opts && opts.selected) el.classList.add('selected');
      if (opts && opts.idx !== undefined) {
        el.dataset.idx = String(opts.idx);
        if (!locked) {
          el.draggable = true;
          el.addEventListener('dragstart', (e) => {
            dragIdx = opts.idx;
            el.classList.add('dragging');
            if (e.dataTransfer) {
              e.dataTransfer.effectAllowed = 'move';
              try { e.dataTransfer.setData('text/plain', String(opts.idx)); } catch (err) { /* Safari needs a type set even if unused */ }
            }
          });
          el.addEventListener('dragend', () => {
            dragIdx = null;
            el.classList.remove('dragging');
          });
        }
      }
      const isRed = RED_SUITS.includes(card.suit);
      const rankFile = (RANK_FILE_LABEL[card.rank] || String(card.rank)) + (isRed ? '_r' : '_b') + '.png';
      const suitFile = (SUIT_FILE[card.suit] || '') + '.png';
      el.innerHTML = ''
        + '<img class="ofc-card-rank" src="' + CARD_IMG_BASE + rankFile + '" alt="' + cardLabel(card) + '">'
        + '<img class="ofc-card-suit" src="' + CARD_IMG_BASE + suitFile + '" alt="' + SUITS[card.suit] + '">';
      return el;
    }

    function resetRoundState() {
      const round = currentRound();
      placement = round ? round.dealt.map(() => 'tray') : [];
      selected = null;
      locked = false;
      lastResult = null;
      dragIdx = null;
      quotaHintVisible = false;
      liveSlot = {};
      ROW_ORDER.forEach((row) => rowEls[row].classList.remove('result-ok', 'result-foul'));
    }

    function selectCard(idx) {
      if (locked) return;
      selected = selected === idx ? null : idx;
      render();
    }

    // v29d: this round's playable area within `row` is the absolute slots
    // from boardBefore(step)[row].length (wherever the locked-in preset
    // cards from earlier rounds stop) up to TOTAL_MAX[row]-1. Returns the
    // first of those not already claimed by some other card of this
    // round (excludeIdx's own current slot doesn't block itself).
    function firstOpenSlot(row, excludeIdx) {
      const presetCount = boardBefore(step)[row].length;
      for (let i = presetCount; i < TOTAL_MAX[row]; i++) {
        const takenByOther = placement.some((loc, otherIdx) =>
          loc === row && otherIdx !== excludeIdx && liveSlot[otherIdx] === i);
        if (!takenByOther) return i;
      }
      return presetCount;
    }

    // v29d-followup: after a round confirms — whether the placement was
    // already correct or got auto-corrected — every one of this round's
    // placed cards collapses to the leftmost open slots in its row (in
    // ascending dealt-index order), so a confirmed round never sits with
    // a gap at whatever slot the visitor happened to drop a card into.
    // Per user feedback: previously only the auto-corrected cards got
    // reassigned a fresh (left-packed) slot; an already-correct placement
    // kept whatever slot the visitor dragged/clicked it into and did not
    // snap left on confirm.
    function packLeftAll() {
      ROW_ORDER.forEach((row) => {
        const presetCount = boardBefore(step)[row].length;
        const idxs = placement
          .map((loc, idx) => (loc === row ? idx : -1))
          .filter((idx) => idx !== -1);
        idxs.forEach((idx, i) => { liveSlot[idx] = presetCount + i; });
      });
    }

    function placeCard(idx, row, slotIndex) {
      if (locked) return;
      if (row !== 'tray') {
        if (dealtIn(row).length >= openCap(row) && placement[idx] !== row) return;
        if (!withinRoundQuota(idx)) {
          // v22: row had room, but this round's own "only N cards leave
          // the tray" limit was hit — reject and explain why, rather than
          // silently doing nothing (which read as a broken click).
          quotaHintVisible = true;
          render();
          return;
        }
      }
      placement[idx] = row;
      if (row === 'tray') {
        delete liveSlot[idx];
      } else {
        // v29d: land on the exact slot the visitor targeted (drag onto a
        // specific box, or click a specific empty box) instead of always
        // repacking to the leftmost open slot. Falls back to "first open
        // slot" only when no specific slot was given (e.g. dropping
        // somewhere in the row that isn't a slot element) or that slot
        // got claimed by something else in between.
        const wanted = slotIndex;
        const alreadyTaken = wanted !== undefined && wanted !== null
          && placement.some((loc, otherIdx) => loc === row && otherIdx !== idx && liveSlot[otherIdx] === wanted);
        liveSlot[idx] = (wanted === undefined || wanted === null || alreadyTaken)
          ? firstOpenSlot(row, idx)
          : wanted;
      }
      selected = null;
      quotaHintVisible = false;
      render();
    }

    function wireDropTarget(el, targetRow, slotIndex) {
      el.addEventListener('dragover', (e) => {
        if (dragIdx === null || locked) return;
        const already = placement[dragIdx] === targetRow;
        const hasRoom = targetRow === 'tray' || already
          || (dealtIn(targetRow).length < openCap(targetRow) && withinRoundQuota(dragIdx));
        if (hasRoom) {
          e.preventDefault();
          el.classList.add('drag-over');
        }
      });
      el.addEventListener('dragleave', () => el.classList.remove('drag-over'));
      el.addEventListener('drop', (e) => {
        el.classList.remove('drag-over');
        if (dragIdx === null || locked) return;
        e.preventDefault();
        placeCard(dragIdx, targetRow, slotIndex);
        dragIdx = null;
      });
    }

    // v29d: an empty slot is both a drop target (drag) and, since clicks
    // bubble up to the row's own click listener which doesn't know which
    // slot was actually clicked, needs its own click handler too so a
    // specific slot can be targeted by click-to-place as well as drag.
    function wireEmptySlot(el, row, slotIndex) {
      wireDropTarget(el, row, slotIndex);
      el.addEventListener('click', (e) => {
        if (locked || !currentRound()) return;
        e.stopPropagation();
        if (selected !== null) placeCard(selected, row, slotIndex);
      });
    }

    // v30-followup10: #ofcDemoDesc's text is different on every step (and a
    // different length in every language), so its line count used to vary
    // freely -- 2 lines on one step, 4-5 on the next at common desktop widths
    // (worst in English, whose sentences run longer than the zh/ja text).
    // Since #ofcDemoDesc and #ofcDemoResult share one CSS Grid cell (see
    // .ofc-demo-desc-wrap, v29e-followup3), that row's height always equals
    // its tallest occupant -- so instead of measuring with JS and writing a
    // resize listener, this just always keeps a real-but-invisible copy of
    // every possible desc string stacked in that same grid cell. The grid
    // auto-sizes the row to the tallest of all of them, at whatever width
    // the widget currently renders at, so navigating between steps (or
    // resizing the window) never changes #ofcDemoDesc's reserved height --
    // the board below it stops jumping. No JS measurement, no resize
    // listener: it falls out of the same grid invariant already in place.
    let descProbesBuilt = false;
    function ensureDescProbes() {
      if (descProbesBuilt) return;
      descProbesBuilt = true;
      const keys = ['howToPlay.interactive.step0.desc'];
      for (let s = 1; s < LAST_STEP; s++) keys.push('howToPlay.interactive.step' + s + '.desc');
      keys.push('howToPlay.interactive.desc');
      keys.forEach((key, i) => {
        const probe = document.createElement('p');
        probe.className = 'ofc-demo-desc-probe';
        probe.setAttribute('aria-hidden', 'true');
        probe.setAttribute('data-desc-probe-key', key);
        probe.dataset.descProbeIndex = String(i);
        descEl.insertAdjacentElement('afterend', probe);
      });
    }
    function renderDescProbes() {
      root.querySelectorAll('.ofc-demo-desc-probe').forEach((probe) => {
        probe.textContent = t(probe.getAttribute('data-desc-probe-key'));
      });
    }

    function renderHeader() {
      progressEl.textContent = t('howToPlay.interactive.progress')
        .replace('{n}', String(step + 1))
        .replace('{total}', String(LAST_STEP + 1));

      if (step === 0) {
        titleEl.textContent = t('howToPlay.interactive.step0.title');
        descEl.textContent = t('howToPlay.interactive.step0.desc');
      } else if (step < LAST_STEP) {
        titleEl.textContent = t('howToPlay.interactive.step' + step + '.title');
        descEl.textContent = t('howToPlay.interactive.step' + step + '.desc');
      } else {
        titleEl.textContent = t('howToPlay.interactive.title');
        descEl.textContent = t('howToPlay.interactive.desc');
      }
      ensureDescProbes();
      renderDescProbes();
    }

    function renderHand() {
      const round = currentRound();
      if (!round) {
        // v30-followup2: step 0 (intro, before "開始練習") used to hide
        // #ofcDemoHand entirely (`hidden = true`), which meant its full
        // height (~94px including margin) only appeared once the learner
        // moved into round 1 -- the single biggest jump in #ofcDemo's
        // total height between any two adjacent steps, on top of the
        // per-round variance in .desc text length that's unavoidable
        // without truncating real instructions. Rendering the same 5
        // ghost placeholders round 1 will show (ROUNDS[1].dealt.length --
        // round 1 is always the next step from here) keeps the tray's
        // reserved height present from the very first screen, so entering
        // round 1 no longer visibly grows the widget.
        handEl.hidden = false;
        handEl.innerHTML = '';
        handEl.setAttribute('aria-label', t('howToPlay.interactive.handLabel'));
        const introCount = (ROUNDS[1] && ROUNDS[1].dealt.length) || 5;
        for (let i = 0; i < introCount; i++) {
          const ghost = document.createElement('div');
          ghost.className = 'ofc-card ofc-card-ghost';
          ghost.setAttribute('aria-hidden', 'true');
          handEl.appendChild(ghost);
        }
        return;
      }
      handEl.hidden = false;
      handEl.innerHTML = '';
      const labelKey = round.discard.length > 0 ? 'howToPlay.interactive.handLabel' : 'howToPlay.interactive.handLabelAllIn';
      handEl.setAttribute('aria-label', t(labelKey));
      // v30-followup: as cards leave the tray (placed on the board), an
      // invisible same-size "ghost" card takes their spot instead of just
      // leaving nothing behind -- keeps #ofcDemoHand's own row height full
      // for as long as this round lasts, so the tray doesn't visibly
      // shrink/jump each time the last card or two get placed (most
      // noticeable in round 1, where all 5 dealt cards leave the tray).
      // Mirrors the same "always render this many boxes" idea renderBoard()
      // already uses for empty board slots.
      placement.forEach((loc, idx) => {
        if (loc === 'tray') {
          handEl.appendChild(makeCardEl(round.dealt[idx], { idx, selected: selected === idx }));
        } else {
          const ghost = document.createElement('div');
          ghost.className = 'ofc-card ofc-card-ghost';
          ghost.setAttribute('aria-hidden', 'true');
          handEl.appendChild(ghost);
        }
      });
      handEl.classList.toggle('can-drop', !locked && selected !== null && placement[selected] !== 'tray');
    }

    function renderBoard() {
      const round = currentRound();
      const preset = boardBefore(step);

      ROW_ORDER.forEach((row) => {
        const slotsEl = rowEls[row].querySelector('[data-slots-for]');
        slotsEl.innerHTML = '';
        const presetCount = preset[row].length;

        // Preset cards (locked in from earlier rounds) always occupy the
        // leftmost `presetCount` absolute slots, in their fixed order —
        // immovable at this point, not drop/click targets.
        preset[row].forEach((card) => slotsEl.appendChild(makeCardEl(card, { preset: true })));

        // v29/v29c/v29d: slots presetCount..TOTAL_MAX[row]-1 are this
        // round's playable area, always rendered as the full fixed 3/5/5
        // grid (card or empty) rather than a growing/shrinking bar. Each
        // absolute slot is rendered at ITS OWN position — a card dropped
        // into slot i via liveSlot[idx] stays exactly there on re-render
        // instead of getting packed to the leftmost open slot (per user
        // feedback: "放的當下可以就放在我拉的位置，不會立刻放到最左邊").
        // Which absolute slot ends up holding which card has no effect on
        // scoring (row order was never meaningful — see the file header);
        // this is purely so the board visually matches where the visitor
        // put things until they move it or the round advances.
        const canClickDrop = round && !locked
          && selected !== null && placement[selected] !== row && dealtIn(row).length < openCap(row);
        for (let i = presetCount; i < TOTAL_MAX[row]; i++) {
          const idxHere = round
            ? placement.findIndex((loc, idx) => loc === row && liveSlot[idx] === i)
            : -1;
          if (idxHere !== -1) {
            slotsEl.appendChild(makeCardEl(round.dealt[idxHere], { idx: idxHere, selected: selected === idxHere }));
          } else {
            const empty = document.createElement('div');
            empty.className = 'ofc-demo-slot-empty';
            if (canClickDrop) empty.classList.add('can-drop');
            if (round) wireEmptySlot(empty, row, i);
            slotsEl.appendChild(empty);
          }
        }

        const capEl = rowEls[row].querySelector('.ofc-demo-row-cap');
        const total = presetCount + (round ? dealtIn(row).length : 0);
        const cap = round ? openCap(row) : 0;
        // v30-followup2: per user feedback, the final round (step ===
        // LAST_STEP) is a review/confirm step rather than an active
        // placement round like 2-4 -- by this point the back row is
        // always the one sitting at cap 0 (this round's data never adds
        // to it), so the "（這輪不開放）" hint that's genuinely useful
        // during rounds 2-4 (which row can still take a card varies each
        // time) just reads as clutter on the final row's label.
        const showLockedHint = round && cap === 0 && step !== LAST_STEP;
        capEl.textContent = total + '/' + TOTAL_MAX[row] + (showLockedHint ? ' ' + t('howToPlay.interactive.rowLocked') : '');
        rowEls[row].classList.toggle('full', total >= TOTAL_MAX[row]);
      });
    }

    // v29e-followup3: the per-round explanation used to live in its own
    // box below the board (`.ofc-demo-explain`), which -- across v29d-
    // followup2 and v29e-followup2 -- had to stay in the layout at its
    // full final height at all times (even pre-confirm, invisible or
    // showing a placeholder hint) purely so `.ofc-demo`'s total height
    // never changed at the moment of confirming (that height change was
    // what made the ::before background photo visibly reposition, see
    // those versions' notes). That box was still a real chunk of extra
    // vertical space the widget carried on every round, which is what
    // read as "this thing is too tall" per user feedback.
    //
    // This version removes that box entirely. The result (badge + the
    // same "recommended layout" explanation) now slides in *over*
    // #ofcDemoDesc -- the round's own instructions text, right under the
    // title -- instead of occupying its own separate space below the
    // board. #ofcDemoDesc and #ofcDemoResult are siblings inside
    // .ofc-demo-desc-wrap, a `display: grid` container with both children
    // sharing the same grid area (see css/style.css): CSS grid sizes a
    // shared area to whichever occupant is tallest, so the wrapper's
    // height is pinned to max(desc height, result height) for this round
    // as soon as both are rendered, and stays exactly that height whether
    // the result is showing or not -- no separate reserved block, and no
    // JS measurement needed to keep the height from jumping at confirm.
    //
    // v29e-followup5: the final round's real pass/fail result used to be a
    // separate box (#ofcDemoFeedback) below the board -- one more block of
    // vertical space the widget always carried once a round was confirmed.
    // Per user feedback ("此段文字應該要跟其他段一樣是覆蓋在標題下方文字欄"),
    // the final round now shares this exact same overlay too: same badge +
    // slide-in mechanism as rounds 1-4, just with buildFinalResultHtml()
    // supplying the richer per-row text instead of the round's canned
    // explanation. The badge itself carries the red "犯規了！" tone via the
    // existing .ofc-demo-result-badge.fail styling -- no separate tinted
    // box needed any more.
    function renderResult() {
      if (step >= 1 && step <= LAST_STEP) {
        const isFinal = step === LAST_STEP;
        const isDone = isFinal
          ? locked && (lastResult === 'legal' || lastResult === 'foul')
          : locked && (lastResult === 'success' || lastResult === 'corrected');
        descEl.classList.toggle('is-covered', isDone);
        if (isDone) {
          resultEl.innerHTML = isFinal ? buildFinalResultHtml() : buildRoundResultHtml();
        } else {
          resultEl.innerHTML = '';
          resultEl.classList.remove('is-shown');
        }
      } else {
        descEl.classList.remove('is-covered');
        resultEl.innerHTML = '';
        resultEl.classList.remove('is-shown');
      }
    }

    function buildRoundResultHtml() {
      const explainText = t('howToPlay.interactive.step' + step + '.explain');
      const badgeClass = lastResult === 'success' ? 'ok' : 'fail';
      const badgeText = lastResult === 'success'
        ? t('howToPlay.interactive.stepSuccessTitle')
        : t('howToPlay.interactive.correctedTitle');
      return '<span class="ofc-demo-result-badge ' + badgeClass + '">' + badgeText + '</span>' + explainText;
    }

    // Same per-row pass/fail evaluation renderFeedback() used to do, but
    // returns an HTML string for #ofcDemoResult instead of writing into
    // the now-removed #ofcDemoFeedback box. Still applies the .result-ok /
    // .result-foul classes directly on the board rows -- that highlight is
    // independent of the text box and stays exactly as before.
    function buildFinalResultHtml() {
      const info = {
        front: rankCards(fullRowForEval('front')),
        middle: rankCards(fullRowForEval('middle')),
        back: rankCards(fullRowForEval('back')),
      };
      const frontOk = compareRank(info.middle, info.front) >= 0;
      const backOk = compareRank(info.back, info.middle) >= 0;

      if (frontOk && backOk) {
        ROW_ORDER.forEach((row) => rowEls[row].classList.add('result-ok'));
        const body = t('howToPlay.interactive.resultSuccessBody')
          .replace('{back}', categoryName(info.back))
          .replace('{middle}', categoryName(info.middle))
          .replace('{front}', categoryName(info.front));
        return '<span class="ofc-demo-result-badge ok">' + t('howToPlay.interactive.stepSuccessTitle') + '</span>' + body;
      }
      const lines = [];
      if (!frontOk) {
        rowEls.front.classList.add('result-foul');
        rowEls.middle.classList.add('result-foul');
        lines.push(t('howToPlay.interactive.resultFoulLineFrontMiddle')
          .replace('{front}', categoryName(info.front))
          .replace('{middle}', categoryName(info.middle)));
      }
      if (!backOk) {
        rowEls.middle.classList.add('result-foul');
        rowEls.back.classList.add('result-foul');
        lines.push(t('howToPlay.interactive.resultFoulLineMiddleBack')
          .replace('{middle}', categoryName(info.middle))
          .replace('{back}', categoryName(info.back)));
      }
      lines.push(t('howToPlay.interactive.resultFoulHint'));
      return '<span class="ofc-demo-result-badge fail">' + t('howToPlay.interactive.resultFoulTitle') + '</span>' + lines.join('<br>');
    }

    // Called once, right when confirmCurrentRound() flips any round
    // (1-4, or the final pass/fail round) from unconfirmed to its result,
    // to slide #ofcDemoResult in over #ofcDemoDesc. Separate from
    // renderResult() itself (which just renders the current state with no
    // animation) so that navigating to a round doesn't replay the slide --
    // only the actual confirm action does.
    function playResultSlideIn() {
      resultEl.classList.remove('is-shown');
      void resultEl.offsetWidth;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => { resultEl.classList.add('is-shown'); });
      });
    }

    function renderHint() {
      hintEl.hidden = !quotaHintVisible;
      if (quotaHintVisible) {
        hintEl.textContent = t('howToPlay.interactive.quotaHint').replace('{n}', String(totalToPlace()));
      }
    }

    function renderDots() {
      dotsEl.innerHTML = '';
      for (let i = 0; i <= LAST_STEP; i += 1) {
        const dot = document.createElement('span');
        dot.className = 'ofc-demo-dot' + (i === step ? ' active' : '');
        dotsEl.appendChild(dot);
      }
    }

    function renderControls() {
      const round = currentRound();
      roundControls.hidden = !round;

      // v22: once a non-final round is locked, Confirm relabels itself
      // into "Next" and stays clickable — advancing no longer needs a
      // second click on the separate arrow. The final round has nowhere
      // to advance to (nextBtn/arrow is already hidden there), so it
      // keeps the plain disabled-after-lock behavior instead.
      const canAdvanceViaConfirm = locked && step < LAST_STEP;

      if (round) {
        const allPlaced = placement.filter((loc) => loc !== 'tray').length === totalToPlace();
        confirmBtn.disabled = canAdvanceViaConfirm ? false : (locked || !allPlaced);
        // v21: "出現就是亮的：有至少排一張牌在桌上" — reset is a plain
        // show/hide (not a disabled state), keyed only on whether any
        // card from this round is currently off the tray. It stays
        // available after a lock (e.g. round 5's foul feedback still
        // says "hit Reset and try again"), since that's the same
        // "at least one card on the table" condition.
        const anyPlaced = placement.some((loc) => loc !== 'tray');
        resetBtn.hidden = !anyPlaced;
      } else {
        resetBtn.hidden = true;
      }
      confirmBtn.textContent = canAdvanceViaConfirm ? t('howToPlay.interactive.next') : t('howToPlay.interactive.confirm');
      root.classList.toggle('locked', locked);

      // v21: prev/next are plain icon arrows now, always clickable — the
      // visitor can move freely between rounds regardless of whether the
      // current one is confirmed. The prev arrow doesn't exist at all on
      // step 0 (not just disabled); step 0 instead shows nextBtn as a
      // left-aligned text CTA ("Start Practicing") rather than an arrow —
      // see .ofc-demo-nav.is-intro in css/style.css.
      const isIntro = step === 0;
      navControls.classList.toggle('is-intro', isIntro);
      prevBtn.hidden = isIntro;
      nextBtn.hidden = step === LAST_STEP;
      nextBtn.classList.toggle('ofc-demo-cta', isIntro);
      nextBtn.textContent = isIntro ? t('howToPlay.interactive.step0.start') : '›';
      dotsEl.hidden = isIntro;
      if (!isIntro) renderDots();
    }

    function render() {
      renderHeader();
      renderHand();
      renderHint();
      renderBoard();
      renderResult();
      renderControls();
    }

    function goToStep(next) {
      step = Math.max(0, Math.min(LAST_STEP, next));
      resetRoundState();
      render();
    }

    prevBtn.addEventListener('click', () => goToStep(step - 1));
    nextBtn.addEventListener('click', () => goToStep(step + 1));
    restartBtn.addEventListener('click', () => goToStep(0));

    handEl.addEventListener('click', (e) => {
      if (!currentRound()) return;
      const cardEl = e.target.closest('.ofc-card');
      if (cardEl && cardEl.dataset.idx !== undefined) { selectCard(Number(cardEl.dataset.idx)); return; }
      if (cardEl) return;
      if (selected !== null) placeCard(selected, 'tray');
    });
    wireDropTarget(handEl, 'tray');

    ROW_ORDER.forEach((row) => {
      rowEls[row].addEventListener('click', (e) => {
        if (!currentRound()) return;
        const cardEl = e.target.closest('.ofc-card');
        if (cardEl && cardEl.dataset.idx !== undefined) { selectCard(Number(cardEl.dataset.idx)); return; }
        if (cardEl) return;
        if (selected !== null) placeCard(selected, row);
      });
      wireDropTarget(rowEls[row], row);
    });

    function cardElByIdx(idx) {
      return root.querySelector('.ofc-card[data-idx="' + idx + '"]');
    }

    // v29: FLIP-style animation for the auto-correct path — capture each
    // moved card's on-screen rect *before* the re-render, then after
    // render() has moved it into its new (correct) slot, jump it back to
    // the old position with a transform and immediately transition that
    // transform to none. Reads as the card sliding from where it was
    // dropped to where it belongs, with a brief glow while it moves.
    function playMoveAnimation(idxs, beforeRects) {
      idxs.forEach((idx, i) => {
        const before = beforeRects[i];
        const el = cardElByIdx(idx);
        if (!before || !el) return;
        const after = el.getBoundingClientRect();
        const dx = before.left - after.left;
        const dy = before.top - after.top;
        if (!dx && !dy) return;
        el.style.transition = 'none';
        el.style.transform = 'translate(' + dx + 'px, ' + dy + 'px)';
        el.classList.add('card-move-glow');
        // Force a reflow so the browser registers the jump-back position
        // above before we switch transition back on below — otherwise the
        // translate(0,0) below would just apply instantly with no visible
        // slide.
        void el.offsetWidth;
        el.style.transition = 'transform 0.45s ease';
        el.style.transform = 'translate(0, 0)';
        const cleanup = () => {
          el.style.transition = '';
          el.style.transform = '';
          el.classList.remove('card-move-glow');
          el.removeEventListener('transitionend', cleanup);
        };
        el.addEventListener('transitionend', cleanup);
        // Belt-and-suspenders in case transitionend doesn't fire (e.g. the
        // element gets re-rendered again before it does).
        setTimeout(cleanup, 600);
      });
    }

    function confirmCurrentRound() {
      if (locked) return;
      locked = true;
      selected = null;
      let pendingMoveIdxs = null;
      let pendingBeforeRects = null;
      if (step === LAST_STEP) {
        // v21: this is the one round that keeps a real pass/fail check —
        // all three rows are complete here, so back >= middle >= front is
        // actually meaningful (see file header). A foul now triggers the
        // bomb animation instead of routing through the removed "Show me
        // a foul" demo button.
        const info = {
          front: rankCards(fullRowForEval('front')),
          middle: rankCards(fullRowForEval('middle')),
          back: rankCards(fullRowForEval('back')),
        };
        const legal = compareRank(info.middle, info.front) >= 0 && compareRank(info.back, info.middle) >= 0;
        lastResult = legal ? 'legal' : 'foul';
        if (!legal) triggerBoom();
      } else {
        // v29d-followup: capture EVERY placed card's current on-screen
        // position before touching `placement`/`liveSlot` at all — this
        // now covers the "already correct" outcome too (not just the
        // auto-corrected one), because packLeftAll() below moves those
        // cards as well (per user feedback: a correct placement used to
        // keep whatever slot it was dropped in instead of also snapping
        // left on confirm).
        const trackedIdxs = placement
          .map((_, idx) => idx)
          .filter((idx) => placement[idx] !== 'tray');
        pendingMoveIdxs = trackedIdxs;
        pendingBeforeRects = trackedIdxs.map((idx) => {
          const el = cardElByIdx(idx);
          return el ? el.getBoundingClientRect() : null;
        });

        if (scriptMatches()) {
          lastResult = 'success';
        } else {
          // v21: no more blocking "wrong, try again" — silently move
          // every dealt card to its scripted row and explain the
          // recommended layout instead of making the visitor guess again.
          placement = placement.map((_, idx) => correctRowFor(idx));
          lastResult = 'corrected';
        }
        // v29d-followup: whichever outcome above, pack every one of this
        // round's placed cards flush-left within its row (ascending
        // dealt-index order) so a confirmed round never sits with a gap
        // at whatever slot the visitor happened to drop a card into.
        packLeftAll();
      }
      render();
      if (pendingMoveIdxs && pendingMoveIdxs.length) playMoveAnimation(pendingMoveIdxs, pendingBeforeRects);
      // v29e-followup5: was `if (step < LAST_STEP)` -- the final round's
      // pass/fail result now uses the same #ofcDemoResult slide-in as
      // rounds 1-4 (see renderResult() above), so it plays unconditionally.
      playResultSlideIn();
    }

    confirmBtn.addEventListener('click', () => {
      // v22: after a non-final round is locked, this same button is now
      // relabeled "Next" (see renderControls) — clicking it advances the
      // step instead of re-running confirmCurrentRound (which would just
      // return early anyway since `locked` is already true, but routing
      // it through goToStep is what actually moves the visitor forward).
      if (locked && step < LAST_STEP) { goToStep(step + 1); return; }
      confirmCurrentRound();
    });

    resetBtn.addEventListener('click', () => { resetRoundState(); render(); });

    // v29e-followup5: per user feedback ("手榴彈特效可以是爆炸效果嗎？"),
    // the grenade image stays but now reads as an actual explosion instead
    // of just an icon popping in -- a radial flash + a few flying debris
    // bits (both pure CSS, see .ofc-demo-boom-flash / -debris in
    // css/style.css) play alongside it, and the whole widget gets a short
    // shake. `root` here IS #ofcDemo (see initOfcDemo(root) below), so the
    // shake class goes straight on it.
    function triggerBoom() {
      boomEl.classList.remove('boom-play');
      root.classList.remove('ofc-demo-shake');
      // Restart the CSS animation even if it's already mid-play (e.g. the
      // visitor reset and fouled again) by forcing a reflow between the
      // remove and the re-add.
      void boomEl.offsetWidth;
      boomEl.classList.add('boom-play');
      root.classList.add('ofc-demo-shake');
    }

    document.querySelectorAll('.lang-switch button[data-lang]').forEach((btn) => {
      btn.addEventListener('click', () => render());
    });

    resetRoundState();
    render();
  }

  // v10: dropped the v9 "Read More" toggle per user feedback — the full
  // rule text + step list under #ofcMore is now always shown, so no JS
  // is needed for it any more (removed initReadMore() and its call).

  document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('ofcDemo');
    if (root) initOfcDemo(root);
  });
})();
