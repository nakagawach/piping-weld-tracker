from pathlib import Path

path = Path('ui_shell.py')
text = path.read_text(encoding='utf-8')
old = "  const more=document.getElementById('moreMenu');\n  if(!toolbar||!top||!prev||!next||!pageField||!more)return;"
new = "  const more=document.getElementById('moreMenu');\n  const preservedProgressActions=[document.getElementById('drawingMemoLaunch'),document.getElementById('drawingMemoEdit'),document.querySelector('a[aria-label=\\\"進捗一覧\\\"]')].filter(Boolean);\n  if(!toolbar||!top||!prev||!next||!pageField||!more)return;"
assert text.count(old) == 1, text.count(old)
text = text.replace(old, new, 1)
old2 = "  toolbar.replaceChildren(pageGroup,viewGroup,pageTools,screenActions,more);\n\n  const collect=()=>{{"
new2 = "  toolbar.replaceChildren(pageGroup,viewGroup,pageTools,screenActions,more);\n  for(const el of preservedProgressActions)screenActions.append(el);\n\n  const collect=()=>{{"
assert text.count(old2) == 1, text.count(old2)
text = text.replace(old2, new2, 1)
path.write_text(text, encoding='utf-8')
print('Preserved existing progress-specific controls before toolbar regrouping')
