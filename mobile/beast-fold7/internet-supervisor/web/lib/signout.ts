import {safeOrigin} from './policy.ts';
export async function guardSignOut(origin:string|null,expected:string|undefined,viewer:string|undefined,revoke:(sid:string)=>Promise<unknown>){
  const reject=(error:string,status:number)=>Response.json({error},{status,headers:{'Cache-Control':'no-store'}});
  if(!safeOrigin(origin,expected))return reject('허용되지 않은 요청이에요',403);
  if(viewer){
    try{await revoke(viewer);}catch{return reject('로그아웃을 완료하지 못했어요. 다시 시도해 주세요.',503);}
  }
  return null;
}
