const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {spawn} = require('node:child_process');
const assert = require('node:assert/strict');

const root = process.argv[2];
const out = __dirname;
const captureDir = path.join(out, 'unity-b-capture-v10');
fs.mkdirSync(captureDir, {recursive:true});
const fixture = JSON.parse(fs.readFileSync(path.join(root, 'tests/fixtures/spatial_guidance_v1.json'), 'utf8'));
const session = 'pamphlet-b-ui-v10';
let sequence = 0;
let lastTime = 0;
const server = http.createServer((req,res) => {
  if (req.url !== '/state.json') {res.writeHead(404); res.end(); return;}
  const now = Math.max(lastTime+1, Date.now());
  lastTime = now;
  const message = structuredClone(fixture.expected);
  Object.assign(message, {
    session_id:session, frame_id:++sequence, timestamp_ms:now, frame_age_ms:0,
    current_state:'S3', current_label:'Fasten screw B', target:'screw_b',
    next_action:'나사 B를 조여주세요.', source:'synthetic_ui_capture',
    guidance:{schema_version:'assembly_guidance_v1', phase:'GUIDING', reason:'',
      acknowledgement:'', acknowledgement_remaining_ms:0,
      hold_progress:'none',hold_remaining_ms:0}
  });
  Object.assign(message.spatial, {
    target_id:'B', pose_frame_id:sequence,pose_timestamp_ms:now,pose_age_ms:0,
    left_pixel:[1237,248],right_pixel:[1200,248]
  });
  const body=JSON.stringify(message);
  res.writeHead(200,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});
  res.end(body);
});
server.listen(0,'127.0.0.1',()=>{
  const url='http://127.0.0.1:'+server.address().port+'/state.json';
  const config={schema_version:'beast_spatial_preview_config_v1',session_id:session,state_url:url,
    display_profile_id:fixture.profile.profile_id,duration_seconds:14};
  for(const key of ['camera_profile_id','workspace_profile_id','camera_profile_sha256','workspace_profile_sha256'])
    config[key]=fixture.profile[key];
  const file=path.join(out,'unity-b-preview-config-v10.json');
  fs.writeFileSync(file,JSON.stringify(config,null,2));
  const exe=path.join(root,'outputs/unity_p1/BeastAssemblyGuide.exe');
  assert(fs.existsSync(exe));
  const child=spawn(exe,['-screen-fullscreen','0','-logFile',path.join(out,'unity-b-player-v10.log'),
    '--spatial-preview-config',file,'--capture-ui',captureDir],{
    cwd:root,windowsHide:true,stdio:'ignore'
  });
  const timer=setTimeout(()=>child.kill(),45000);
  child.once('error',err=>{clearTimeout(timer);server.close();console.error(err);process.exitCode=1;});
  child.once('exit',code=>{
    clearTimeout(timer);server.close();
    const images=fs.readdirSync(captureDir).filter(x=>x.endsWith('.png'));
    console.log(JSON.stringify({code,requests:sequence,captures:images}));
    process.exitCode=code===0&&images.length>0?0:1;
  });
});

