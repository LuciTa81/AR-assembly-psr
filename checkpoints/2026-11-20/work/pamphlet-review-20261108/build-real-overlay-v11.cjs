const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const sharp = require('C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const out = __dirname;
const width = 1530, height = 1020;
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

(async () => {
  const previous = JSON.parse(fs.readFileSync(path.join(out, 'visual-provenance-v10.json')));
  assert.equal(sha(previous.photo), previous.photo_sha256, 'Original photograph changed');
  const photo = path.join(out, 'photo-only-v10-compact.png');
  const base = await sharp(photo).removeAlpha().raw().toBuffer();
  assert.equal(base.length, width * height * 3);
  const captures = path.join(out, 'unity-overlay-capture-v11');
  const black = await sharp(path.join(captures, 'black.png')).removeAlpha().raw().toBuffer({resolveWithObject:true});
  const white = await sharp(path.join(captures, 'white.png')).removeAlpha().raw().toBuffer({resolveWithObject:true});
  for (const {info} of [black,white]) {
    assert.equal(info.width, width);
    assert.equal(info.height, height);
  }
  assert.ok(black.data.some(value=>value>32),'Unity foreground render is blank');
  assert.ok(white.data.some(value=>value>240),'Unity white matte is blank');
  // Two matte renders recover opacity, including the subtle black text shadow.
  const rgba = Buffer.alloc(width * height * 4);
  let matteDisagreement = 0;
  for (let i = 0; i < width * height; i++) {
    const p = i*3, q = i*4;
    const differences = [0,1,2].map(c => white.data[p+c] - black.data[p+c]);
    matteDisagreement = Math.max(matteDisagreement, Math.max(...differences)-Math.min(...differences));
    const alpha = Math.max(0, Math.min(255, Math.round(255 - differences.reduce((a,b)=>a+b,0)/3)));
    for (let c = 0; c < 3; c++) rgba[q+c] = alpha ? Math.min(255,Math.round(black.data[p+c] * 255 / alpha)) : 0;
    rgba[q+3] = alpha;
  }
  assert.ok(matteDisagreement <= 3, `Mismatched matte captures: ${matteDisagreement}`);
  const overlay = await sharp(rgba,{raw:{width,height,channels:4}}).png().toBuffer();
  const result = await sharp(base,{raw:{width,height,channels:3}}).composite([{input:overlay}]).removeAlpha().raw().toBuffer();
  let unchangedPhotoPixels = 0, overlayPixels = 0, unexpectedChanges = 0;
  for (let i = 0; i < width*height; i++) {
    if (rgba[i*4+3]) { overlayPixels++; continue; }
    unchangedPhotoPixels++;
    if ([0,1,2].some(c => result[i*3+c] !== base[i*3+c])) unexpectedChanges++;
  }
  assert.equal(unexpectedChanges,0,'Photo pixels outside the overlay must remain unchanged');
  assert.ok(overlayPixels>10000 && overlayPixels<width*height*0.15,'Unexpected overlay coverage');
  assert.ok(unchangedPhotoPixels>width*height*0.85,'The photograph must dominate the image');
  const output = path.join(out,'ar-guidance-B-photo-unity-v11.png');
  await sharp(result,{raw:{width,height,channels:3}}).png().toFile(output);
  await sharp(overlay).toFile(path.join(out,'unity-overlay-transparent-v11.png'));
  await sharp(output).resize(765,510).png().toFile(path.join(out,'ar-guidance-B-photo-unity-v11-half.png'));
  await sharp(output).resize(306,204).png().toFile(path.join(out,'ar-guidance-B-photo-unity-v11-small.png'));
  const report = {
    photo:previous.photo,photo_sha256:previous.photo_sha256,baseCrop:photo,baseCrop_sha256:sha(photo),
    transformation:{sourceCrop:previous.crop,resize:previous.resize,pamphletCrop:previous.pamphletCrop},
    unityProject:path.join(out,'unity-overlay-v11'),unityVersion:'6000.3.25f1',
    rendering:'Orthographic Unity camera into RenderTexture; two-matte alpha recovery',
    font:{family:'Noto Sans KR',weight:600,style:'SemiBold',source:'Local installed variable font instantiated at weight 600'},
    captureFiles:['black.png','white.png'].map(name=>({path:path.join(captures,name),sha256:sha(path.join(captures,name))})),
    text:['나사 B · 2/4','나사 B를 조여주세요.'],
    targetCenterInImage:[1042.3,248],placement:'Editorial image coordinates, not calibrated headset projection',
    additions:['subdued lid perimeter','corner accents','active B ring','short downward arrow','Korean screen-facing guidance'],
    photoGeometryChanged:false,generativeImageModelUsed:false,cameraStarted:false,
    existingRuntimeChanged:false,calibrationChanged:false,googleSlidesChanged:false,
    description:'Real archived photo with separately rendered Unity design-preview graphics; not a through-lens photograph.',
    width,height,matteDisagreement,unchangedPhotoPixels,overlayPixels,unexpectedChanges,output
  };
  fs.writeFileSync(path.join(out,'visual-provenance-v11.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({output,matteDisagreement,unchangedPhotoPixels,overlayPixels,unexpectedChanges}));
})().catch(error=>{console.error(error);process.exitCode=1;});
