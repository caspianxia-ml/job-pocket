/* Only visible DOM is read. No API, cookies, hidden JSON or framework state. */
({action, selectors: s, phrases = []}) => {
  const visible = e => !!e && !!e.getClientRects().length &&
    getComputedStyle(e).visibility !== 'hidden' && getComputedStyle(e).display !== 'none' &&
    (!e.checkVisibility || e.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}));
  const first = (root, choices) => {
    for (const css of choices) {
      const el = [...root.querySelectorAll(css)].find(visible);
      if (el) return el;
    }
    return null;
  };
  const text = (root, choices) => first(root, choices)?.innerText?.trim() || '';
  const list = (root, choices) => {
    for (const css of choices) {
      const items = [...root.querySelectorAll(css)].filter(visible)
        .map(e => e.innerText.trim()).filter(Boolean);
      if (items.length) return [...new Set(items)];
    }
    return [];
  };
  const root = () => {
    for (const css of s.feed_roots) {
      const roots = [...document.querySelectorAll(css)].filter(visible);
      if (roots.length > 1) throw Error('FEED_AMBIGUOUS: 推荐列表容器不唯一，请配置精确 CSS');
      if (roots.length === 1) return roots[0];
    }
    throw Error('FEED_MISSING: 未找到可见推荐列表，请检查页面和 CSS');
  };
  if (action === 'guard') {
    const body = document.body?.innerText || '';
    const risk = first(document, s.risk_visible);
    const phrase = phrases.find(p => body.includes(p));
    return {risk: !!risk || !!phrase, phrase: phrase || '', login: !!first(document, s.login_visible)};
  }
  if (action === 'detail') return {
    jd: text(document, s.jd), address: text(document, s.address),
    detail_title: text(document, s.detail_title)
  };
  if (action === 'scroll') {
    let scroll = root();
    while (scroll !== document.body && scroll !== document.documentElement &&
           !(scroll.scrollHeight > scroll.clientHeight + 20 &&
             /auto|scroll/.test(getComputedStyle(scroll).overflowY))) {
      scroll = scroll.parentElement || document.documentElement;
    }
    if (scroll === document.body || scroll === document.documentElement) scroll = document.scrollingElement;
    scroll.scrollBy({top: Math.max(500, scroll.clientHeight * 0.8), behavior: 'instant'});
    return true;
  }
  const feed = root();
  let cards = [];
  for (const css of s.cards) {
    cards = [...feed.querySelectorAll(css)].filter(visible);
    if (cards.length) break;
  }
  return cards.map(card => {
    const link = first(card, s.link);
    return {
      href: link?.getAttribute('href') || '', title: text(card, s.title),
      salary: text(card, s.salary), location: text(card, s.location),
      requirements: list(card, s.requirements), skills: list(card, s.skills),
      company: text(card, s.company), company_info: list(card, s.company_info),
      benefits: text(card, s.benefits), card_text: (card.innerText || '').trim()
    };
  });
}
