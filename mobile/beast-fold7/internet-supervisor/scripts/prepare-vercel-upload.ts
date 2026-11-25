import {cpSync, existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync} from 'node:fs';
import {resolve, join, relative, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const destination=resolve(process.argv[2]??'');
if(!process.argv[2]||existsSync(destination))throw new Error('Provide a new destination directory');
const files=['next-env.d.ts','next.config.mjs','package.json','pnpm-lock.yaml','tsconfig.json','types.d.ts'];
for(const folder of ['app','lib','public']){
  for(const name of readdirSync(join(root,'web',folder),{recursive:true,withFileTypes:true})){
    if(name.isSymbolicLink())throw new Error('Symlinks are not allowed');
    if(name.isFile())files.push(relative(join(root,'web'),join(name.parentPath,name.name)));
  }
}
mkdirSync(destination,{recursive:true});
for(const file of files){
  if(file.split(/[\\/]/).some(part=>part.startsWith('.')))throw new Error('Hidden source excluded');
  const target=join(destination,file);mkdirSync(dirname(target),{recursive:true});
  cpSync(join(root,'web',file),target);
}
mkdirSync(join(destination,'shared'));
cpSync(join(root,'shared','protocol.ts'),join(destination,'shared','protocol.ts'));
for(const file of ['video.ts','avc.ts'])cpSync(join(root,'shared',file),join(destination,'shared',file));
for(const [file,from,to] of [
  ['lib/wire.ts','../../shared/protocol.ts','../shared/protocol.ts'],
  ['app/ui/dashboard.tsx','../../../shared/protocol','../../shared/protocol'],
  ['app/ui/video-preview.tsx','../../../shared/video','../../shared/video'],
  ['app/ui/video-preview.tsx','../../../shared/avc','../../shared/avc'],
]){
  const target=join(destination,file),source=readFileSync(target,'utf8');
  if(source.split(from).length!==2)throw new Error(`Unexpected import in ${file}`);
  writeFileSync(target,source.replace(from,to));
}
const manifest=[...files,'shared/protocol.ts','shared/video.ts','shared/avc.ts'].sort().map(file=>({file,sha256:createHash('sha256').update(readFileSync(join(destination,file))).digest('hex')}));
writeFileSync(destination+'.manifest.json',JSON.stringify(manifest,null,2));
console.log(JSON.stringify({destination,files:manifest.length,secretsIncluded:false}));
