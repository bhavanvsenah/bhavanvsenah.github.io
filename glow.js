'use strict';

// Lights each image as the pointer approaches it: --heat grows evenly from 0
// at the middle point between the two images to 1 on the image's opaque
// pixels. Distances come from glowmaps.js. With a catalogue open the same
// rule works for the corner images, and the chosen one stays at full glow.
{
  const EASE = 0.35; // share of the remaining gap closed each frame
  const MOVE_TIME = 700; // ms to keep tracking the images while they travel

  const data = window.glowMaps;
  const stage = document.querySelector('.stage');
  const doors = [...document.querySelectorAll('.door')];

  if (data && doors.length) {
    const { grid, maps } = data;
    const entries = doors.map((door) => {
      const img = door.querySelector('img');
      // The address carries a version mark (?v=…); the maps are keyed by the file.
      const bytes = Uint8Array.from(atob(maps[img.getAttribute('src').split('?')[0]]), (c) => c.charCodeAt(0));
      return { door, img, bytes, heat: 0 };
    });
    document.documentElement.classList.add('proximity');

    const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

    // Bilinear sample of the distance grid at u, v in 0..1; result in image widths.
    const sample = (bytes, u, v) => {
      const x = clamp(u * grid - 0.5, 0, grid - 1);
      const y = clamp(v * grid - 0.5, 0, grid - 1);
      const x0 = Math.floor(x);
      const y0 = Math.floor(y);
      const x1 = Math.min(x0 + 1, grid - 1);
      const y1 = Math.min(y0 + 1, grid - 1);
      const fx = x - x0;
      const fy = y - y0;
      const at = (i, j) => bytes[j * grid + i];
      const top = at(x0, y0) * (1 - fx) + at(x1, y0) * fx;
      const bottom = at(x0, y1) * (1 - fx) + at(x1, y1) * fx;
      return (top * (1 - fy) + bottom * fy) / 255;
    };

    let pointer = null;
    let frame = 0;
    let movingUntil = 0;

    // Distance in CSS pixels from a point to the nearest opaque pixel of the image.
    const distanceTo = ({ bytes }, box, px, py) => {
      const x = clamp(px, box.left, box.right);
      const y = clamp(py, box.top, box.bottom);
      const outside = Math.hypot(px - x, py - y);
      const inside = sample(bytes, (x - box.left) / box.width, (y - box.top) / box.height) * box.width;
      const slack = box.width / grid / 2; // half a grid cell counts as touching
      return Math.max(0, outside + inside - slack);
    };

    const tick = () => {
      frame = 0;
      let settling = false;
      const boxes = entries.map(({ img }) => img.getBoundingClientRect());
      const visible = boxes.every((box) => box.width);
      const middle = {
        x: boxes.reduce((sum, box) => sum + box.left + box.width / 2, 0) / boxes.length,
        y: boxes.reduce((sum, box) => sum + box.top + box.height / 2, 0) / boxes.length,
      };
      const chosen = stage.dataset.section;
      entries.forEach((entry, index) => {
        let target = 0;
        if (entry.door.dataset.route === chosen) {
          target = 1;
        } else if (pointer && visible) {
          const box = boxes[index];
          const reach = distanceTo(entry, box, middle.x, middle.y);
          const distance = distanceTo(entry, box, pointer.x, pointer.y);
          target = reach > 0 ? clamp(1 - distance / reach, 0, 1) : Number(distance === 0);
        }
        entry.heat += (target - entry.heat) * EASE;
        if (Math.abs(target - entry.heat) < 0.002) entry.heat = target;
        else settling = true;
        entry.door.style.setProperty('--heat', entry.heat.toFixed(3));
      });
      if (settling || performance.now() < movingUntil) frame = requestAnimationFrame(tick);
    };

    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(tick);
    };

    addEventListener(
      'pointermove',
      (event) => {
        if (event.pointerType === 'touch') return;
        pointer = { x: event.clientX, y: event.clientY };
        schedule();
      },
      { passive: true },
    );

    document.documentElement.addEventListener('pointerleave', () => {
      pointer = null;
      schedule();
    });

    // The images travel between the centre and the corners: follow them.
    document.addEventListener('sectionchange', () => {
      movingUntil = performance.now() + MOVE_TIME;
      schedule();
    });

    addEventListener('resize', schedule);

    // A catalogue opened straight from the address starts with its door lit.
    schedule();
  }
}
