import type {IncomingMessage} from 'node:http';
import {isIP} from 'node:net';

export function clientIP(req:IncomingMessage,trustedProxy?:'127.0.0.1'):string|null{
  const peer=req.socket.remoteAddress;
  if(!trustedProxy)return peer??'unknown';
  if(peer!=='127.0.0.1'&&peer!=='::ffff:127.0.0.1')return null;
  // The single local reverse proxy must overwrite, never append, X-Real-IP.
  const ip=req.headers['x-real-ip'];
  if(typeof ip!=='string'||!isIP(ip))return null;
  return isIP(ip)===6?new URL(`http://[${ip}]`).hostname.slice(1,-1):ip;
}
