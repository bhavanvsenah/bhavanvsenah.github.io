'use strict';

// Books and real HTML links are already in index.html (generated from JSON).
// Enhance native disclosures only; do not fetch, erase or recreate the catalog.
{
  const animateDisclosure = (details, content) => {
    const summary = details.querySelector('summary');
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    let animation = null;
    let expanded = details.open;
    content.inert = !expanded;
    const finish = () => {
      animation?.cancel();
      animation = null;
      details.open = expanded;
      content.inert = !expanded;
      content.style.removeProperty('overflow');
    };
    summary.addEventListener('click', (event) => {
      if (reduced.matches || !content.animate) return;
      event.preventDefault();
      const from = details.open ? content.getBoundingClientRect().height : 0;
      const opacity = details.open ? getComputedStyle(content).opacity : 0;
      expanded = !expanded;
      animation?.cancel();
      details.open = true;
      content.inert = !expanded;
      content.style.overflow = 'hidden';
      const to = expanded ? content.scrollHeight : 0;
      animation = content.animate([
        { height: `${from}px`, opacity },
        { height: `${to}px`, opacity: expanded ? 1 : 0 },
      ], { duration: 320, easing: 'cubic-bezier(.2,.75,.25,1)' });
      animation.onfinish = finish;
    });
    details.addEventListener('toggle', () => {
      if (!animation) {
        expanded = details.open;
        content.inert = !expanded;
      }
    });
    reduced.addEventListener('change', () => { if (animation) finish(); });
  };

  for (const details of document.querySelectorAll('.catalog-category details')) {
    animateDisclosure(details, details.querySelector('.category-content'));
  }
}
