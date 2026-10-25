/* THE "MORE" AUDIT (2026-10-24). Doug: "audit all the show more links in the entire system and make sure they all
   work". The rule it checks (memory: app navigation rules): every "more" opens, and says truthfully what it hides.

   Run in the page after it has rendered: paste the function into the page (the browser pane's JavaScript tool),
   then `await moreAudit()`, on each page in turn. It returns a list of problems, each with the control's text and where it sits, and a count of what it checked:
     inline    <details class="moreinl"> "+N more": opening it must show N more items
     listbox   a list footer: "show more" must add rows; "showing X of Y" with X < Y must have a way to the rest
     svg       a "+N more" box in a diagram must be clickable
     loose     any other text saying "N more" / "show more" / "show all" that is not a control at all        */
async function moreAudit() {
  const problems = [], checked = {inline: 0, listbox: 0, svg: 0, loose: 0};
  const where = el => {
    const sec = el.closest('details,section,.lb,[id]');
    const h = sec && (sec.querySelector(':scope > summary, :scope > h2, :scope > h3, .vp-h2')?.textContent || sec.id);
    return (h || '').trim().slice(0, 60);
  };
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // 1. inline expanders: "+N more" must reveal N items
  for (const d of document.querySelectorAll('details.moreinl')) {
    checked.inline++;
    const s = d.querySelector(':scope > summary');
    const n = +((s?.textContent || '').match(/\+(\d+)/) || [])[1];
    const kids = [...d.children].filter(c => c !== s && c.textContent.trim());
    const items = kids.length > 1 ? kids.length : (kids[0] ? kids[0].children.length || 1 : 0);
    if (!d.textContent.replace(s?.textContent || '', '').trim())
      problems.push({kind: 'inline', text: s?.textContent, where: where(d), why: 'opens empty'});
    else if (n && items && Math.abs(items - n) > 0 && kids.length > 1)
      problems.push({kind: 'inline', text: s?.textContent, where: where(d), why: `promises ${n}, holds ${items}`});
  }

  // 2. list footers: a "show more" button must add rows; a partial list must not strand its rest
  for (const lb of document.querySelectorAll('.lb')) {
    const foot = lb.querySelector('.lbfoot');
    if (!foot || foot.hidden) continue;
    checked.listbox++;
    const txt = foot.textContent.replace(/\s+/g, ' ').trim();
    const m = txt.match(/(\d[\d,]*) of (\d[\d,]*)/);
    const btn = [...foot.querySelectorAll('button,a,[role=button]')].find(b => !b.hidden && b.offsetParent !== null);
    const shownBefore = lb.querySelectorAll('.lbrow:not([hidden])').length;
    if (btn) {
      btn.click();
      await sleep(1200);
      const shownAfter = lb.querySelectorAll('.lbrow:not([hidden])').length;
      if (shownAfter <= shownBefore && !document.querySelector('.lb-loading'))
        problems.push({kind: 'listbox', text: btn.textContent.trim(), where: where(lb),
                       why: `clicked: rows ${shownBefore} -> ${shownAfter}`, foot: txt});
    } else if (m && +m[1].replace(/,/g, '') < +m[2].replace(/,/g, '')) {
      problems.push({kind: 'listbox', text: txt, where: where(lb), why: 'says there is more and offers no way to it'});
    }
  }

  // 3. "+N more" boxes in diagrams must be clickable
  for (const t of document.querySelectorAll('svg text')) {
    if (!/\+\d+ more/.test(t.textContent)) continue;
    checked.svg++;
    const g = t.closest('a, g[onclick], g[data-href], g[style*="cursor"], [role=button]');
    const cur = getComputedStyle(t.closest('g') || t).cursor;
    if (!g && cur !== 'pointer')
      problems.push({kind: 'svg', text: t.textContent, where: where(t), why: 'a diagram says it hides more and cannot be opened'});
  }

  // 4. any other text promising more that is not a control
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const loose = /(\+\d+ more|\b\d+ more\b|show more|show all|see all|view all)/i;
  let node;
  while ((node = walker.nextNode())) {
    if (!loose.test(node.textContent)) continue;
    const el = node.parentElement;
    if (!el || el.closest('svg, details.moreinl > summary, .lbfoot, script, style, [hidden]')) continue;
    if (el.offsetParent === null) continue;
    checked.loose++;
    const control = el.closest('a, button, summary, [onclick], [role=button], label');
    if (!control && getComputedStyle(el).cursor !== 'pointer')
      problems.push({kind: 'loose', text: node.textContent.trim().slice(0, 80), where: where(el),
                     why: 'promises more and is not a control'});
  }
  // 5. a counted section ("1 Kings 70", "Where the text speaks of it 583") must hold what its count promises: its
  //    sub-sections' counts add up to it, or it holds that many rows
  checked.counted = 0;
  for (const d of document.querySelectorAll('details')) {
    const s = d.querySelector(':scope > summary');
    const m = (s?.textContent || '').replace(/\s+/g, ' ').trim().match(/(\d[\d,]*)$/);
    if (!m || d.classList.contains('moreinl')) continue;
    checked.counted++;
    const n = +m[1].replace(/,/g, '');
    d.open = true;
    const subs = [...d.querySelectorAll(':scope > * details, :scope > details')]
      .filter(x => x.parentElement.closest('details') === d)
      .map(x => +(((x.querySelector(':scope > summary')?.textContent || '').match(/(\d[\d,]*)\s*$/) || [])[1] || '0').replace(/,/g, ''));
    const rows = [...d.querySelectorAll('.refmore, .lbrow, li')].filter(x => x.closest('details') === d).length;
    const have = subs.length ? subs.reduce((a, b) => a + b, 0) : rows;
    if (have && have !== n)
      problems.push({kind: 'counted', text: s.textContent.replace(/\s+/g, ' ').trim().slice(0, 60), where: where(d),
                     why: `says ${n}, holds ${have}${subs.length ? ' (its sections add up to that)' : ' rows'}`});
  }

  // 6. a verse button must show its verse
  const rb = document.querySelector('.refmore');
  if (rb) {
    checked.refmore = 1;
    const before = document.body.innerText.length;
    rb.click();
    await sleep(1500);
    if (document.body.innerText.length <= before)
      problems.push({kind: 'refmore', text: rb.textContent.trim(), where: where(rb), why: 'clicked: nothing opened'});
  }
  return {url: location.pathname + location.hash, checked, problems: problems.slice(0, 40)};
}
