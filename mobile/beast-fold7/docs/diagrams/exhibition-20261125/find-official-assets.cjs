(async()=>{
 const s=await(await fetch('https://www.viture.com/beast')).text();
 const urls=[...s.matchAll(/(?:src|href|content)="([^"]+)"/g)].map(x=>x[1]);
 console.log([...new Set(urls)].filter(x=>/logo|favicon|beast.*png|beast.*webp/i.test(x)).slice(0,60).join('\n'));
})();
