import 'next-auth';
declare module 'next-auth' {interface Session {ownerId:string;viewerSession:string;}}
