import type {IncomingHttpHeaders} from 'node:http';

// Call only after the BFF service credential has been authenticated.
export function requestOwner(headers:IncomingHttpHeaders,fallback:string,multiUser=false):string|null{
  const value=headers['x-owner-id'];
  if(!multiUser)return value===undefined||value===fallback?fallback:null;
  return typeof value==='string'&&/^[1-9][0-9]{0,19}$/.test(value)?value:null;
}
