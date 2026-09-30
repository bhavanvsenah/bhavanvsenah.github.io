'use strict';

// One page with three levels: the start screen, an open catalogue, or a text
// from a catalogue. Opening a catalogue moves both doors into the top corners
// and slides the catalogue up from below; the chosen door keeps glowing.
// Opening a text slides the reader up while the catalogue fades out. Clicking
// the glowing door or pressing Escape goes one level up, clicking the other
// door swaps catalogues. The leaf on the start screen opens the page about
// the artel, articles/about, in the same way, with both doors in the corners
// and neither glowing; one level up from it is the start screen. Other pages
// from articles/ are reached from that page (the brethren of the artel from
// its signature) and lead back to it: there either door goes one level up.
// Two readers take turns, so a text opened from a text slides up over it.
// State lives in the URL hash: #dharma for a catalogue,
// #dharma/trisharanasaptati for the text dharma/trisharanasaptati.html,
// #articles/about for articles/about.html.
{
  const stage = document.querySelector('.stage');
  const doors = [...stage.querySelectorAll('.door')];
  const leaf = stage.querySelector('.leaf');
  const catalogs = new Map([...stage.querySelectorAll('.catalog')].map((c) => [c.dataset.catalog, c]));
  const readers = [...stage.querySelectorAll('.reader')].map((panel) => ({
    panel,
    frame: panel.querySelector('iframe'),
    route: '', // the text loaded, or loading, in this reader
    ready: false,
    focus: false, // take the focus once shown
  }));
  const root = new URL('.', location.href); // the site's folder
  const fadeTimers = new Map();
  const ABOUT = 'articles/about';
  let route = '';
  let shown = null; // the reader showing the current text

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
  const sectionOf = (value) => value.split('/')[0];
  const isText = (value) => value.includes('/');

  // A catalogue name; or a catalogue name, or "articles", and the name of a
  // page in that folder.
  const parse = (value) => {
    const [, folder, page] = /^([a-z]+)(?:\/([a-z0-9-]+))?$/.exec(value) ?? [];
    return catalogs.has(folder) || (page && folder === 'articles') ? value : '';
  };

  // Percent-decoding that gives '' for a malformed address such as "#%"
  // instead of throwing.
  const decode = (value) => {
    try {
      return decodeURIComponent(value);
    } catch {
      return '';
    }
  };

  const routeFromUrl = () => parse(decode(location.hash.slice(1)));

  // The route of a page of this site that the reader can show, or ''; also ''
  // for an address the browser cannot parse.
  const routeOf = (href) => {
    let url;
    try {
      url = new URL(href, location.href);
    } catch {
      return '';
    }
    if (url.origin !== root.origin || !url.pathname.startsWith(root.pathname)) return '';
    const page = /^(.+)\.html$/.exec(decode(url.pathname.slice(root.pathname.length)));
    const value = page ? parse(page[1]) : '';
    return isText(value) ? value : '';
  };

  // One level up: a text goes back to its catalogue, the page about the artel
  // to the start screen, any other page from articles/ to the page about.
  const parentOf = (value) => {
    if (!isText(value)) return '';
    if (catalogs.has(sectionOf(value))) return sectionOf(value);
    return value === ABOUT ? '' : ABOUT;
  };

  // A plain left click; with a modifier the browser keeps its own behaviour.
  const plain = (event) =>
    event.button === 0 && !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey);

  // Corner transforms, in CSS pixels. Both doors shrink by the same factor,
  // so the stone keeps its size relative to the wheel.
  const layout = () => {
    const width = document.documentElement.clientWidth;
    const size = clamp(width * 0.07, 48, 84); // corner diameter of the widest door
    const margin = clamp(width * 0.025, 12, 32);
    const k = size / Math.max(...doors.map((door) => door.offsetWidth));
    doors.forEach((door, index) => {
      const x = index === 0 ? margin + size / 2 : width - margin - size / 2;
      const y = margin + size / 2;
      const dx = x - (door.offsetLeft + door.offsetWidth / 2);
      const dy = y - (door.offsetTop + door.offsetHeight / 2);
      door.style.setProperty('--corner', `translate(${dx}px, ${dy}px) scale(${k})`);
    });
    stage.style.setProperty('--k', k);
    stage.style.setProperty('--catalog-top', `${size + 2 * margin}px`);
  };

  // Put a panel below the screen without animating it: parked ("down") or,
  // for a reader about to load a text, "loading" (below the screen as well,
  // but not hidden).
  const park = (panel, state = 'down') => {
    clearTimeout(fadeTimers.get(panel));
    panel.classList.add('instant');
    panel.dataset.state = state;
    panel.getBoundingClientRect();
    panel.classList.remove('instant');
  };

  const setPanel = (panel, state) => {
    clearTimeout(fadeTimers.get(panel));
    panel.dataset.state = state;
    // A reader is never inert: styles.css hides it off screen instead.
    if (!readers.some((reader) => reader.panel === panel)) panel.inert = state !== 'up';
    if (state === 'fading') {
      const duration = parseFloat(getComputedStyle(panel).transitionDuration) * 1000;
      fadeTimers.set(panel, setTimeout(() => park(panel), duration));
    }
  };

  // Show one panel, or none: whichever others are showing fade out, or slide
  // back down when the start screen returns.
  const showPanel = (panel) => {
    for (const other of stage.querySelectorAll('.panel[data-state="up"]')) {
      if (other !== panel) setPanel(other, panel ? 'fading' : 'down');
    }
    if (panel && panel.dataset.state !== 'up') setPanel(panel, 'up');
  };

  // Load a text into a reader, afresh even if the reader holds it already.
  // Replacing the frame's location keeps the switch out of the history, so
  // Back leaves the text rather than the frame.
  const load = (reader, value) => {
    reader.route = value;
    reader.ready = false;
    const { frame } = reader;
    const url = new URL(`${value}.html`, location.href).href;
    const doc = frame.contentDocument;
    if (doc && doc.URL !== 'about:blank') frame.contentWindow.location.replace(url);
    else frame.src = url;
  };

  const titleOf = (value) => {
    if (isText(value) && shown?.route === value && shown.ready && shown.frame.contentDocument) {
      return shown.frame.contentDocument.title;
    }
    const catalog = catalogs.get(sectionOf(value));
    return catalog ? catalog.querySelector('h2').textContent : 'Переводы';
  };

  const apply = (next, push) => {
    const from = route;
    if (next === from) return;
    route = next;
    const section = sectionOf(next);
    const text = isText(next);

    if (section) stage.dataset.section = section;
    else delete stage.dataset.section;

    for (const door of doors) {
      const selected = door.dataset.route === section;
      if (selected) {
        door.setAttribute('aria-current', 'true');
        door.setAttribute('aria-label', text ? 'К каталогу' : 'На главную');
      } else {
        door.removeAttribute('aria-current');
        door.removeAttribute('aria-label');
      }
    }

    leaf.inert = Boolean(next);
    for (const reader of readers) {
      if (reader.panel.dataset.state === 'loading') park(reader.panel); // no longer wanted
    }
    if (text) {
      // Every text is loaded afresh into the reader off screen, which slides
      // up over whatever is showing only once the text has loaded (see the
      // frames' load handler): a large text would otherwise come up as an
      // empty panel and then just appear. It loads just below the screen and
      // not hidden: a text loaded into an inert or hidden frame did not
      // scroll with the wheel in Chrome once shown.
      shown = readers.find((reader) => reader !== shown);
      shown.focus = false;
      park(shown.panel, 'loading');
      load(shown, next);
    } else {
      shown = null;
      showPanel(next ? catalogs.get(next) : null);
    }

    document.title = titleOf(next);
    if (push) history.pushState(null, '', next ? `#${next}` : location.pathname + location.search);
    document.dispatchEvent(new CustomEvent('sectionchange', { detail: { from: sectionOf(from), to: section } }));
  };

  const focusAfter = (from) => {
    if (isText(route)) {
      if (shown) shown.focus = true; // its reader is still hidden
      return;
    }
    const target = route
      ? catalogs.get(route).querySelector('h2')
      : (doors.find((door) => door.dataset.route === sectionOf(from)) ?? leaf);
    target?.focus({ preventScroll: true });
  };

  const go = (next) => {
    const from = route;
    apply(next, true);
    focusAfter(from);
  };

  const up = () => {
    if (route) go(parentOf(route));
  };

  for (const reader of readers) reader.frame.addEventListener('load', () => {
    // The document is out of reach when the site is opened as a file; the
    // text still shows, only its title and Escape stay with the frame.
    const { frame } = reader;
    const doc = frame.contentDocument;
    if (!reader.route || doc?.URL === 'about:blank') return;
    reader.ready = true;
    // The text is in: its reader comes up now, unless another route has
    // taken over meanwhile.
    if (reader === shown) {
      showPanel(reader.panel);
      if (reader.focus) frame.focus({ preventScroll: true });
    }
    reader.focus = false;
    if (!doc) return;
    frame.title = doc.title;
    if (route === reader.route) document.title = doc.title;
    // Keys pressed inside the text do not reach this page.
    doc.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') up();
    });
    // Nor does the pointer: pass its moves on in this page's coordinates, so
    // glow.js still lights the doors as it approaches them, and say when it
    // leaves, so a door it last touched does not stay lit.
    const pass = (type, target) => (event) => {
      const box = frame.getBoundingClientRect();
      target.dispatchEvent(new PointerEvent(type, {
        clientX: event.clientX + box.left,
        clientY: event.clientY + box.top,
        pointerType: event.pointerType,
      }));
    };
    doc.addEventListener('pointermove', pass('pointermove', window), { passive: true });
    doc.documentElement.addEventListener('pointerleave', pass('pointerleave', document.documentElement));
    // Links within the text (contents, stanzas, notes) stay as they are. A
    // link to another page of this site that the reader can show opens it
    // here, with its own address; any other link out of the text, to other
    // sites above all, opens in a new tab.
    const here = doc.URL.split('#')[0];
    const outside = (link) => link.href.split('#')[0] !== here;
    for (const link of doc.links) {
      if (outside(link) && !routeOf(link.href)) {
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
      }
    }
    doc.addEventListener('click', (event) => {
      const link = event.target.closest('a[href]');
      const next = link && outside(link) && plain(event) && routeOf(link.href);
      if (next) {
        event.preventDefault();
        go(next);
      }
    });
  });

  // The doors, the leaf and the titles in a catalogue are buttons, not links,
  // so the browser shows no address over them; each names its route in
  // data-route. The leaf and a title open a text in the reader.
  stage.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-route]');
    if (!button) return;
    const next = parse(button.dataset.route);
    if (button.classList.contains('door')) {
      if (isText(parentOf(route)) || next === sectionOf(route)) up();
      else go(next);
    } else if (isText(next)) {
      go(next);
    }
  });

  addEventListener('keydown', (event) => {
    if (event.key === 'Escape') up();
  });

  addEventListener('popstate', () => {
    const from = route;
    apply(routeFromUrl(), false);
    focusAfter(from);
  });

  addEventListener('resize', layout);

  // Open straight into a catalogue or a text when the address has one, without animation.
  stage.classList.add('instant');
  layout();
  apply(routeFromUrl(), false);
  stage.getBoundingClientRect();
  requestAnimationFrame(() => stage.classList.remove('instant'));
}
