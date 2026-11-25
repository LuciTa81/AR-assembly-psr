// Vercel CLI puts the Windows host name in an HTTP header, which must be ASCII.
const os=require('node:os');
const name=os.hostname();
if(!/^[\x00-\x7f]*$/.test(name))os.hostname=()=> 'ar-deploy-workstation';
require('node:module').syncBuiltinESMExports();
