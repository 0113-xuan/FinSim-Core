(function(root) {
  'use strict';
  const T=root.EventTemplates;
  const paths={
    vehicle:'M4 10l2-5h12l2 5v8H4zM4 10h16M7 18v3M17 18v3M7 14h2M15 14h2',
    job:'M4 7h16v13H4zM8 7V4h8v3M4 12h16M10 12v3h4v-3',
    home:'M3 11l9-8 9 8M5 9v12h14V9M10 21v-7h4v7',
    moving:'M3 7l9-4 9 4v13H3zM3 7l9 4 9-4M12 11v9',
    marriage:'M12 20C5 15 2 12 3 8c1-5 7-5 9-1 2-4 8-4 9 1 1 4-2 7-9 12z',
    child:'M8 4l-2 8h14M6 12l3 5h8l3-5M3 4h5M9 20h.01M17 20h.01',
    travel:'M3 10l7 2 7 9 2-1-3-9 5-5-2-2-5 5-9-3z',
    study:'M3 4h7l2 2 2-2h7v15h-7l-2 2-2-2H3zM12 6v15',
    one_time:'M12 4v16M4 12h16',range:'M4 8h16M4 16h16M7 4v16M17 4v16'
  };
  function icon(code) {
    const svg=root.document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.classList.add('event-icon');
    const path=root.document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',paths[code]||paths.one_time);
    for(const[key,value]of Object.entries({fill:'none',stroke:'currentColor','stroke-width':'1.7','stroke-linecap':'round','stroke-linejoin':'round'}))path.setAttribute(key,value);
    svg.append(path);return svg;
  }
  function picker(container,{selected=null,locked=false,disabled=false,onSelect=()=>{}}={}) {
    const el=(tag,text,className)=>{const node=root.document.createElement(tag);if(text)node.textContent=text;if(className)node.className=className;return node;};
    container.replaceChildren();
    for(const[group,title]of [['life','人生事件'],['custom','自訂收支']]) {
      const entries=T.availableTemplates().filter(t=>t.group===group&&(!locked||t.id===selected));if(!entries.length)continue;
      const section=el('section',null,'template-group');section.setAttribute('aria-label',title);section.append(el('h3',title));
      const grid=el('div',null,'template-grid');
      for(const template of entries) {
        const button=el('button',null,'template-card');button.type='button';button.dataset.templateId=template.id;
        button.setAttribute('aria-pressed',String(template.id===selected));
        if(locked)button.setAttribute('aria-disabled','true');
        button.disabled=disabled;
        const heading=el('span',null,'template-title');heading.append(icon(template.icon),el('strong',template.name));
        button.append(heading,el('span',template.description,'template-description'));
        button.addEventListener('click',()=>{if(!locked&&!button.disabled)onSelect(template);});
        grid.append(button);
      }
      section.append(grid);container.append(section);
    }
    // Planned templates are one quiet line, not cards that look clickable but do nothing.
    const upcoming=T.templates.filter(t=>t.status!=='available').map(t=>t.name);
    if(!locked&&upcoming.length)container.append(el('p',`之後會加入：${upcoming.join('、')}。`,'template-upcoming'));
  }
  function select(container,id) {
    for(const button of container.querySelectorAll('[data-template-id]'))button.setAttribute('aria-pressed',String(button.dataset.templateId===id));
  }
  root.EventPicker={render:picker,select,icon};
})(globalThis);
