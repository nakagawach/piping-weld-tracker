from pathlib import Path

path = Path('thumbnail_grid.py')
text = path.read_text(encoding='utf-8')

old_fav = "  const controls=document.querySelector('.controls');const toolbar=document.querySelector('.toolbar');\n  if(controls){{star.classList.add('icon-button');controls.insertBefore(star,document.getElementById('ocr')||controls.lastChild)}}else if(toolbar){{star.classList.add('icon-button');const anchor=toolbar.querySelector('#thumbnailGridButton, .spacer');toolbar.insertBefore(star,anchor?.nextSibling||toolbar.lastChild)}}"
new_fav = "  const pageTools=document.querySelector('.ui3-page-tools');const controls=document.querySelector('.controls');const toolbar=document.querySelector('.toolbar');\n  if(pageTools){{star.classList.add('icon-button');pageTools.appendChild(star)}}else if(controls){{star.classList.add('icon-button');const ocr=document.getElementById('ocr');controls.insertBefore(star,ocr&&ocr.parentNode===controls?ocr:controls.lastChild)}}else if(toolbar){{star.classList.add('icon-button');const anchor=toolbar.querySelector('#thumbnailGridButton, .spacer');toolbar.insertBefore(star,anchor?.nextSibling||toolbar.lastChild)}}"
assert text.count(old_fav) == 1, text.count(old_fav)
text = text.replace(old_fav, new_fav, 1)

old_grid = "  const controls=document.querySelector('.controls');\n  if(controls){{controls.insertBefore(button,document.getElementById('ocr')||controls.lastChild);}}\n  else {{\n    const toolbar=document.querySelector('.toolbar');\n    if(toolbar){{button.classList.add('icon-button');button.textContent='▦';button.setAttribute('aria-label','ページ一覧');const actionBar=toolbar.querySelector('.ui3-drawing');if(actionBar)actionBar.appendChild(button);else toolbar.insertBefore(button,toolbar.querySelector('.spacer')?.nextSibling||toolbar.lastChild);}}\n  }}"
new_grid = "  const pageTools=document.querySelector('.ui3-page-tools');const controls=document.querySelector('.controls');\n  if(pageTools){{button.classList.add('icon-button');button.textContent='▦';button.setAttribute('aria-label','ページ一覧');pageTools.appendChild(button);}}\n  else if(controls){{const ocr=document.getElementById('ocr');controls.insertBefore(button,ocr&&ocr.parentNode===controls?ocr:controls.lastChild);}}\n  else {{\n    const toolbar=document.querySelector('.toolbar');\n    if(toolbar){{button.classList.add('icon-button');button.textContent='▦';button.setAttribute('aria-label','ページ一覧');const actionBar=toolbar.querySelector('.ui3-drawing');if(actionBar)actionBar.appendChild(button);else toolbar.insertBefore(button,toolbar.querySelector('.spacer')?.nextSibling||toolbar.lastChild);}}\n  }}"
assert text.count(old_grid) == 1, text.count(old_grid)
text = text.replace(old_grid, new_grid, 1)

path.write_text(text, encoding='utf-8')
print('Dynamic page-list/favorite controls now target the unified page-tools group when present')
