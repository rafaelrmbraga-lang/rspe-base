import re,sys
p='abas_modelo.html'; s=open(p,encoding='utf-8').read()
i=s.index('/*TEMAS_LIBS*/'); j=s.index('</style></head>')
s=s[:i]+'/*TEMAS_LIBS*/\n'+open('temas_libs.css',encoding='utf-8').read()+s[j:]
open(p,'w',encoding='utf-8').write(s)
