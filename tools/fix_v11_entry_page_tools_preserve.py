from pathlib import Path

path = Path('ui_shell.py')
text = path.read_text(encoding='utf-8')
old = "  const ocr=document.getElementById('ocr'),bbox=document.getElementById('bboxEdit'),save=document.getElementById('save'),reset=document.getElementById('reset'),bulkDelete=document.getElementById('bulkDelete'),pageState=document.getElementById('pageState');\n  if(!top||!controls||!prev||!next||!pageInput||!ocr||!save)return;"
new = "  const ocr=document.getElementById('ocr'),bbox=document.getElementById('bboxEdit'),save=document.getElementById('save'),reset=document.getElementById('reset'),bulkDelete=document.getElementById('bulkDelete'),pageState=document.getElementById('pageState');\n  const preservedEntryPageTools=[document.querySelector('[data-thumbnail-grid-launch]'),document.querySelector('.page-favorite-view')].filter(Boolean);\n  if(!top||!controls||!prev||!next||!pageInput||!ocr||!save)return;"
assert text.count(old) == 1, text.count(old)
text = text.replace(old, new, 1)
old2 = "  controls.replaceChildren(pageGroup,viewGroup,pageTools,screenActions,more);\n\n  const updateTotal=()=>{{"
new2 = "  controls.replaceChildren(pageGroup,viewGroup,pageTools,screenActions,more);\n  for(const el of preservedEntryPageTools)pageTools.append(el);\n\n  const updateTotal=()=>{{"
assert text.count(old2) == 1, text.count(old2)
text = text.replace(old2, new2, 1)
path.write_text(text, encoding='utf-8')
print('Preserved existing Entry page-list/favorite controls before toolbar regrouping')
