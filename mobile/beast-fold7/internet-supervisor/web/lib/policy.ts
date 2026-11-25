export function isOwner(value:unknown,owner:string|undefined){
  return typeof value==='string'&&!!owner&&/^\d+$/.test(owner)&&value===owner;
}
export function canSignIn(value:unknown,owner:string|undefined,publicLogin?:string){
  return typeof value==='string'&&/^[1-9][0-9]{0,19}$/.test(value)&&(publicLogin==='true'||isOwner(value,owner));
}
export function safeOrigin(origin:string|null,expected:string|undefined){
  return !!expected&&origin===expected;
}
