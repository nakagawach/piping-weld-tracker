(() => {
  const current = document.currentScript?.src;
  if (!current) return;
  const sibling = name => new URL(name, current).href;
  window.__progressFieldEntryAssets = {
    smartUrl: sibling('entry_smart_field_draw.js')
  };
  const load = (src, id, next) => {
    if (document.getElementById(id)) { next?.(); return; }
    const script = document.createElement('script');
    script.id = id;
    script.src = src;
    script.onload = () => next?.();
    script.onerror = () => console.error('script load failed:', src);
    document.head.appendChild(script);
  };
  load(sibling('progress_list_panel_base.js'), 'progressListPanelBaseScript', () => {
    load(sibling('progress_field_entry_mode.js'), 'progressFieldEntryModeScript');
  });
})();
